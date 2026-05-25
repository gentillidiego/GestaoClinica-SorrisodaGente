from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from database import execute, query, execute_transaction
from werkzeug.security import check_password_hash
from datetime import datetime

endodontia_bp = Blueprint('endodontia', __name__, url_prefix='/endodontia')

@endodontia_bp.route('/<int:patient_id>/add_element', methods=['POST'])
@login_required
def add_element(patient_id):
    elemento = request.form.get('elemento_dentario')
    if not elemento:
        flash('O elemento dentário é obrigatório.', 'danger')
        return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-endodontia')
        
    try:
        execute('''
            INSERT INTO endodontia (patient_id, elemento_dentario, aluno_id)
            VALUES (%s, %s, %s)
        ''', (patient_id, elemento, current_user.id))
        flash(f'Elemento {elemento} adicionado para acompanhamento endodôntico.', 'success')
    except Exception as e:
        flash(f'Erro ao adicionar elemento: {str(e)}', 'danger')
        
    return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-endodontia')

@endodontia_bp.route('/followup/<int:endo_id>')
@login_required
def followup(endo_id):
    endo = query('''
        SELECT e.*, p.nome as patient_name, u.username as aluno_nome 
        FROM endodontia e
        JOIN patients p ON e.patient_id = p.id
        JOIN users u ON e.aluno_id = u.id
        WHERE e.id = %s
    ''', (endo_id,), one=True)
    
    if not endo:
        flash('Registro de endodontia não encontrado.', 'danger')
        return redirect(url_for('patients.list_patients'))
        
    followups = query('''
        SELECT f.*, u.username as professor_nome, u.role as professor_role
        FROM endodontia_followup f
        LEFT JOIN users u ON f.professor_id = u.id
        WHERE f.endodontia_id = %s
        ORDER BY f.data DESC, f.criado_em DESC
    ''', (endo_id,))
    
    canais = query('SELECT * FROM endodontia_canais WHERE endodontia_id = %s', (endo_id,))
    
    return render_template('endodontia/followup.html', 
                           endo=endo, 
                           followups=followups,
                           canais=canais,
                           current_date=datetime.now().strftime('%Y-%m-%d'))

