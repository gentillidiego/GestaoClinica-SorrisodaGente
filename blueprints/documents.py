from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response
from flask_login import login_required, current_user
from database import execute, query
import os
import re
import weasyprint
from tasks.pdf_tasks import generate_pdf_task
from celery.result import AsyncResult
from celery_app import celery
from services.institutional_report_service import role_can_access_report_type
from services.bi_report_service import BI_REPORT_TYPE
from services.security_service import audit_log, deny_access
from services.sensitive_file_service import safe_file_in_directory, sensitive_file_response
from services.web_security_service import flash_internal_error, flash_recorded_error

documents_bp = Blueprint('documents', __name__, url_prefix='/documents')


def _clinical_pdf_context(filename):
    patterns = (
        (
            'receituario',
            r'^receituario_(\d+)_(\d+)\.pdf$',
            """
            SELECT r.id, r.patient_id
            FROM receituarios r
            WHERE r.id = %s AND r.patient_id = %s
            """,
            lambda match: (int(match.group(1)), int(match.group(2))),
        ),
        (
            'atestado',
            r'^atestado_(\d+)_(\d+)\.pdf$',
            """
            SELECT a.id, a.patient_id
            FROM atestados a
            WHERE a.patient_id = %s AND a.id = %s
            """,
            lambda match: (int(match.group(1)), int(match.group(2))),
        ),
        (
            'estomatologia',
            r'^encaminhamento_(\d+)_(\d+)\.pdf$',
            """
            SELECT e.id, e.patient_id
            FROM estomatologia e
            WHERE e.id = %s AND e.patient_id = %s
            """,
            lambda match: (int(match.group(1)), int(match.group(2))),
        ),
    )
    for document_kind, pattern, sql, params_factory in patterns:
        match = re.fullmatch(pattern, filename)
        if match:
            return {
                'matched': True,
                'document_kind': document_kind,
                'record': query(sql, params_factory(match), one=True),
            }
    return {'matched': False, 'document_kind': None, 'record': None}


