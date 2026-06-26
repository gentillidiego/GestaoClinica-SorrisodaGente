from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from database import execute, query, execute_transaction
from werkzeug.security import check_password_hash
from constants import can_sign_clinical_document
from services.signature_evidence_service import (
    SIGNATURE_MODE_CANVAS,
    build_generic_signature_payload,
    register_signature_event,
)
from services.web_security_service import flash_internal_error

prosthesis_bp = Blueprint('prosthesis', __name__, url_prefix='/prosthesis')

ETAPAS_PPR = [
    "1ª Sessão – Moldagem Anatômica",
    "Planejamento e Delineamento (etapa sem o paciente)",
    "2ª Sessão – Preparo de boca + Moldagem de Trabalho",
    "3ª Sessão – Prova da Estrutura Metálica e Registros",
    "4ª Sessão – Prova Estética e Funcional",
    "5ª Sessão – Instalação da PPR",
    "6ª Sessão – Retorno / Ajustes"
]

ETAPAS_TOTAL = [
    "1ª Sessão – Moldagem Preliminar",
    "2ª Sessão – Moldagem Funcional",
    "3ª Sessão – Planos de Orientação",
    "4ª Sessão – Prova de Dentes",
    "5ª Sessão – Instalação",
    "6ª Sessão – Retorno/Ajustes"
]


def _record_prosthesis_signature(document_type, document_id, patient, document_data, assinatura):
    payload = build_generic_signature_payload(
        document_type,
        patient,
        SIGNATURE_MODE_CANVAS,
        document_data=document_data,
        signature_capture=assinatura,
        signer=current_user,
    )
    return register_signature_event(
        document_type=document_type,
        document_id=document_id,
        patient=patient,
        signature_mode=SIGNATURE_MODE_CANVAS,
        payload=payload,
        signed_by_user=current_user,
        auth_method='patient_canvas_session',
        metadata=document_data,
    )


def _get_prosthesis(prosthesis_id):
    return query(
        """
        SELECT pr.*, p.nome, p.cpf, p.rg
        FROM prosthesis pr
        JOIN patients p ON p.id = pr.patient_id
        WHERE pr.id = %s
        """,
        (prosthesis_id,),
        one=True,
    )


def _get_prosthesis_stage(etapa_id):
    return query(
        """
        SELECT pe.*, pr.patient_id, p.nome, p.cpf, p.rg
        FROM prosthesis_etapas pe
        JOIN prosthesis pr ON pr.id = pe.prosthesis_id
        JOIN patients p ON p.id = pr.patient_id
        WHERE pe.id = %s
        """,
        (etapa_id,),
        one=True,
    )


def _patient_scope_matches(requested_patient_id, actual_patient_id):
    if not requested_patient_id:
        return True
    try:
        return int(requested_patient_id) == int(actual_patient_id)
    except (TypeError, ValueError):
        return False


@prosthesis_bp.route('/<int:patient_id>/create', methods=['POST'])
@login_required
def create_case(patient_id):
    patient = query(
        "SELECT id FROM patients WHERE id = %s",
        (patient_id,),
        one=True,
    )
    if not patient:
        flash('Paciente não encontrado.', 'danger')
        return redirect(url_for('patients.list_patients'))

    tipo = request.form.get('tipo')
    valor_acordado = request.form.get('valor_acordado', 0)
    operator_id = request.form.get('operator_id')
    
    if tipo not in ['PPR', 'Total']:
        flash('Tipo de prótese inválido.', 'danger')
        return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-protese')
        
    try:
        # O profissional logado é o responsável padrão quando o formulário não informa outro.
        operator_id = operator_id or current_user.id
        
        # Cria o caso com valor default 0 se não especificado
        prosthesis_id = execute('''
            INSERT INTO prosthesis (patient_id, created_by, responsible_professional_id, tipo, valor_acordado, status)
            VALUES (%s, %s, %s, %s, %s, 'Ativo')
            RETURNING id
        ''', (patient_id, current_user.id, operator_id, tipo, valor_acordado or 0.0))
        
        # Cria as etapas base
        etapas = ETAPAS_PPR if tipo == 'PPR' else ETAPAS_TOTAL
        for i, nome in enumerate(etapas, 1):
            execute('''
                INSERT INTO prosthesis_etapas (prosthesis_id, numero_etapa, nome_etapa)
                VALUES (%s, %s, %s)
            ''', (prosthesis_id, i, nome))
            
        flash(f'Tratamento de {tipo} iniciado com sucesso.', 'success')
    except Exception as e:
        flash_internal_error('Falha ao iniciar tratamento de prótese')
        
    return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-protese')

