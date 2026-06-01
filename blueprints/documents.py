from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response, send_file
from flask_login import login_required, current_user
from database import execute, query
import os
import weasyprint
from tasks.pdf_tasks import generate_pdf_task
from celery.result import AsyncResult
from celery_app import celery
from services.institutional_report_service import role_can_access_report_type

documents_bp = Blueprint('documents', __name__, url_prefix='/documents')

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
        flash(f'Erro ao salvar receituário: {str(e)}', 'danger')
        
    return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-receituario')

@documents_bp.route('/<int:patient_id>/receituario/<int:doc_id>/delete', methods=['POST'])
@login_required
def delete_receituario(patient_id, doc_id):
    doc = query("SELECT created_by FROM receituarios WHERE id = %s", (doc_id,), one=True)
    if not doc or (current_user.id != doc['created_by'] and not current_user.is_admin):
        flash('Sem permissão para excluir este receituário.', 'danger')
        return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-receituario')
        
    try:
        execute('DELETE FROM receituarios WHERE id = %s AND patient_id = %s', (doc_id, patient_id))
        flash('Receituário excluído.', 'success')
    except Exception as e:
        flash(f'Erro ao excluir receituário: {str(e)}', 'danger')
        
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
        flash(f'Erro ao salvar atestado: {str(e)}', 'danger')
        
    return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-atestado')

@documents_bp.route('/<int:patient_id>/atestado/<int:doc_id>/delete', methods=['POST'])
@login_required
def delete_atestado(patient_id, doc_id):
    doc = query("SELECT created_by FROM atestados WHERE id = %s", (doc_id,), one=True)
    if not doc or (current_user.id != doc['created_by'] and not current_user.is_admin):
        flash('Sem permissão para excluir este atestado.', 'danger')
        return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-atestado')
        
    try:
        execute('DELETE FROM atestados WHERE id = %s AND patient_id = %s', (doc_id, patient_id))
        flash('Atestado excluído.', 'success')
    except Exception as e:
        flash(f'Erro ao excluir atestado: {str(e)}', 'danger')
        
    return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-atestado')

@documents_bp.route('/<int:patient_id>/receituario/<int:doc_id>/pdf', methods=['GET'])
@login_required
def pdf_receituario(patient_id, doc_id):
    doc_row = query("SELECT * FROM receituarios WHERE id = %s AND patient_id = %s", (doc_id, patient_id), one=True)
    patient = query("SELECT * FROM patients WHERE id = %s", (patient_id,), one=True)
    prof = query("SELECT * FROM users WHERE id = %s", (doc_row['created_by'],), one=True)
    
    if not doc_row or not patient:
        return "Not found", 404
        
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
    prof = query("SELECT * FROM users WHERE id = %s", (doc['created_by'],), one=True)
    
    if not doc or not patient:
        return "Not found", 404
        
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
    task = AsyncResult(task_id, app=celery)
    
    if task.state == 'SUCCESS':
        return redirect(url_for('documents.download_pdf', filename=filename))
    elif task.state == 'FAILURE':
        flash('Ocorreu um erro ao gerar o PDF. Tente novamente.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # PENDING ou STARTED - Renderiza a página de loader
    return render_template('pdfs/loading.html', task_id=task_id, filename=filename, status=task.state)

@documents_bp.route('/download/<filename>')
@login_required
def download_pdf(filename):
    pdf_dir = os.path.join(os.getcwd(), 'pdf_temp')
    path = os.path.join(pdf_dir, filename)

    if filename.startswith('relatorio_'):
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
        if not current_user.can('reports:view'):
            flash('Acesso negado para relatórios institucionais.', 'danger')
            return redirect(url_for('main.dashboard'))
        if report and not role_can_access_report_type(current_user.role, report['report_type']):
            flash('Seu perfil não pode acessar este relatório.', 'danger')
            return redirect(url_for('reports.institutional'))
    
    if not os.path.exists(path):
        flash('Arquivo PDF não foi encontrado', 'danger')
        return redirect(url_for('main.dashboard'))
        
    return send_file(path, as_attachment=False, mimetype='application/pdf')
