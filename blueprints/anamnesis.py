from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from database import execute, query
from services.signature_evidence_service import (
    ANAMNESIS_CLINICIAN_DECLARATION,
    SIGNATURE_MARKER_A_ROGO,
    SIGNATURE_MODE_A_ROGO,
    build_generic_signature_payload,
    json_dumps,
    register_signature_event,
    validate_a_rogo_signer,
)
from services.web_security_service import flash_internal_error

anamnesis_bp = Blueprint('anamnesis', __name__, url_prefix='/anamnesis')


ANAMNESIS_EDIT_POSTBACK_FIELDS = (
    'queixa_principal', 'historia_doenca_atual',
    'sofre_doenca', 'sofre_doenca_explica',
    'tratamento_medico', 'tratamento_medico_explica',
    'tomando_medicamento', 'tomando_medicamento_explica',
    'tem_alergia', 'tem_alergia_explica',
    'pressao_arterial', 'desmaios_convulsoes', 'tem_cancer',
    'radioterapia_quimioterapia', 'falta_ar',
    'fez_cirurgia', 'fez_cirurgia_explica',
    'sangramento_cortar', 'cicatrizacao',
    'foi_hospitalizado', 'foi_hospitalizado_explica',
    'alergia_medicamento_alimento', 'gestante', 'gestante_semanas',
    'problemas_saude_ja_teve', 'reacao_anestesia', 'reacao_anestesia_explica',
    'ultimo_tratamento_dentario', 'dor_dentes_gengiva', 'gengiva_sangra',
    'fio_dental', 'dores_estalos_maxilar', 'range_dentes',
    'antecedentes_familiares', 'causas_obitos_familiares',
    'fuma', 'fuma_quantidade', 'ingere_alcool', 'ingere_alcool_frequencia',
    'exercicios_fisicos', 'exercicios_fisicos_frequencia',
)


def _merge_anamnesis_postback(anamnesis, form_data):
    postback = dict(anamnesis)
    for field in ANAMNESIS_EDIT_POSTBACK_FIELDS:
        if field in form_data:
            postback[field] = form_data.get(field)
    return postback


def _signature_error_message(error):
    message = str(error)
    if 'Credenciais do CD inválidas' in message:
        return 'Usuário ou senha do clínico inválidos. Confira os dados e tente novamente.'
    if 'Informe usuário e senha' in message:
        return 'Informe usuário e senha do clínico responsável para confirmar a assinatura.'
    if 'sem permissão clínica' in message:
        return 'O usuário informado não tem permissão clínica para confirmar esta assinatura.'
    return message


def _prepare_anamnesis_signature(form_data):
    signer = validate_a_rogo_signer(
        form_data.get('clinico_username'),
        form_data.get('clinico_password'),
    )

    return {
        'assinatura': SIGNATURE_MARKER_A_ROGO,
        'signature_mode': SIGNATURE_MODE_A_ROGO,
        'signer': signer,
        'declaration_text': ANAMNESIS_CLINICIAN_DECLARATION,
        'auth_method': 'login_senha_clinico',
        'witnesses': [],
    }


def _record_anamnesis_signature(
    anamnesis_id,
    patient,
    form_data,
    signature_data,
    action='created',
):
    assinatura = signature_data['assinatura']
    signature_mode = signature_data['signature_mode']
    signer = signature_data['signer']
    declaration_text = signature_data['declaration_text']
    auth_method = signature_data['auth_method']
    witnesses = signature_data['witnesses']
    signer_id = signer['id'] if isinstance(signer, dict) else signer.id

    payload = build_generic_signature_payload(
        'anamnesis',
        patient,
        signature_mode,
        document_data={
            'anamnesis_id': anamnesis_id,
            'action': action,
            'queixa_principal': form_data.get('queixa_principal'),
            'historia_doenca_atual': form_data.get('historia_doenca_atual'),
            'tem_alergia': form_data.get('tem_alergia'),
            'tomando_medicamento': form_data.get('tomando_medicamento'),
        },
        signature_capture=None,
        witnesses=witnesses,
        signer=signer,
    )
    evidence = register_signature_event(
        document_type='anamnesis',
        document_id=anamnesis_id,
        patient=patient,
        signature_mode=signature_mode,
        payload=payload,
        signed_by_user=signer,
        auth_method=auth_method,
        declaration_text=declaration_text,
        witnesses=witnesses,
        metadata={'anamnesis_action': action},
    )
    execute(
        """
        UPDATE anamnesis
        SET assinatura_base64 = %s,
            assinatura_modo = %s,
            assinatura_event_id = %s,
            assinatura_document_hash = %s,
            assinatura_a_rogo_por = %s,
            assinatura_a_rogo_declaracao = %s,
            assinatura_a_rogo_testemunhas = %s::jsonb,
            assinatura_auth_method = %s,
            assinatura_source_ip = %s,
            assinatura_user_agent = %s
        WHERE id = %s
        """,
        (
            assinatura,
            signature_mode,
            evidence['event_id'],
            evidence['document_hash'],
            signer_id,
            declaration_text,
            json_dumps(witnesses),
            auth_method,
            evidence['source_ip'],
            evidence['user_agent'],
            anamnesis_id,
        ),
    )
    return evidence

