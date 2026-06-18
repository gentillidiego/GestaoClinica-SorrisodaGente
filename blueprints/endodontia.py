import os
import uuid

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from database import execute, query
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from constants import can_sign_clinical_document
from services.endodontia_service import (
    ENDODONTIA_FORM_OPTIONS,
    build_anamnesis_risk_summary,
    build_budget_summary,
    build_case_details_payload,
    build_channel_payloads,
    build_diagnosis_context,
    build_endodontia_budget_items,
    build_proservation_evaluation_payload,
    build_proservation_schedule_payloads,
    build_protocol_safety_context,
    build_session_context,
    build_session_payload,
    parse_json_list,
    suggest_typical_channels,
)
from services.security_service import audit_log, permission_required
from services.sensitive_file_service import sensitive_file_response
from services.google_drive_service import get_drive_service, ensure_patient_drive_folder, upload_file_in_memory, download_file_in_memory
import io
from flask import Response
import mimetypes
from services.signature_evidence_service import (
    SIGNATURE_MODE_CANVAS,
    build_generic_signature_payload,
    register_signature_event,
)
from services.visual_media_service import (
    build_endodontia_image_metadata,
    get_endodontia_image_category_options,
    get_comparison_label_options,
    is_previewable_visual_file,
    normalize_visual_category,
)

endodontia_bp = Blueprint('endodontia', __name__, url_prefix='/endodontia')

ENDODONTIA_IMAGE_ALLOWED_EXTENSIONS = {
    '.jpg',
    '.jpeg',
    '.png',
    '.webp',
    '.tif',
    '.tiff',
    '.dcm',
    '.dicom',
}


def _as_int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _get_endodontia_case(endo_id):
    return query('''
        SELECT e.*, p.nome as patient_name,
               COALESCE(u.full_name, u.username) as profissional_nome,
               u.username as profissional_username
        FROM endodontia e
        JOIN patients p ON e.patient_id = p.id
        LEFT JOIN users u ON e.aluno_id = u.id
        WHERE e.id = %s
    ''', (endo_id,), one=True)


def _case_unavailable(case):
    return (not case) or case.get('cancelado_em') or case.get('status') == 'Cancelado'


def _decorate_endo_image(row):
    item = dict(row)
    item['category_label'] = dict(get_endodontia_image_category_options()).get(
        normalize_visual_category(item.get('visual_category'), 'periapical_inicial'),
        'Imagem endodôntica',
    )
    item['previewable'] = is_previewable_visual_file(item.get('filename') or item.get('file_path'))
    if item.get('filename') and '.' in item['filename']:
        item['format_label'] = item['filename'].rsplit('.', 1)[-1].upper()
    else:
        item['format_label'] = (item.get('formato') or 'arquivo').upper()
    return item


def _create_proservation_schedule(endo, followup_id, session_payload):
    if session_payload.get('etapa_realizada') != 'obturacao' or session_payload.get('status_sessao') != 'realizada':
        return []

    scheduled = []
    for item in build_proservation_schedule_payloads(endo, session_payload.get('data')):
        proservation_id = execute(
            '''
            INSERT INTO endodontia_proservacao (
                patient_id, endodontia_id, followup_id, tipo_retorno,
                data_prevista, status, lembrete_dias
            )
            VALUES (%s, %s, %s, %s, %s, 'planejado', %s)
            ON CONFLICT (endodontia_id, tipo_retorno) DO NOTHING
            RETURNING id
            ''',
            (
                endo['patient_id'],
                endo['id'],
                followup_id,
                item['tipo_retorno'],
                item['data_prevista'],
                item['lembrete_dias'],
            ),
        )
        if proservation_id:
            scheduled.append({**item, 'id': proservation_id})
    return scheduled


def _get_endodontia_cost_references():
    rows = query(
        '''
        SELECT sigtap_code, sigtap_name, public_cost, private_reference,
               reference_label, source, methodology_status
        FROM procedure_cost_references
        WHERE active = TRUE
          AND sigtap_code IN ('0307020061', '0307020045', '0307020053')
        '''
    ) or []
    return {row['sigtap_code']: dict(row) for row in rows}

@endodontia_bp.route('/<int:patient_id>/add_element', methods=['POST'])
@login_required
def add_element(patient_id):
    elemento = request.form.get('elemento_dentario')
    if not elemento:
        flash('O elemento dentário é obrigatório.', 'danger')
        return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-endodontia')
        
    try:
        endo_id = execute('''
            INSERT INTO endodontia (patient_id, elemento_dentario, aluno_id)
            VALUES (%s, %s, %s)
            RETURNING id
        ''', (patient_id, elemento, current_user.id))
        audit_log(
            action='endodontia_case_created',
            module='endodontia',
            entity_type='endodontia',
            entity_id=endo_id,
            patient_id=patient_id,
            details={
                'elemento_dentario': elemento,
                'profissional_id': current_user.id,
            },
        )
        flash(f'Elemento {elemento} adicionado para acompanhamento endodôntico.', 'success')
    except Exception as e:
        audit_log(
            action='endodontia_case_create_failed',
            module='endodontia',
            patient_id=patient_id,
            status='failed',
            details={'elemento_dentario': elemento, 'error': str(e)},
        )
        flash(f'Erro ao adicionar elemento: {str(e)}', 'danger')
        
    return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-endodontia')