@endodontia_bp.route('/followup/save_details/<int:endo_id>', methods=['POST'])
@login_required
def save_case_details(endo_id):
    # Campos básicos do caso
    coroa = request.form.get('coroa')
    canais_radiculares = request.form.get('canais_radiculares')
    regiao_apical = request.form.get('regiao_apical')
    demais = request.form.get('demais')
    diagnostico = request.form.get('diagnostico')
    grampo = request.form.get('grampo')
    finalidade_protetica = request.form.get('finalidade_protetica')
    
    try:
        execute('''
            UPDATE endodontia 
            SET coroa = %s, canais_radiculares = %s, regiao_apical = %s, demais = %s, 
                diagnostico = %s, grampo = %s, finalidade_protetica = %s
            WHERE id = %s
        ''', (coroa, canais_radiculares, regiao_apical, demais, diagnostico, grampo, finalidade_protetica, endo_id))
        
        # Gerenciar Canais (Tabela Técnica)
        # Primeiro removemos os existentes e adicionamos os novos para simplificar a atualização
        execute('DELETE FROM endodontia_canais WHERE endodontia_id = %s', (endo_id,))
        
        canais_lista = request.form.getlist('canal[]')
        cad_lista = request.form.getlist('cad[]')
        ref_lista = request.form.getlist('referencia[]')
        ct_lista = request.form.getlist('ct[]')
        li_lista = request.form.getlist('lima_inicial[]')
        lf_lista = request.form.getlist('lima_final[]')
        cone_lista = request.form.getlist('cone[]')
        selamento_lista = request.form.getlist('selamento[]')
        
        for i in range(len(canais_lista)):
            if canais_lista[i].strip():
                execute('''
                    INSERT INTO endodontia_canais (endodontia_id, canal, cad, referencia, ct, lima_inicial, lima_final, cone, selamento)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (endo_id, canais_lista[i], cad_lista[i], ref_lista[i], ct_lista[i], li_lista[i], lf_lista[i], cone_lista[i], selamento_lista[i]))
        
        flash('Informações técnicas salvas com sucesso.', 'success')
    except Exception as e:
        flash(f'Erro ao salvar informações técnicas: {str(e)}', 'danger')
        
    return redirect(url_for('endodontia.followup', endo_id=endo_id))

@endodontia_bp.route('/followup/add/<int:endo_id>', methods=['POST'])
@login_required
def add_followup(endo_id):
    data = request.form.get('data')
    evolucao = request.form.get('evolucao')
    
    if not data or not evolucao:
        flash('Data e evolução são obrigatórias.', 'danger')
        return redirect(url_for('endodontia.followup', endo_id=endo_id))
        
    try:
        execute('''
            INSERT INTO endodontia_followup (endodontia_id, data, evolucao, status)
            VALUES (%s, %s, %s, 'Pendente')
        ''', (endo_id, data, evolucao))
        flash('Evolução registrada com sucesso.', 'success')
    except Exception as e:
        flash(f'Erro ao registrar evolução: {str(e)}', 'danger')
        
    return redirect(url_for('endodontia.followup', endo_id=endo_id))

@endodontia_bp.route('/followup/sign_patient/<int:followup_id>', methods=['POST'])
@login_required
def sign_patient(followup_id):
    endo_id = request.form.get('endo_id')
    assinatura = request.form.get('assinatura_base64')
    
    if not assinatura:
        flash('Assinatura do paciente não capturada.', 'danger')
        return redirect(url_for('endodontia.followup', endo_id=endo_id))
        
    try:
        execute('UPDATE endodontia_followup SET assinatura_paciente_base64 = %s WHERE id = %s', (assinatura, followup_id))
        flash('Assinatura do paciente salva com sucesso.', 'success')
    except Exception as e:
        flash(f'Erro ao assinar: {str(e)}', 'danger')
        
    return redirect(url_for('endodontia.followup', endo_id=endo_id))

@endodontia_bp.route('/followup/sign_professor/<int:followup_id>', methods=['POST'])
@login_required
def sign_professor(followup_id):
    endo_id = request.form.get('endo_id')
    username = request.form.get('prof_username')
    password = request.form.get('prof_password')
    
    from constants import Role
    prof = query("SELECT id, password, role FROM users WHERE username = %s", (username,), one=True)
    if not prof or not check_password_hash(prof['password'], password) or prof['role'] not in [Role.DENTISTA, Role.ADMIN]:
        flash('Credenciais inválidas ou usuário sem permissão para validar.', 'danger')
        return redirect(url_for('endodontia.followup', endo_id=endo_id))
        
    try:
        execute('''
            UPDATE endodontia_followup 
            SET professor_id = %s, status = 'Concluído' 
            WHERE id = %s
        ''', (prof['id'], followup_id))
        flash('Evolução validada pelo dentista responsável.', 'success')
    except Exception as e:
        flash(f'Erro ao validar: {str(e)}', 'danger')
        
    return redirect(url_for('endodontia.followup', endo_id=endo_id))

@endodontia_bp.route('/delete/<int:endo_id>', methods=['POST'])
@login_required
def delete_element(endo_id):
    patient_id = request.form.get('patient_id')
    username = request.form.get('prof_username')
    password = request.form.get('prof_password')
    
    prof = query("SELECT password FROM users WHERE username = %s", (username,), one=True)
    if not prof or not check_password_hash(prof['password'], password):
        flash('Credenciais inválidas para excluir o elemento.', 'danger')
        return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-endodontia')
        
    try:
        execute_transaction([
            ('DELETE FROM endodontia_canais WHERE endodontia_id = %s', (endo_id,)),
            ('DELETE FROM endodontia_followup WHERE endodontia_id = %s', (endo_id,)),
            ('DELETE FROM endodontia WHERE id = %s', (endo_id,)),
        ])
        flash('Acompanhamento endodôntico removido.', 'success')
    except Exception as e:
        flash(f'Erro ao remover: {str(e)}', 'danger')
        
    return redirect(url_for('patients.view_patient', id=patient_id) + '#tab-endodontia')