@prosthesis_bp.route('/etapa/update/<int:etapa_id>', methods=['POST'])
@login_required
def update_etapa(etapa_id):
    etapa = _get_prosthesis_stage(etapa_id)
    if not etapa:
        flash('Etapa de prótese não encontrada.', 'danger')
        return redirect(url_for('patients.list_patients'))
    patient_id = etapa['patient_id']
    if not _patient_scope_matches(request.form.get('patient_id'), patient_id):
        flash('Etapa não pertence ao paciente informado.', 'danger')
        return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-protese')
    data_etapa = request.form.get('data_etapa')
    data_envio_lab = request.form.get('data_envio_lab')
    servico = request.form.get('servico_solicitado')
    
    try:
        execute('''
            UPDATE prosthesis_etapas 
            SET data_etapa = %s, data_envio_lab = %s, servico_solicitado = %s
            WHERE id = %s
        ''', (data_etapa, data_envio_lab, servico, etapa_id))
        flash('Informações da etapa atualizadas.', 'success')
    except Exception as e:
        flash_internal_error('Falha ao atualizar etapa de prótese')
        
    return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-protese')

@prosthesis_bp.route('/etapa/sign_patient/<int:etapa_id>', methods=['POST'])
@login_required
def sign_patient(etapa_id):
    etapa = _get_prosthesis_stage(etapa_id)
    if not etapa:
        flash('Etapa de prótese não encontrada.', 'danger')
        return redirect(url_for('patients.list_patients'))
    patient_id = etapa['patient_id']
    if not _patient_scope_matches(request.form.get('patient_id'), patient_id):
        flash('Etapa não pertence ao paciente informado.', 'danger')
        return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-protese')
    assinatura = request.form.get('assinatura_base64')
    
    if not assinatura:
        flash('Assinatura não capturada.', 'danger')
        return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-protese')
        
    try:
        patient = {'id': etapa['patient_id'], 'nome': etapa['nome'], 'cpf': etapa['cpf'], 'rg': etapa['rg']}
        evidence = _record_prosthesis_signature(
            'prosthesis_stage_patient_signature',
            etapa_id,
            patient,
            {
                'prosthesis_id': etapa['prosthesis_id'],
                'etapa_id': etapa_id,
                'numero_etapa': etapa['numero_etapa'],
                'nome_etapa': etapa['nome_etapa'],
                'servico_solicitado': etapa['servico_solicitado'],
            },
            assinatura,
        )
        execute(
            """
            UPDATE prosthesis_etapas
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
                evidence['event_id'],
                evidence['document_hash'],
                'patient_canvas_session',
                evidence['source_ip'],
                evidence['user_agent'],
                etapa_id,
            ),
        )
        flash('Assinatura do paciente salva.', 'success')
    except Exception as e:
        flash_internal_error('Falha ao registrar assinatura da prótese')
        
    return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-protese')

@prosthesis_bp.route('/etapa/sign_validator/<int:etapa_id>', methods=['POST'])
@login_required
def sign_validator(etapa_id):
    etapa = _get_prosthesis_stage(etapa_id)
    if not etapa:
        flash('Etapa de prótese não encontrada.', 'danger')
        return redirect(url_for('patients.list_patients'))
    patient_id = etapa['patient_id']
    if not _patient_scope_matches(request.form.get('patient_id'), patient_id):
        flash('Etapa não pertence ao paciente informado.', 'danger')
        return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-protese')
    username = request.form.get('validator_username')
    password = request.form.get('validator_password')
    
    prof = query("SELECT id, password, role FROM users WHERE username = %s", (username,), one=True)
    if not prof or not check_password_hash(prof['password'], password) or not can_sign_clinical_document(prof['role']):
        flash('Credenciais inválidas ou usuário sem permissão para validar etapa.', 'danger')
        return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-protese')
        
    try:
        execute("UPDATE prosthesis_etapas SET validator_id = %s, status = 'Concluído' WHERE id = %s", (prof['id'], etapa_id))
        flash('Etapa validada pelo dentista responsável.', 'success')
    except Exception as e:
        flash_internal_error('Falha ao validar etapa de prótese')
        
    return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-protese')

@prosthesis_bp.route('/payment/add/<int:prosthesis_id>', methods=['POST'])
@login_required
def add_payment(prosthesis_id):
    prosthesis = _get_prosthesis(prosthesis_id)
    if not prosthesis:
        flash('Tratamento de prótese não encontrado.', 'danger')
        return redirect(url_for('patients.list_patients'))
    patient_id = prosthesis['patient_id']
    if not _patient_scope_matches(request.form.get('patient_id'), patient_id):
        flash('Tratamento não pertence ao paciente informado.', 'danger')
        return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-protese')
    valor = request.form.get('valor')
    assinatura = request.form.get('assinatura_base64')

    if not assinatura:
        flash('Assinatura do paciente é obrigatória para registrar pagamento.', 'danger')
        return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-protese')
    
    try:
        payment_id = execute('''
            INSERT INTO prosthesis_pagamentos (prosthesis_id, valor, responsavel_id, assinatura_paciente_base64)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        ''', (prosthesis_id, valor, current_user.id, assinatura))
        if prosthesis:
            patient = {'id': prosthesis['patient_id'], 'nome': prosthesis['nome'], 'cpf': prosthesis['cpf'], 'rg': prosthesis['rg']}
            evidence = _record_prosthesis_signature(
                'prosthesis_payment_receipt',
                payment_id,
                patient,
                {
                    'prosthesis_id': prosthesis_id,
                    'payment_id': payment_id,
                    'valor': valor,
                },
                assinatura,
            )
            execute(
                """
                UPDATE prosthesis_pagamentos
                SET assinatura_modo = %s,
                    assinatura_event_id = %s,
                    assinatura_document_hash = %s,
                    assinatura_auth_method = %s,
                    assinatura_source_ip = %s,
                    assinatura_user_agent = %s
                WHERE id = %s
                """,
                (
                    SIGNATURE_MODE_CANVAS,
                    evidence['event_id'],
                    evidence['document_hash'],
                    'patient_canvas_session',
                    evidence['source_ip'],
                    evidence['user_agent'],
                    payment_id,
                ),
            )
        flash('Pagamento registrado com sucesso.', 'success')
    except Exception as e:
        flash_internal_error('Falha ao registrar pagamento de prótese')
        
    return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-protese')

@prosthesis_bp.route('/delete_case/<int:patient_id>/<int:prosthesis_id>', methods=['POST'])
@login_required
def delete_case(patient_id, prosthesis_id):
    username = request.form.get('validator_username')
    password = request.form.get('validator_password')
    
    prosthesis = query(
        """
        SELECT id, patient_id
        FROM prosthesis
        WHERE id = %s AND patient_id = %s
        """,
        (prosthesis_id, patient_id),
        one=True,
    )
    if not prosthesis:
        flash('Tratamento de prótese não encontrado para este paciente.', 'danger')
        return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-protese')

    prof = query("SELECT password, role FROM users WHERE username = %s", (username,), one=True)
    if (
        not prof
        or not check_password_hash(prof['password'], password)
        or not can_sign_clinical_document(prof['role'])
    ):
        flash('Credenciais inválidas para excluir o caso.', 'danger')
        return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-protese')
        
    try:
        execute_transaction([
            ('DELETE FROM prosthesis_etapas WHERE prosthesis_id = %s', (prosthesis_id,)),
            ('DELETE FROM prosthesis_pagamentos WHERE prosthesis_id = %s', (prosthesis_id,)),
            ('DELETE FROM prosthesis WHERE id = %s', (prosthesis_id,)),
        ])
        flash('Tratamento de prótese removido.', 'success')
    except Exception as e:
        flash_internal_error('Falha ao remover tratamento de prótese')
        
    return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-protese')

@prosthesis_bp.route('/update_agreement/<int:prosthesis_id>', methods=['POST'])
@login_required
def update_agreement(prosthesis_id):
    prosthesis = _get_prosthesis(prosthesis_id)
    if not prosthesis:
        flash('Tratamento de prótese não encontrado.', 'danger')
        return redirect(url_for('patients.list_patients'))
    patient_id = prosthesis['patient_id']
    if not _patient_scope_matches(request.form.get('patient_id'), patient_id):
        flash('Tratamento não pertence ao paciente informado.', 'danger')
        return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-protese')
    valor = request.form.get('valor_acordado')
    
    try:
        execute('UPDATE prosthesis SET valor_acordado = %s WHERE id = %s', (valor, prosthesis_id))
        flash('Valor acordado atualizado.', 'success')
    except Exception as e:
        flash_internal_error('Falha ao atualizar valor da prótese')
        
    return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-protese')