@endodontia_bp.route('/followup/<int:endo_id>')
@login_required
def followup(endo_id):
    endo = _get_endodontia_case(endo_id)
    
    if not endo:
        flash('Registro de endodontia não encontrado.', 'danger')
        return redirect(url_for('patients.list_patients'))
    if _case_unavailable(endo):
        flash('Este acompanhamento endodôntico foi cancelado e está disponível apenas na linha do tempo/auditoria.', 'warning')
        return redirect(url_for('patients.view_patient', id=endo['patient_id']) + '#tab-endodontia')
        
    followups = query('''
        SELECT f.*, u.username as professor_nome, u.role as professor_role
        FROM endodontia_followup f
        LEFT JOIN users u ON f.professor_id = u.id
        WHERE f.endodontia_id = %s
        ORDER BY COALESCE(f.numero_sessao, 0) DESC, f.data DESC, f.criado_em DESC
    ''', (endo_id,))
    pending_followups = [
        f for f in followups or []
        if not f.get('assinatura_paciente_base64') or not f.get('professor_id')
    ]
    
    canais = query('SELECT * FROM endodontia_canais WHERE endodontia_id = %s', (endo_id,))
    linked_anamnesis = query(
        "SELECT * FROM anamnesis WHERE patient_id = %s ORDER BY id DESC LIMIT 1",
        (endo['patient_id'],),
        one=True,
    )
    anamnesis_risks = build_anamnesis_risk_summary(linked_anamnesis)
    diagnosis_context = build_diagnosis_context(
        endo.get('diagnostico_pulpar'),
        endo.get('diagnostico_apical'),
        endo.get('polpa_normal_justificativa'),
    )
    protocol_safety = build_protocol_safety_context(linked_anamnesis)
    channel_suggestions = suggest_typical_channels(endo.get('elemento_dentario'))
    session_context = build_session_context(endo, followups)
    endodontia_images = query(
        '''
        SELECT img.*,
               f.numero_sessao,
               f.data as sessao_data,
               COALESCE(u.full_name, u.username) as uploaded_by_name
        FROM endodontia_imagens img
        LEFT JOIN endodontia_followup f ON f.id = img.followup_id
        LEFT JOIN users u ON u.id = img.uploaded_by
        WHERE img.endodontia_id = %s
          AND COALESCE(img.active, TRUE) = TRUE
        ORDER BY COALESCE(img.taken_at, img.created_at) DESC, img.id DESC
        ''',
        (endo_id,),
    )
    proservations = query(
        '''
        SELECT pr.*,
               COALESCE(u.full_name, u.username) as restaurador_nome
        FROM endodontia_proservacao pr
        LEFT JOIN users u ON u.id = pr.restauracao_cd_id
        WHERE pr.endodontia_id = %s
        ORDER BY pr.data_prevista ASC, pr.id ASC
        ''',
        (endo_id,),
    )
    budget_items = query(
        '''
        SELECT *
        FROM endodontia_orcamento_items
        WHERE endodontia_id = %s
        ORDER BY id ASC
        ''',
        (endo_id,),
    ) or []
    
    return render_template('endodontia/followup.html', 
                           endo=endo, 
                           followups=followups,
                           pending_followups=pending_followups,
                           canais=canais,
                           endodontia_images=[_decorate_endo_image(row) for row in (endodontia_images or [])],
                           proservations=proservations or [],
                           budget_items=budget_items,
                           budget_summary=build_budget_summary(budget_items),
                           linked_anamnesis=linked_anamnesis,
                           anamnesis_risks=anamnesis_risks,
                           diagnosis_context=diagnosis_context,
                           protocol_safety=protocol_safety,
                           channel_suggestions=channel_suggestions,
                           session_context=session_context,
                           endodontia_options=ENDODONTIA_FORM_OPTIONS,
                           endodontia_image_category_options=get_endodontia_image_category_options(),
                           visual_comparison_options=get_comparison_label_options(),
                           selected_exacerbating_factors=parse_json_list(endo.get('fatores_exacerbantes')),
                           selected_relief_factors=parse_json_list(endo.get('fatores_alivio')),
                           current_date=datetime.now().strftime('%Y-%m-%d'),
                           today_date=datetime.now().date())


@endodontia_bp.route('/followup/<int:endo_id>/images/upload', methods=['POST'])
@login_required
def upload_image(endo_id):
    endo = _get_endodontia_case(endo_id)
    if _case_unavailable(endo):
        flash('Acompanhamento endodôntico indisponível para envio de imagem.', 'danger')
        return redirect(url_for('patients.list_patients'))

    file = request.files.get('imagem')
    if not file or not file.filename:
        flash('Selecione uma imagem endodôntica para enviar.', 'danger')
        return redirect(url_for('endodontia.followup', endo_id=endo_id))

    original_filename = secure_filename(file.filename)
    ext = os.path.splitext(original_filename)[1].lower()
    if ext not in ENDODONTIA_IMAGE_ALLOWED_EXTENSIONS:
        flash('Formato inválido. Use JPG, PNG, WEBP, TIFF ou DICOM.', 'danger')
        return redirect(url_for('endodontia.followup', endo_id=endo_id))

    metadata = build_endodontia_image_metadata(request.form)
    if not metadata['caption']:
        flash('A legenda da imagem endodôntica é obrigatória.', 'danger')
        return redirect(url_for('endodontia.followup', endo_id=endo_id))

    followup_id = _as_int_or_none(request.form.get('followup_id'))
    if followup_id:
        followup = query(
            'SELECT id FROM endodontia_followup WHERE id = %s AND endodontia_id = %s',
            (followup_id, endo_id),
            one=True,
        )
        if not followup:
            flash('Sessão selecionada não pertence a este acompanhamento.', 'danger')
            return redirect(url_for('endodontia.followup', endo_id=endo_id))

    # GDrive upload
    service = get_drive_service()
    folder_info = ensure_patient_drive_folder(endo['patient_id'], service)
    folder_id = folder_info['id']
    
    comparison_group = metadata['comparison_group'] or f"Endodontia dente {endo['elemento_dentario']}"
    file_format = ext.lstrip('.')
    if file_format == 'dcm':
        file_format = 'dicom'

    try:
        drive_file = upload_file_in_memory(
            service=service,
            file_stream=file.stream,
            filename=original_filename or f"endodontia{ext}",
            mime_type=file.mimetype,
            parent_id=folder_id
        )
        file_path = f"gdrive://{drive_file['id']}"
        
        image_id = execute(
            '''
            INSERT INTO endodontia_imagens (
                patient_id, endodontia_id, followup_id, filename, file_path,
                visual_category, caption, clinical_context, comparison_label,
                comparison_group, canal, equipamento, formato, taken_at, uploaded_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULLIF(%s, '')::timestamp, %s)
            RETURNING id
            ''',
            (
                endo['patient_id'],
                endo_id,
                followup_id,
                original_filename or f"endodontia{ext}",
                file_path,
                metadata['visual_category'],
                metadata['caption'],
                metadata['clinical_context'],
                metadata['comparison_label'],
                comparison_group,
                metadata['canal'],
                metadata['equipamento'],
                file_format,
                metadata['taken_at'] or '',
                current_user.id,
            ),
        )
        audit_log(
            action='endodontia_image_uploaded',
            module='endodontia',
            entity_type='endodontia_imagens',
            entity_id=image_id,
            patient_id=endo['patient_id'],
            details={
                'endodontia_id': endo_id,
                'elemento_dentario': endo['elemento_dentario'],
                'followup_id': followup_id,
                'visual_category': metadata['visual_category'],
                'canal': metadata['canal'],
                'filename': original_filename,
                'formato': file_format,
            },
        )
        flash('Imagem endodôntica enviada e vinculada à Biblioteca Visual.', 'success')
    except Exception as exc:
        audit_log(
            action='endodontia_image_upload_failed',
            module='endodontia',
            entity_type='endodontia',
            entity_id=endo_id,
            patient_id=endo['patient_id'],
            status='failed',
            details={'error': str(exc), 'filename': original_filename},
        )
        flash(f'Erro ao enviar imagem endodôntica: {str(exc)}', 'danger')

    return redirect(url_for('endodontia.followup', endo_id=endo_id))