def _can_access_pdf(filename):
    clinical_context = _clinical_pdf_context(filename)
    if clinical_context['matched']:
        if not clinical_context['record']:
            return False
        if not (
            current_user.can('patients:view')
            and current_user.can('documents:generate')
        ):
            return False
        if clinical_context['document_kind'] == 'estomatologia':
            return current_user.can('estomatologia:view')
        return True

    legacy_report = re.fullmatch(r'relatorio_gerencial_(\d+)\.pdf', filename)
    if legacy_report:
        owner_id = int(legacy_report.group(1))
        return current_user.can('reports:view') and (
            current_user.id == owner_id or current_user.is_admin
        )

    report = query(
        """
        SELECT report_type
        FROM generated_reports
        WHERE filename = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (filename,),
        one=True,
    )
    if not report:
        return False
    if report['report_type'] == BI_REPORT_TYPE:
        return current_user.can('bi:view')
    return (
        current_user.can('reports:view')
        and role_can_access_report_type(current_user.role, report['report_type'])
    )


def _deny_pdf_access(filename):
    return deny_access(
        permissions={
            'all_of': [],
            'any_of': ['documents:generate', 'reports:view', 'bi:view'],
        },
        reason='pdf_scope_denied',
    )


@documents_bp.route('/signatures/<int:event_id>')
@login_required
def signature_receipt(event_id):
    event = query(
        """
        SELECT se.*, p.nome as patient_display_name, p.cpf as patient_display_cpf,
               u.full_name as signer_full_name, u.cro as signer_cro, u.cro_uf as signer_cro_uf
        FROM signature_events se
        LEFT JOIN patients p ON p.id = se.patient_id
        LEFT JOIN users u ON u.id = se.signed_by
        WHERE se.id = %s
        """,
        (event_id,),
        one=True,
    )
    if not event:
        flash('Comprovante de assinatura não encontrado.', 'danger')
        return redirect(url_for('main.dashboard'))

    audit_log(
        action='signature_receipt_viewed',
        module='documents',
        entity_type='signature_event',
        entity_id=event_id,
        patient_id=event['patient_id'],
        details={
            'document_type': event['document_type'],
            'document_id': event['document_id'],
            'signature_mode': event['signature_mode'],
            'document_hash': event['document_hash'],
        },
    )
    return render_template('documents/signature_receipt.html', event=event)

@documents_bp.route('/<int:patient_id>/receituario/add', methods=['POST'])
@login_required
def add_receituario(patient_id):
    uso = request.form.get('uso')
    
    medicamentos = request.form.getlist('medicamento[]')
    quantidades = request.form.getlist('quantidade[]')
    usos_med = request.form.getlist('uso_med[]')
    
    import json
    prescricao_list = []
    for med, qtd, umed in zip(medicamentos, quantidades, usos_med):
        if med.strip():
            prescricao_list.append({
                'medicamento': med.strip(),
                'quantidade': qtd.strip(),
                'uso': umed.strip()
            })
            
    if not prescricao_list:
        flash('Adicione pelo menos um medicamento para a prescrição.', 'danger')
        return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-receituario')
        
    prescricao = json.dumps(prescricao_list)
        
    try:
        execute('''
            INSERT INTO receituarios (patient_id, created_by, uso, prescricao)
            VALUES (%s, %s, %s, %s)
        ''', (patient_id, current_user.id, uso, prescricao))
        flash('Receituário salvo com sucesso.', 'success')
    except Exception as e:
        flash_internal_error('Falha ao salvar receituário')
        
    return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-receituario')

@documents_bp.route('/<int:patient_id>/receituario/<int:doc_id>/delete', methods=['POST'])
@login_required
def delete_receituario(patient_id, doc_id):
    doc = query(
        """
        SELECT created_by
        FROM receituarios
        WHERE id = %s AND patient_id = %s
        """,
        (doc_id, patient_id),
        one=True,
    )
    if not doc or (current_user.id != doc['created_by'] and not current_user.is_admin):
        flash('Sem permissão para excluir este receituário.', 'danger')
        return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-receituario')
        
    try:
        execute('DELETE FROM receituarios WHERE id = %s AND patient_id = %s', (doc_id, patient_id))
        flash('Receituário excluído.', 'success')
    except Exception as e:
        flash_internal_error('Falha ao excluir receituário')
        
    return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-receituario')

@documents_bp.route('/<int:patient_id>/atestado/add', methods=['POST'])
@login_required
def add_atestado(patient_id):
    motivo = request.form.get('motivo')
    dias = request.form.get('dias_repouso')
    cid = request.form.get('cid')
    observacao = request.form.get('observacao')
    
    try:
        execute('''
            INSERT INTO atestados (patient_id, created_by, motivo, dias_repouso, cid, observacao)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (patient_id, current_user.id, motivo, dias, cid, observacao))
        flash('Atestado salvo com sucesso.', 'success')
    except Exception as e:
        flash_internal_error('Falha ao salvar atestado')
        
    return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-atestado')

@documents_bp.route('/<int:patient_id>/atestado/<int:doc_id>/delete', methods=['POST'])
@login_required
def delete_atestado(patient_id, doc_id):
    doc = query(
        """
        SELECT created_by
        FROM atestados
        WHERE id = %s AND patient_id = %s
        """,
        (doc_id, patient_id),
        one=True,
    )
    if not doc or (current_user.id != doc['created_by'] and not current_user.is_admin):
        flash('Sem permissão para excluir este atestado.', 'danger')
        return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-atestado')
        
    try:
        execute('DELETE FROM atestados WHERE id = %s AND patient_id = %s', (doc_id, patient_id))
        flash('Atestado excluído.', 'success')
    except Exception as e:
        flash_internal_error('Falha ao excluir atestado')
        
    return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-atestado')

@documents_bp.route('/<int:patient_id>/receituario/<int:doc_id>/pdf', methods=['GET'])
@login_required
def pdf_receituario(patient_id, doc_id):
    doc_row = query("SELECT * FROM receituarios WHERE id = %s AND patient_id = %s", (doc_id, patient_id), one=True)
    patient = query("SELECT * FROM patients WHERE id = %s", (patient_id,), one=True)
    
    if not doc_row or not patient:
        return "Not found", 404
    prof = query("SELECT * FROM users WHERE id = %s", (doc_row['created_by'],), one=True)
        
    doc = dict(doc_row)
    import json
    try:
        if doc['prescricao'] and doc['prescricao'].strip().startswith('['):
            doc['prescricao_parsed'] = json.loads(doc['prescricao'])
        else:
            doc['prescricao_parsed'] = None
    except:
        doc['prescricao_parsed'] = None
        
    html = render_template('pdfs/receituario_pdf.html', doc=doc, patient=patient, prof=prof)
    
    # Prepara caminhos
    pdf_dir = os.path.join(os.getcwd(), 'pdf_temp')
    os.makedirs(pdf_dir, exist_ok=True)
    filename = f'receituario_{doc_id}_{patient_id}.pdf'
    output_path = os.path.join(pdf_dir, filename)

    # Chama Celery
    task = generate_pdf_task.delay(html, output_path)
    return redirect(url_for('documents.pdf_status', task_id=task.id, filename=filename))

@documents_bp.route('/<int:patient_id>/atestado/<int:doc_id>/pdf', methods=['GET'])
@login_required
def pdf_atestado(patient_id, doc_id):
    doc = query("SELECT * FROM atestados WHERE id = %s AND patient_id = %s", (doc_id, patient_id), one=True)
    patient = query("SELECT * FROM patients WHERE id = %s", (patient_id,), one=True)
    
    if not doc or not patient:
        return "Not found", 404
    prof = query("SELECT * FROM users WHERE id = %s", (doc['created_by'],), one=True)
        
    html = render_template('pdfs/atestado_pdf.html', doc=doc, patient=patient, prof=prof)
    
    pdf_dir = os.path.join(os.getcwd(), 'pdf_temp')
    os.makedirs(pdf_dir, exist_ok=True)
    filename = f'atestado_{patient_id}_{doc_id}.pdf'
    output_path = os.path.join(pdf_dir, filename)
    
    task = generate_pdf_task.delay(html, output_path)
    return redirect(url_for('documents.pdf_status', task_id=task.id, filename=filename))

@documents_bp.route('/<int:patient_id>/estomatologia/<int:est_id>/pdf', methods=['GET'])
@login_required
def pdf_estomatologia(patient_id, est_id):
    doc = query("SELECT * FROM estomatologia WHERE id = %s AND patient_id = %s", (est_id, patient_id), one=True)
    patient = query("SELECT * FROM patients WHERE id = %s", (patient_id,), one=True)

    if not doc or not patient:
        return "Not found", 404

    # Obtém dados de triagem, se houver
    triage = query("""
        SELECT s.codigo, m.nome as municipio_nome
        FROM triagem_senhas s
        JOIN municipios m ON s.municipio_id = m.id
        WHERE s.patient_id = %s
        ORDER BY s.id DESC LIMIT 1
    """, (patient_id,), one=True)

    html = render_template('pdfs/encaminhamento_estomatologia_pdf.html', doc=doc, patient=patient, triage=triage)

    pdf_dir = os.path.join(os.getcwd(), 'pdf_temp')
    os.makedirs(pdf_dir, exist_ok=True)
    filename = f'encaminhamento_{est_id}_{patient_id}.pdf'
    output_path = os.path.join(pdf_dir, filename)

    task = generate_pdf_task.delay(html, output_path)
    return redirect(url_for('documents.pdf_status', task_id=task.id, filename=filename))

@documents_bp.route('/status/<task_id>/<filename>')
@login_required
def pdf_status(task_id, filename):
    if not _can_access_pdf(filename):
        return _deny_pdf_access(filename)

    task = AsyncResult(task_id, app=celery)
    
    if task.state == 'SUCCESS':
        return redirect(url_for('documents.download_pdf', filename=filename))
    elif task.state == 'FAILURE':
        flash_recorded_error(
            f'Falha assíncrona ao gerar PDF task_id={task_id}',
            'Não foi possível gerar o PDF. Tente novamente.',
        )
        return redirect(url_for('main.dashboard'))
    
    # PENDING ou STARTED - Renderiza a página de loader
    return render_template('pdfs/loading.html', task_id=task_id, filename=filename, status=task.state)

@documents_bp.route('/download/<filename>')
@login_required
def download_pdf(filename):
    if not _can_access_pdf(filename):
        return _deny_pdf_access(filename)

    pdf_dir = os.path.join(os.getcwd(), 'pdf_temp')
    try:
        path = safe_file_in_directory(pdf_dir, filename)
    except Exception:
        audit_log(
            action='pdf_download_blocked',
            module='documents',
            status='denied',
            details={'filename': filename, 'reason': 'invalid_or_missing_file'},
        )
        flash('Arquivo PDF não foi encontrado', 'danger')
        return redirect(url_for('main.dashboard'))

    audit_log(
        action='pdf_downloaded',
        module='documents',
        entity_type='generated_pdf',
        entity_id=filename,
        details={'filename': filename},
    )
    return sensitive_file_response(path, as_attachment=False, mimetype='application/pdf')