@anamnesis_bp.route('/search')
@login_required
def search():
    q = request.args.get('q', '')
    patients = []
    if q:
        patients = query("""
            SELECT p.id, p.nome, p.cpf, MAX(a.id) as last_anamnesis_id 
            FROM patients p 
            LEFT JOIN anamnesis a ON p.id = a.patient_id 
            WHERE p.nome LIKE %s 
            GROUP BY p.id
        """, (f'%{q}%',))
    return render_template('anamnesis/search.html', patients=patients, query=q)

@anamnesis_bp.route('/form/<int:patient_id>', methods=['GET', 'POST'])
@login_required
def form(patient_id):
    patient = query("SELECT * FROM patients WHERE id = %s", (patient_id,), one=True)
    if not patient:
        flash('Paciente não encontrado.', 'danger')
        return redirect(url_for('anamnesis.search'))

    if request.method == 'POST':
        try:
            signature_data = _prepare_anamnesis_signature(request.form)
        except ValueError as exc:
            signature_error = _signature_error_message(exc)
            flash(signature_error, 'danger')
            from datetime import datetime
            return render_template(
                'anamnesis/form.html',
                patient=patient,
                now=datetime.now(),
                signature_error=signature_error,
            )

        # Coleta de dados seguindo o esquema do banco
        fields = [
            'patient_id', 'queixa_principal', 'historia_doenca_atual',
            'sofre_doenca', 'sofre_doenca_explica',
            'tratamento_medico', 'tratamento_medico_explica',
            'tomando_medicamento', 'tomando_medicamento_explica',
            'tem_alergia', 'tem_alergia_explica',
            'pressao_arterial', 'desmaios_convulsoes', 'tem_cancer',
            'radioterapia_quimioterapia', 'falta_ar',
            'fez_cirurgia', 'fez_cirurgia_explica',
            'sangramento_cortar', 'cicatrizacao',
            'foi_hospitalizado', 'foi_hospitalizado_explica',
            'alergia_medicamento_alimento', 'gestante', 'gestante_semanas',
            'problemas_saude_ja_teve', 'reacao_anestesia', 'reacao_anestesia_explica',
            'ultimo_tratamento_dentario', 'dor_dentes_gengiva', 'gengiva_sangra',
            'fio_dental', 'dores_estalos_maxilar', 'range_dentes',
            'antecedentes_familiares', 'causas_obitos_familiares',
            'fuma', 'fuma_quantidade', 'ingere_alcool', 'ingere_alcool_frequencia',
            'exercicios_fisicos', 'exercicios_fisicos_frequencia', 'assinatura_base64'
        ]
        
        values = [patient_id]
        for field in fields[1:]:
            if field == 'assinatura_base64':
                values.append(signature_data['assinatura'])
            else:
                values.append(request.form.get(field))
            
        try:
            placeholders = ', '.join(['%s'] * len(fields))
            columns = ', '.join(fields)
            anamnesis_id = execute(f'INSERT INTO anamnesis ({columns}) VALUES ({placeholders}) RETURNING id', values)
            _record_anamnesis_signature(
                anamnesis_id,
                patient,
                request.form,
                signature_data,
                action='created',
            )
            flash('Anamnese salva com sucesso!', 'success')
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            flash_internal_error('Falha ao salvar anamnese')

    from datetime import datetime
    return render_template('anamnesis/form.html', patient=patient, now=datetime.now())
@anamnesis_bp.route('/list-completed')
@login_required
def list_completed():
    q = request.args.get('q', '')
    if q:
        # Busca anamneses por nome do paciente ou CPF
        results = query("""
            SELECT a.id, p.nome, p.cpf, a.data_anamnese
            FROM anamnesis a
            JOIN patients p ON a.patient_id = p.id
            WHERE p.nome LIKE %s OR p.cpf LIKE %s
            ORDER BY a.id DESC
        """, (f'%{q}%', f'%{q}%'))
    else:
        results = []
    return render_template('anamnesis/list_completed.html', results=results, query=q)