@endodontia_bp.route('/image/<int:image_id>')
@login_required
@permission_required('patients:view')
def serve_image(image_id):
    image = query(
        '''
        SELECT img.*, e.patient_id, e.elemento_dentario
        FROM endodontia_imagens img
        JOIN endodontia e ON e.id = img.endodontia_id
        WHERE img.id = %s
          AND COALESCE(img.active, TRUE) = TRUE
          AND e.cancelado_em IS NULL
          AND COALESCE(e.status, 'Ativo') != 'Cancelado'
        ''',
        (image_id,),
        one=True,
    )
    if not image:
        return 'Arquivo não encontrado', 404

    audit_log(
        action='visual_media_file_viewed',
        module='visual_media',
        entity_type='endodontia_imagens',
        entity_id=image_id,
        patient_id=image['patient_id'],
        details={
            'source': 'endodontia_image',
            'filename': image.get('filename'),
            'caption': image.get('caption'),
            'elemento_dentario': image.get('elemento_dentario'),
        },
    )
    
    if str(image['file_path']).startswith('gdrive://'):
        gdrive_id = str(image['file_path']).replace('gdrive://', '')
        service = get_drive_service()
        try:
            file_bytes = download_file_in_memory(service, gdrive_id)
            mime_type, _ = mimetypes.guess_type(image['filename'])
            return Response(file_bytes, mimetype=mime_type or 'application/octet-stream')
        except Exception as e:
            return f"Erro ao baixar arquivo do Drive: {str(e)}", 500
    else:
        if not os.path.exists(image['file_path']):
            return "Arquivo local não encontrado", 404
        return sensitive_file_response(image['file_path'])


