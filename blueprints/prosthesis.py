from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from database import execute, query, execute_transaction
from werkzeug.security import check_password_hash

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

@prosthesis_bp.route('/<int:patient_id>/create', methods=['POST'])
@login_required
def create_case(patient_id):
    tipo = request.form.get('tipo')
    valor_acordado = request.form.get('valor_acordado', 0)
    aluno_id = request.form.get('aluno_id')
    
    if tipo not in ['PPR', 'Total']:
        flash('Tipo de prótese inválido.', 'danger')
        return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-protese')
        
    try:
        # Aluno é o usuário logado por padrão se não vier do form
        aluno_id = aluno_id or current_user.id
        
        # Cria o caso com valor default 0 se não especificado
        prosthesis_id = execute('''
            INSERT INTO prosthesis (patient_id, created_by, aluno_responsavel_id, tipo, valor_acordado, status)
            VALUES (%s, %s, %s, %s, %s, 'Ativo')
        ''', (patient_id, current_user.id, aluno_id, tipo, valor_acordado or 0.0))
        
        # Cria as etapas base
        etapas = ETAPAS_PPR if tipo == 'PPR' else ETAPAS_TOTAL
        for i, nome in enumerate(etapas, 1):
            execute('''
                INSERT INTO prosthesis_etapas (prosthesis_id, numero_etapa, nome_etapa)
                VALUES (%s, %s, %s)
            ''', (prosthesis_id, i, nome))
            
        flash(f'Tratamento de {tipo} iniciado com sucesso.', 'success')
    except Exception as e:
        flash(f'Erro ao iniciar tratamento: {str(e)}', 'danger')
        
    return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-protese')

@prosthesis_bp.route('/etapa/update/<int:etapa_id>', methods=['POST'])
@login_required
def update_etapa(etapa_id):
    patient_id = request.form.get('patient_id')
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
        flash(f'Erro ao atualizar: {str(e)}', 'danger')
        
    return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-protese')

@prosthesis_bp.route('/etapa/sign_patient/<int:etapa_id>', methods=['POST'])
@login_required
def sign_patient(etapa_id):
    patient_id = request.form.get('patient_id')
    assinatura = request.form.get('assinatura_base64')
    
    if not assinatura:
        flash('Assinatura não capturada.', 'danger')
        return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-protese')
        
    try:
        execute('UPDATE prosthesis_etapas SET assinatura_paciente_base64 = %s WHERE id = %s', (assinatura, etapa_id))
        flash('Assinatura do paciente salva.', 'success')
    except Exception as e:
        flash(f'Erro ao assinar: {str(e)}', 'danger')
        
    return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-protese')

@prosthesis_bp.route('/etapa/sign_professor/<int:etapa_id>', methods=['POST'])
@login_required
def sign_professor(etapa_id):
    patient_id = request.form.get('patient_id')
    username = request.form.get('prof_username')
    password = request.form.get('prof_password')
    
    from constants import Role
    prof = query("SELECT id, password, role FROM users WHERE username = %s", (username,), one=True)
    if not prof or not check_password_hash(prof['password'], password) or prof['role'] not in [Role.DENTISTA, Role.ADMIN]:
        flash('Credenciais inválidas ou usuário sem permissão para validar etapa.', 'danger')
        return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-protese')
        
    try:
        execute("UPDATE prosthesis_etapas SET professor_id = %s, status = 'Concluído' WHERE id = %s", (prof['id'], etapa_id))
        flash('Etapa validada pelo dentista responsável.', 'success')
    except Exception as e:
        flash(f'Erro ao validar: {str(e)}', 'danger')
        
    return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-protese')

@prosthesis_bp.route('/payment/add/<int:prosthesis_id>', methods=['POST'])
@login_required
def add_payment(prosthesis_id):
    patient_id = request.form.get('patient_id')
    valor = request.form.get('valor')
    assinatura = request.form.get('assinatura_base64')
    
    try:
        execute('''
            INSERT INTO prosthesis_pagamentos (prosthesis_id, valor, responsavel_id, assinatura_paciente_base64)
            VALUES (%s, %s, %s, %s)
        ''', (prosthesis_id, valor, current_user.id, assinatura))
        flash('Pagamento registrado com sucesso.', 'success')
    except Exception as e:
        flash(f'Erro ao registrar pagamento: {str(e)}', 'danger')
        
    return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-protese')

@prosthesis_bp.route('/delete_case/<int:patient_id>/<int:prosthesis_id>', methods=['POST'])
@login_required
def delete_case(patient_id, prosthesis_id):
    username = request.form.get('prof_username')
    password = request.form.get('prof_password')
    
    prof = query("SELECT password FROM users WHERE username = %s", (username,), one=True)
    if not prof or not check_password_hash(prof['password'], password):
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
        flash(f'Erro ao remover: {str(e)}', 'danger')
        
    return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-protese')

@prosthesis_bp.route('/update_agreement/<int:prosthesis_id>', methods=['POST'])
@login_required
def update_agreement(prosthesis_id):
    patient_id = request.form.get('patient_id')
    valor = request.form.get('valor_acordado')
    
    try:
        execute('UPDATE prosthesis SET valor_acordado = %s WHERE id = %s', (valor, prosthesis_id))
        flash('Valor acordado atualizado.', 'success')
    except Exception as e:
        flash(f'Erro ao atualizar valor: {str(e)}', 'danger')
        
    return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-protese')