@anamnesis_bp.route('/view/<int:id>')
@login_required
def view_anamnesis(id):
    # Busca todos os campos da anamnese e o nome do paciente
    data = query("""
        SELECT a.*, p.nome as patient_name, p.cpf as patient_cpf,
               p.data_nascimento as patient_birth,
               ar.full_name as rogo_signer_name,
               ar.username as rogo_signer_username,
               ar.cro as rogo_signer_cro,
               ar.cro_uf as rogo_signer_cro_uf
        FROM anamnesis a
        JOIN patients p ON a.patient_id = p.id
        LEFT JOIN users ar ON ar.id = a.assinatura_a_rogo_por
        WHERE a.id = %s
    """, (id,), one=True)
    
    if not data:
        flash('Anamnese não encontrada.', 'danger')
        return redirect(url_for('anamnesis.list_completed'))
        
    return render_template('anamnesis/view.html', a=data)

@anamnesis_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_anamnesis(id):
    from werkzeug.security import check_password_hash
    anamnesis = query("SELECT a.*, p.nome as patient_name, p.id as patient_id, p.cpf as patient_cpf, p.rg as patient_rg FROM anamnesis a JOIN patients p ON a.patient_id = p.id WHERE a.id = %s", (id,), one=True)
    if not anamnesis:
        flash('Anamnese não encontrada.', 'danger')
        return redirect(url_for('anamnesis.list_completed'))

    if request.method == 'POST':
        password = request.form.get('confirm_password')
        user_data = query("SELECT password FROM users WHERE id = %s", (current_user.id,), one=True)
        
        if not check_password_hash(user_data['password'], password):
            flash('Senha de confirmação incorreta.', 'danger')
            return render_template(
                'anamnesis/edit_anamnesis.html',
                a=_merge_anamnesis_postback(anamnesis, request.form),
                signature_error='Senha de confirmação incorreta.',
            )

        try:
            signature_data = _prepare_anamnesis_signature(request.form)
        except ValueError as exc:
            signature_error = _signature_error_message(exc)
            flash(signature_error, 'danger')
            return render_template(
                'anamnesis/edit_anamnesis.html',
                a=_merge_anamnesis_postback(anamnesis, request.form),
                signature_error=signature_error,
            )

        # Campos para atualização (excluindo patient_id e id)
        fields = [
            'queixa_principal', 'historia_doenca_atual',
            'sofre_doenca', 'sofre_doenca_explica',
            'tratamento_medico', 'tratamento_medico_explica',
            'tomando_medicamento', 'tomando_medicamento_explica',
            'tem_alergia', 'tem_alergia_explica',
            'pressao_arterial', 'desmaios_convulsoes', 'tem_cancer',
            'radioterapia_quimioterapia', 'falta_ar',
            'fez_cirurgia', 'fez_cirurgia_explica',
            'sangramento_cortar', 'cicatrizacao',
            'foi_hospitalizado', 'foi_hospitalizado_explica',
            'alergia_medicamento_alimento', 'gestante', 'gestante_semanas',
            'problemas_saude_ja_teve', 'reacao_anestesia', 'reacao_anestesia_explica',
            'ultimo_tratamento_dentario', 'dor_dentes_gengiva', 'gengiva_sangra',
            'fio_dental', 'dores_estalos_maxilar', 'range_dentes',
            'antecedentes_familiares', 'causas_obitos_familiares',
            'fuma', 'fuma_quantidade', 'ingere_alcool', 'ingere_alcool_frequencia',
            'exercicios_fisicos', 'exercicios_fisicos_frequencia', 'assinatura_base64'
        ]
        
        set_clause = ', '.join([f"{f}=%s" for f in fields])
        values = [
            signature_data['assinatura'] if field == 'assinatura_base64' else request.form.get(field)
            for field in fields
        ]
        values.append(id)
        
        try:
            execute(f"UPDATE anamnesis SET {set_clause} WHERE id=%s", values)
            patient = {
                'id': anamnesis['patient_id'],
                'nome': anamnesis['patient_name'],
                'cpf': anamnesis.get('patient_cpf'),
                'rg': anamnesis.get('patient_rg'),
            }
            _record_anamnesis_signature(
                id,
                patient,
                request.form,
                signature_data,
                action='updated',
            )
            flash('Anamnese atualizada com sucesso!', 'success')
            return redirect(url_for('anamnesis.view_anamnesis', id=id))
        except Exception as e:
            flash_internal_error('Falha ao atualizar anamnese')

    return render_template('anamnesis/edit_anamnesis.html', a=anamnesis)