@endodontia_bp.route('/proservation/<int:proservation_id>/evaluate', methods=['POST'])
@login_required
def evaluate_proservation(proservation_id):
    proservation = query(
        '''
        SELECT pr.*, e.patient_id, e.elemento_dentario, e.status, e.cancelado_em
        FROM endodontia_proservacao pr
        JOIN endodontia e ON e.id = pr.endodontia_id
        WHERE pr.id = %s
        ''',
        (proservation_id,),
        one=True,
    )
    if not proservation:
        flash('Retorno de proservação não encontrado.', 'danger')
        return redirect(url_for('patients.list_patients'))

    endo = _get_endodontia_case(proservation['endodontia_id'])
    if _case_unavailable(endo):
        flash('Acompanhamento endodôntico indisponível para proservação.', 'danger')
        return redirect(url_for('patients.list_patients'))

    try:
        payload = build_proservation_evaluation_payload(request.form)
    except ValueError as exc:
        flash(str(exc), 'danger')
        return redirect(url_for('endodontia.followup', endo_id=proservation['endodontia_id']))

    treatment_status = None
    if payload['resultado_strindberg']:
        treatment_status = 'retratamento_necessario' if payload['resultado_strindberg'] == 'insucesso' else 'concluido'
    try:
        execute(
            '''
            UPDATE endodontia_proservacao
            SET status = %s,
                data_realizada = NULLIF(%s, '')::date,
                dente_funcao_mastigatoria = %s,
                ausencia_dor_percussao = %s,
                ausencia_dor_palpacao_apical = %s,
                ausencia_edema_mucosa = %s,
                ausencia_fistula = %s,
                clinica_observacoes = %s,
                espaco_periodontal_normal = %s,
                lamina_dura_integra = %s,
                ausencia_lesao_radiolucida = %s,
                reducao_lesao_preexistente = %s,
                radiografica_observacoes = %s,
                criterio_negativo_instavel = %s,
                resultado_strindberg = %s,
                resultado_observacoes = %s,
                restauracao_tipo = %s,
                restauracao_selamento_adequado = %s,
                restauracao_data = NULLIF(%s, '')::date,
                restauracao_cd_id = %s,
                restauracao_observacoes = %s,
                atualizado_em = NOW()
            WHERE id = %s
            ''',
            (
                payload['status'],
                payload['data_realizada'] or '',
                payload['dente_funcao_mastigatoria'],
                payload['ausencia_dor_percussao'],
                payload['ausencia_dor_palpacao_apical'],
                payload['ausencia_edema_mucosa'],
                payload['ausencia_fistula'],
                payload['clinica_observacoes'],
                payload['espaco_periodontal_normal'],
                payload['lamina_dura_integra'],
                payload['ausencia_lesao_radiolucida'],
                payload['reducao_lesao_preexistente'],
                payload['radiografica_observacoes'],
                payload['criterio_negativo_instavel'],
                payload['resultado_strindberg'],
                payload['resultado_observacoes'],
                payload['restauracao_tipo'],
                payload['restauracao_selamento_adequado'],
                payload['restauracao_data'] or '',
                current_user.id,
                payload['restauracao_observacoes'],
                proservation_id,
            ),
        )
        if treatment_status:
            execute(
                '''
                UPDATE endodontia
                SET status_tratamento = %s,
                    status = CASE WHEN %s = 'concluido' THEN 'Concluído' ELSE status END,
                    updated_at = NOW()
                WHERE id = %s
                ''',
                (treatment_status, treatment_status, proservation['endodontia_id']),
            )
        audit_log(
            action='endodontia_proservation_evaluated',
            module='endodontia',
            entity_type='endodontia_proservacao',
            entity_id=proservation_id,
            patient_id=proservation['patient_id'],
            details={
                'endodontia_id': proservation['endodontia_id'],
                'elemento_dentario': proservation['elemento_dentario'],
                'tipo_retorno': proservation['tipo_retorno'],
                'resultado_strindberg': payload['resultado_strindberg'],
                'status_tratamento': treatment_status,
                'restauracao_tipo': payload['restauracao_tipo'],
            },
        )
        flash('Proservação registrada com critérios de Strindberg.', 'success')
    except Exception as exc:
        audit_log(
            action='endodontia_proservation_evaluate_failed',
            module='endodontia',
            entity_type='endodontia_proservacao',
            entity_id=proservation_id,
            patient_id=proservation['patient_id'],
            status='failed',
            details={'error': str(exc)},
        )
        flash(f'Erro ao registrar proservação: {str(exc)}', 'danger')

    return redirect(url_for('endodontia.followup', endo_id=proservation['endodontia_id']))


@endodontia_bp.route('/followup/<int:endo_id>/budget/generate', methods=['POST'])
@login_required
def generate_budget(endo_id):
    endo = _get_endodontia_case(endo_id)
    if _case_unavailable(endo):
        flash('Acompanhamento endodôntico indisponível para orçamento.', 'danger')
        return redirect(url_for('patients.list_patients'))

    diagnosis_context = build_diagnosis_context(
        endo.get('diagnostico_pulpar'),
        endo.get('diagnostico_apical'),
        endo.get('polpa_normal_justificativa'),
    )
    if endo.get('diagnostico_pulpar') == 'polpa_normal' or not diagnosis_context['can_advance']:
        audit_log(
            action='endodontia_budget_generation_denied',
            module='endodontia',
            entity_type='endodontia',
            entity_id=endo_id,
            patient_id=endo['patient_id'],
            status='denied',
            details={
                'elemento_dentario': endo['elemento_dentario'],
                'diagnostico_pulpar': endo.get('diagnostico_pulpar'),
                'diagnostico_apical': endo.get('diagnostico_apical'),
            },
        )
        flash('Diagnóstico atual não libera orçamento endodôntico para tratamento radical.', 'danger')
        return redirect(url_for('endodontia.followup', endo_id=endo_id))

    canais = query('SELECT * FROM endodontia_canais WHERE endodontia_id = %s ORDER BY id ASC', (endo_id,)) or []
    try:
        budget = build_endodontia_budget_items(endo, canais, _get_endodontia_cost_references())
    except ValueError as exc:
        flash(str(exc), 'danger')
        return redirect(url_for('endodontia.followup', endo_id=endo_id))

    try:
        execute('DELETE FROM endodontia_orcamento_items WHERE endodontia_id = %s', (endo_id,))
        for item in budget['items']:
            execute(
                '''
                INSERT INTO endodontia_orcamento_items (
                    patient_id, endodontia_id, dente_numero, canal_id,
                    procedimento, codigo_tuss, codigo_sigtap, sigtap_name,
                    codigo_cid10, valor_unitario, valor_publico_unitario,
                    economia_estimada_unitaria, sessoes_previstas,
                    complexidade, grupo_dentario, multiplicador,
                    observacoes, status, created_by
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'gerado', %s
                )
                ''',
                (
                    endo['patient_id'],
                    endo_id,
                    item['dente_numero'],
                    item['canal_id'],
                    item['procedimento'],
                    item['codigo_tuss'],
                    item['codigo_sigtap'],
                    item['sigtap_name'],
                    item['codigo_cid10'],
                    item['valor_unitario'],
                    item['valor_publico_unitario'],
                    item['economia_estimada_unitaria'],
                    item['sessoes_previstas'],
                    item['complexidade'],
                    item['grupo_dentario'],
                    item['multiplicador'],
                    item['observacoes'],
                    current_user.id,
                ),
            )
        summary = build_budget_summary(budget['items'])
        audit_log(
            action='endodontia_budget_generated',
            module='endodontia',
            entity_type='endodontia',
            entity_id=endo_id,
            patient_id=endo['patient_id'],
            details={
                'elemento_dentario': endo['elemento_dentario'],
                'workflow': budget['workflow'],
                'channel_count': budget['channel_count'],
                'reference_code': budget['reference_code'],
                'total_private': str(summary['total_private']),
                'total_public': str(summary['total_public']),
                'total_savings': str(summary['total_savings']),
            },
        )
        flash('Orçamento endodôntico gerado canal a canal.', 'success')
    except Exception as exc:
        audit_log(
            action='endodontia_budget_generation_failed',
            module='endodontia',
            entity_type='endodontia',
            entity_id=endo_id,
            patient_id=endo['patient_id'],
            status='failed',
            details={'error': str(exc)},
        )
        flash(f'Erro ao gerar orçamento endodôntico: {str(exc)}', 'danger')

    return redirect(url_for('endodontia.followup', endo_id=endo_id))

@endodontia_bp.route('/followup/save_details/<int:endo_id>', methods=['POST'])
@login_required
def save_case_details(endo_id):
    endo = _get_endodontia_case(endo_id)
    if _case_unavailable(endo):
        flash('Acompanhamento endodôntico indisponível para edição.', 'danger')
        return redirect(url_for('patients.list_patients'))

    try:
        payload = build_case_details_payload(request.form)
        channel_result = build_channel_payloads(request.form, payload.get('diagnostico_pulpar'))
    except ValueError as exc:
        flash(str(exc), 'danger')
        return redirect(url_for('endodontia.followup', endo_id=endo_id))
    
    try:
        execute('''
            UPDATE endodontia 
            SET coroa = %s, canais_radiculares = %s, regiao_apical = %s, demais = %s, 
                diagnostico = %s, grampo = %s, finalidade_protetica = %s,
                queixa_inicio = %s, queixa_duracao = %s, queixa_intensidade = %s,
                queixa_localizacao = %s, fatores_exacerbantes = %s, fatores_alivio = %s,
                queixa_descricao = %s, linfadenopatia_cervical = %s,
                linfadenopatia_submandibular = %s, assimetria_facial = %s,
                edema_extraoral = %s, exame_extraoral_observacoes = %s,
                edema_submucoso = %s, fistula_trajeto = %s, fistula_localizacao = %s,
                carie_profunda = %s, restauracao_inadequada = %s, faceta_desgaste = %s,
                exame_intraoral_observacoes = %s, mobilidade = %s,
                sondagem_mesial_mm = %s, sondagem_distal_mm = %s,
                sondagem_vestibular_mm = %s, sondagem_lingual_palatino_mm = %s,
                tipo_lesao = %s, diagnostico_pulpar = %s,
                diagnostico_apical = %s, cid10_sugerido = %s,
                workflow_tipo = %s, polpa_normal_justificativa = %s,
                diagnostico_estruturado_status = %s,
                lesao_periapical_extensa = %s,
                updated_at = NOW()
            WHERE id = %s
        ''', (
            payload['coroa'], payload['canais_radiculares'], payload['regiao_apical'], payload['demais'],
            payload['diagnostico'], payload['grampo'], payload['finalidade_protetica'],
            payload['queixa_inicio'], payload['queixa_duracao'], payload['queixa_intensidade'],
            payload['queixa_localizacao'], payload['fatores_exacerbantes'], payload['fatores_alivio'],
            payload['queixa_descricao'], payload['linfadenopatia_cervical'],
            payload['linfadenopatia_submandibular'], payload['assimetria_facial'],
            payload['edema_extraoral'], payload['exame_extraoral_observacoes'],
            payload['edema_submucoso'], payload['fistula_trajeto'], payload['fistula_localizacao'],
            payload['carie_profunda'], payload['restauracao_inadequada'], payload['faceta_desgaste'],
            payload['exame_intraoral_observacoes'], payload['mobilidade'],
            payload['sondagem_mesial_mm'], payload['sondagem_distal_mm'],
            payload['sondagem_vestibular_mm'], payload['sondagem_lingual_palatino_mm'],
            payload['tipo_lesao'], payload['diagnostico_pulpar'],
            payload['diagnostico_apical'], payload['cid10_sugerido'],
            payload['workflow_tipo'], payload['polpa_normal_justificativa'],
            payload['diagnostico_estruturado_status'],
            payload['lesao_periapical_extensa'],
            endo_id,
        ))
        
        execute('DELETE FROM endodontia_canais WHERE endodontia_id = %s', (endo_id,))

        for channel in channel_result['channels']:
            execute('''
                INSERT INTO endodontia_canais (
                    endodontia_id, canal, cad, referencia, ct,
                    ponto_referencia_coronario, cri_mm, cai_mm, crd_mm,
                    crt_sugerido_mm, crt_final_mm, crt_override_justificativa,
                    localizador_apical_usado, modelo_localizador, leitura_localizador,
                    confirmacao_eletronica, lima_inicial, lima_final, cone, selamento
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
            ''', (
                endo_id,
                channel['canal'], channel['cad'], channel['referencia'], channel['ct'],
                channel['ponto_referencia_coronario'], channel['cri_mm'], channel['cai_mm'],
                channel['crd_mm'], channel['crt_sugerido_mm'], channel['crt_final_mm'],
                channel['crt_override_justificativa'], channel['localizador_apical_usado'],
                channel['modelo_localizador'], channel['leitura_localizador'],
                channel['confirmacao_eletronica'], channel['lima_inicial'], channel['lima_final'],
                channel['cone'], channel['selamento'],
            ))

        if channel_result['overrides']:
            audit_log(
                action='endodontia_odontometry_override',
                module='endodontia',
                entity_type='endodontia',
                entity_id=endo_id,
                patient_id=endo['patient_id'],
                details={
                    'elemento_dentario': endo['elemento_dentario'],
                    'overrides': channel_result['overrides'],
                    'profissional_id': current_user.id,
                },
            )

        audit_log(
            action='endodontia_case_details_updated',
            module='endodontia',
            entity_type='endodontia',
            entity_id=endo_id,
            patient_id=endo['patient_id'],
            details={
                'elemento_dentario': endo['elemento_dentario'],
                'diagnostico_livre': payload['diagnostico'],
                'diagnostico_pulpar': payload['diagnostico_pulpar'],
                'diagnostico_apical': payload['diagnostico_apical'],
                'cid10_sugerido': payload['cid10_sugerido'],
                'workflow_tipo': payload['workflow_tipo'],
                'diagnostico_estruturado_status': payload['diagnostico_estruturado_status'],
                'queixa_intensidade': payload['queixa_intensidade'],
                'tipo_lesao': payload['tipo_lesao'],
                'lesao_periapical_extensa': payload['lesao_periapical_extensa'],
                'canais_registrados': len(channel_result['channels']),
                'odontometria_overrides': len(channel_result['overrides']),
            },
        )
        flash('Informações técnicas salvas com sucesso.', 'success')
    except Exception as e:
        audit_log(
            action='endodontia_case_details_update_failed',
            module='endodontia',
            entity_type='endodontia',
            entity_id=endo_id,
            patient_id=endo['patient_id'],
            status='failed',
            details={'error': str(e)},
        )
        flash(f'Erro ao salvar informações técnicas: {str(e)}', 'danger')
        
    return redirect(url_for('endodontia.followup', endo_id=endo_id))

@endodontia_bp.route('/followup/add/<int:endo_id>', methods=['POST'])
@login_required
def add_followup(endo_id):
    endo = _get_endodontia_case(endo_id)
    if _case_unavailable(endo):
        flash('Acompanhamento endodôntico indisponível para nova evolução.', 'danger')
        return redirect(url_for('patients.list_patients'))

    diagnosis_context = build_diagnosis_context(
        endo.get('diagnostico_pulpar'),
        endo.get('diagnostico_apical'),
        endo.get('polpa_normal_justificativa'),
    )
    if not diagnosis_context['can_advance']:
        reasons = ', '.join(diagnosis_context['missing'] + diagnosis_context['blockers'])
        audit_log(
            action='endodontia_followup_blocked_by_diagnosis',
            module='endodontia',
            entity_type='endodontia',
            entity_id=endo_id,
            patient_id=endo['patient_id'],
            status='denied',
            details={
                'elemento_dentario': endo['elemento_dentario'],
                'reasons': reasons,
            },
        )
        flash(f'Defina o diagnóstico pulpar e apical antes de avançar. {reasons}', 'danger')
        return redirect(url_for('endodontia.followup', endo_id=endo_id))

    last_session = query(
        'SELECT MAX(numero_sessao) AS max_numero FROM endodontia_followup WHERE endodontia_id = %s',
        (endo_id,),
        one=True,
    )
    next_session_number = (last_session or {}).get('max_numero') or 0
    linked_anamnesis = query(
        "SELECT * FROM anamnesis WHERE patient_id = %s ORDER BY id DESC LIMIT 1",
        (endo['patient_id'],),
        one=True,
    )

    try:
        payload = build_session_payload(request.form, next_session_number + 1, anamnesis=linked_anamnesis)
    except ValueError as exc:
        flash(str(exc), 'danger')
        return redirect(url_for('endodontia.followup', endo_id=endo_id))
        
    try:
        followup_id = execute('''
            INSERT INTO endodontia_followup (
                endodontia_id, data, evolucao, status,
                numero_sessao, etapa_realizada, status_sessao,
                proxima_sessao_prevista, janela_retorno_dias, observacao_clinica,
                lai_mm, tecnica_instrumentacao, sistema_instrumentacao, liga_instrumento,
                protocolo_observacoes, solucao_irrigadora, edta_usado,
                tempo_irrigacao_min, agitacao_irrigadora, volume_irrigacao_ml,
                irrigacao_observacoes, medicacao_intracanal, medicacao_intracanal_outra,
                medicacao_veiculo, medicacao_quantidade, selamento_provisorio,
                selamento_provisorio_outro, cone_principal_material, cone_principal_calibre,
                cone_principal_conicidade, prova_cone, tug_back, crt_confirmado_mm,
                cimento_obturador, cimento_classe, cimento_classe_outro, cimento_lote,
                cimento_validade, tecnica_obturacao, tecnica_obturacao_outra,
                radiografia_final_aprovada, radiografia_final_gaps, radiografia_final_voids,
                controle_qualidade_observacoes, restauracao_definitiva_registrada,
                restauracao_definitiva_data, restauracao_definitiva_material,
                selamento_coronario_adequado, restauracao_observacoes
            )
            VALUES (
                %s, %s, %s, 'Pendente',
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
            RETURNING id
        ''', (
            endo_id,
            payload['data'],
            payload['evolucao'],
            payload['numero_sessao'],
            payload['etapa_realizada'],
            payload['status_sessao'],
            payload['proxima_sessao_prevista'],
            payload['janela_retorno_dias'],
            payload['observacao_clinica'],
            payload.get('lai_mm'),
            payload.get('tecnica_instrumentacao'),
            payload.get('sistema_instrumentacao'),
            payload.get('liga_instrumento'),
            payload.get('protocolo_observacoes'),
            payload.get('solucao_irrigadora'),
            payload.get('edta_usado', False),
            payload.get('tempo_irrigacao_min'),
            payload.get('agitacao_irrigadora'),
            payload.get('volume_irrigacao_ml'),
            payload.get('irrigacao_observacoes'),
            payload.get('medicacao_intracanal'),
            payload.get('medicacao_intracanal_outra'),
            payload.get('medicacao_veiculo'),
            payload.get('medicacao_quantidade'),
            payload.get('selamento_provisorio'),
            payload.get('selamento_provisorio_outro'),
            payload.get('cone_principal_material'),
            payload.get('cone_principal_calibre'),
            payload.get('cone_principal_conicidade'),
            payload.get('prova_cone', False),
            payload.get('tug_back', False),
            payload.get('crt_confirmado_mm'),
            payload.get('cimento_obturador'),
            payload.get('cimento_classe'),
            payload.get('cimento_classe_outro'),
            payload.get('cimento_lote'),
            payload.get('cimento_validade'),
            payload.get('tecnica_obturacao'),
            payload.get('tecnica_obturacao_outra'),
            payload.get('radiografia_final_aprovada', False),
            payload.get('radiografia_final_gaps', False),
            payload.get('radiografia_final_voids', False),
            payload.get('controle_qualidade_observacoes'),
            payload.get('restauracao_definitiva_registrada', False),
            payload.get('restauracao_definitiva_data'),
            payload.get('restauracao_definitiva_material'),
            payload.get('selamento_coronario_adequado', False),
            payload.get('restauracao_observacoes'),
        ))
        execute('''
            UPDATE endodontia
            SET status_tratamento = %s,
                sessoes_planejadas = COALESCE(%s, sessoes_planejadas),
                proxima_sessao_prevista = %s,
                janela_retorno_dias = %s,
                restauracao_definitiva_registrada = CASE WHEN %s THEN TRUE ELSE restauracao_definitiva_registrada END,
                restauracao_definitiva_data = COALESCE(%s, restauracao_definitiva_data),
                restauracao_definitiva_material = COALESCE(%s, restauracao_definitiva_material),
                selamento_coronario_adequado = CASE WHEN %s THEN TRUE ELSE selamento_coronario_adequado END,
                restauracao_observacoes = COALESCE(%s, restauracao_observacoes),
                status = CASE WHEN %s = 'concluido' THEN 'Concluído' ELSE status END,
                updated_at = NOW()
            WHERE id = %s
        ''', (
            payload['status_tratamento'],
            payload['sessoes_planejadas'],
            payload['proxima_sessao_prevista'],
            payload['janela_retorno_dias'],
            payload.get('restauracao_definitiva_registrada', False),
            payload.get('restauracao_definitiva_data'),
            payload.get('restauracao_definitiva_material'),
            payload.get('selamento_coronario_adequado', False),
            payload.get('restauracao_observacoes'),
            payload['status_tratamento'],
            endo_id,
        ))
        proservation_schedule = _create_proservation_schedule(endo, followup_id, payload)
        if proservation_schedule:
            audit_log(
                action='endodontia_proservation_schedule_created',
                module='endodontia',
                entity_type='endodontia',
                entity_id=endo_id,
                patient_id=endo['patient_id'],
                details={
                    'followup_id': followup_id,
                    'elemento_dentario': endo['elemento_dentario'],
                    'retornos': proservation_schedule,
                },
            )
        audit_log(
            action='endodontia_session_created',
            module='endodontia',
            entity_type='endodontia_followup',
            entity_id=followup_id,
            patient_id=endo['patient_id'],
            details={
                'endodontia_id': endo_id,
                'elemento_dentario': endo['elemento_dentario'],
                'numero_sessao': payload['numero_sessao'],
                'data': payload['data'],
                'etapa_realizada': payload['etapa_realizada'],
                'status_sessao': payload['status_sessao'],
                'status_tratamento': payload['status_tratamento'],
                'proxima_sessao_prevista': payload['proxima_sessao_prevista'],
                'solucao_irrigadora': payload.get('solucao_irrigadora'),
                'medicacao_intracanal': payload.get('medicacao_intracanal'),
                'selamento_provisorio': payload.get('selamento_provisorio'),
                'tecnica_obturacao': payload.get('tecnica_obturacao'),
                'radiografia_final_aprovada': payload.get('radiografia_final_aprovada'),
                'restauracao_definitiva_registrada': payload.get('restauracao_definitiva_registrada'),
                'proservacoes_criadas': len(proservation_schedule),
            },
        )
        flash('Sessão endodôntica registrada com sucesso.', 'success')
    except Exception as e:
        audit_log(
            action='endodontia_session_create_failed',
            module='endodontia',
            entity_type='endodontia',
            entity_id=endo_id,
            patient_id=endo['patient_id'],
            status='failed',
            details={'error': str(e)},
        )
        flash(f'Erro ao registrar evolução: {str(e)}', 'danger')
        
    return redirect(url_for('endodontia.followup', endo_id=endo_id))

@endodontia_bp.route('/followup/sign_patient/<int:followup_id>', methods=['POST'])
@login_required
def sign_patient(followup_id):
    endo_id = request.form.get('endo_id')
    assinatura = request.form.get('assinatura_base64')
    endo = _get_endodontia_case(endo_id)
    if _case_unavailable(endo):
        flash('Acompanhamento endodôntico indisponível para assinatura.', 'danger')
        return redirect(url_for('patients.list_patients'))
    
    if not assinatura:
        flash('Assinatura do paciente não capturada.', 'danger')
        return redirect(url_for('endodontia.followup', endo_id=endo_id))
        
    try:
        followup = query("SELECT * FROM endodontia_followup WHERE id = %s", (followup_id,), one=True)
        patient = query("SELECT id, nome, cpf, rg FROM patients WHERE id = %s", (endo['patient_id'],), one=True)
        evidence = None
        if followup and patient:
            payload = build_generic_signature_payload(
                'endodontia_followup_patient_signature',
                patient,
                SIGNATURE_MODE_CANVAS,
                document_data={
                    'endodontia_id': endo_id,
                    'followup_id': followup_id,
                    'elemento_dentario': endo['elemento_dentario'],
                    'numero_sessao': followup.get('numero_sessao'),
                    'etapa_realizada': followup.get('etapa_realizada'),
                    'evolucao': followup.get('evolucao'),
                },
                signature_capture=assinatura,
                signer=current_user,
            )
            evidence = register_signature_event(
                document_type='endodontia_followup_patient_signature',
                document_id=followup_id,
                patient=patient,
                signature_mode=SIGNATURE_MODE_CANVAS,
                payload=payload,
                signed_by_user=current_user,
                auth_method='patient_canvas_session',
                metadata={'endodontia_id': endo_id, 'followup_id': followup_id},
            )
        execute(
            """
            UPDATE endodontia_followup
            SET assinatura_paciente_base64 = %s,
                assinatura_modo = %s,
                assinatura_event_id = %s,
                assinatura_document_hash = %s,
                assinatura_auth_method = %s,
                assinatura_source_ip = %s,
                assinatura_user_agent = %s
            WHERE id = %s
            """,
            (
                assinatura,
                SIGNATURE_MODE_CANVAS,
                evidence['event_id'] if evidence else None,
                evidence['document_hash'] if evidence else None,
                'patient_canvas_session',
                evidence['source_ip'] if evidence else None,
                evidence['user_agent'] if evidence else None,
                followup_id,
            ),
        )
        audit_log(
            action='endodontia_followup_patient_signed',
            module='endodontia',
            entity_type='endodontia_followup',
            entity_id=followup_id,
            patient_id=endo['patient_id'],
            details={
                'endodontia_id': endo_id,
                'elemento_dentario': endo['elemento_dentario'],
                'signature_event_id': evidence['event_id'] if evidence else None,
                'document_hash': evidence['document_hash'] if evidence else None,
            },
        )
        flash('Assinatura do paciente salva com sucesso.', 'success')
    except Exception as e:
        audit_log(
            action='endodontia_followup_patient_sign_failed',
            module='endodontia',
            entity_type='endodontia_followup',
            entity_id=followup_id,
            patient_id=endo['patient_id'],
            status='failed',
            details={'error': str(e)},
        )
        flash(f'Erro ao assinar: {str(e)}', 'danger')
        
    return redirect(url_for('endodontia.followup', endo_id=endo_id))

@endodontia_bp.route('/followup/sign_professor/<int:followup_id>', methods=['POST'])
@login_required
def sign_professor(followup_id):
    endo_id = request.form.get('endo_id')
    username = request.form.get('prof_username')
    password = request.form.get('prof_password')
    endo = _get_endodontia_case(endo_id)
    if _case_unavailable(endo):
        flash('Acompanhamento endodôntico indisponível para validação.', 'danger')
        return redirect(url_for('patients.list_patients'))
    
    prof = query("SELECT id, password, role FROM users WHERE username = %s", (username,), one=True)
    if not prof or not check_password_hash(prof['password'], password) or not can_sign_clinical_document(prof['role']):
        flash('Credenciais inválidas ou usuário sem permissão para validar.', 'danger')
        return redirect(url_for('endodontia.followup', endo_id=endo_id))
        
    try:
        execute('''
            UPDATE endodontia_followup 
            SET professor_id = %s, status = 'Concluído' 
            WHERE id = %s
        ''', (prof['id'], followup_id))
        audit_log(
            action='endodontia_followup_validated',
            module='endodontia',
            entity_type='endodontia_followup',
            entity_id=followup_id,
            patient_id=endo['patient_id'],
            details={
                'endodontia_id': endo_id,
                'elemento_dentario': endo['elemento_dentario'],
                'validated_by': prof['id'],
            },
        )
        flash('Evolução validada pelo dentista responsável.', 'success')
    except Exception as e:
        audit_log(
            action='endodontia_followup_validate_failed',
            module='endodontia',
            entity_type='endodontia_followup',
            entity_id=followup_id,
            patient_id=endo['patient_id'],
            status='failed',
            details={'error': str(e)},
        )
        flash(f'Erro ao validar: {str(e)}', 'danger')
        
    return redirect(url_for('endodontia.followup', endo_id=endo_id))

@endodontia_bp.route('/delete/<int:endo_id>', methods=['POST'])
@login_required
def delete_element(endo_id):
    patient_id = request.form.get('patient_id')
    username = request.form.get('prof_username')
    password = request.form.get('prof_password')
    reason = (request.form.get('motivo_cancelamento') or '').strip()
    
    endo = _get_endodontia_case(endo_id)
    if not endo:
        flash('Acompanhamento endodôntico não encontrado.', 'danger')
        return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-endodontia')

    prof = query("SELECT id, password, role FROM users WHERE username = %s", (username,), one=True)
    if not prof or not check_password_hash(prof['password'], password) or not can_sign_clinical_document(prof['role']):
        audit_log(
            action='endodontia_case_cancel_denied',
            module='endodontia',
            entity_type='endodontia',
            entity_id=endo_id,
            patient_id=patient_id,
            status='denied',
            details={'elemento_dentario': endo['elemento_dentario']},
        )
        flash('Credenciais inválidas ou usuário sem permissão clínica para cancelar o acompanhamento.', 'danger')
        return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-endodontia')

    if not reason:
        flash('Informe o motivo do cancelamento para manter a rastreabilidade clínica.', 'danger')
        return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-endodontia')
        
    try:
        execute('''
            UPDATE endodontia
            SET status = 'Cancelado',
                cancelado_em = NOW(),
                cancelado_por = %s,
                motivo_cancelamento = %s,
                updated_at = NOW()
            WHERE id = %s
        ''', (prof['id'], reason, endo_id))
        audit_log(
            action='endodontia_case_cancelled',
            module='endodontia',
            entity_type='endodontia',
            entity_id=endo_id,
            patient_id=patient_id,
            details={
                'elemento_dentario': endo['elemento_dentario'],
                'validated_by': prof['id'],
                'reason': reason,
            },
        )
        flash('Acompanhamento endodôntico cancelado com rastreabilidade.', 'success')
    except Exception as e:
        audit_log(
            action='endodontia_case_cancel_failed',
            module='endodontia',
            entity_type='endodontia',
            entity_id=endo_id,
            patient_id=patient_id,
            status='failed',
            details={'error': str(e)},
        )
        flash(f'Erro ao cancelar: {str(e)}', 'danger')
        
    return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-endodontia')
