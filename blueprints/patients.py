from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash
from database import execute, query, execute_transaction
from constants import Role
import math
from datetime import datetime

patients_bp = Blueprint('patients', __name__, url_prefix='/patients')


def _normalize_triage_code(value):
    return (value or '').strip().upper()

@patients_bp.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    senha_triagem = _normalize_triage_code(request.args.get('senha'))
    if request.method == 'POST':
        senha_triagem = _normalize_triage_code(request.form.get('senha_triagem'))
        triage_ticket = query('''
            SELECT s.*, e.nome as especialidade_nome, m.nome as municipio_nome
            FROM triagem_senhas s
            JOIN especialidades e ON s.especialidade_id = e.id
            JOIN municipios m ON s.municipio_id = m.id
            WHERE s.codigo = %s
        ''', (senha_triagem,), one=True)

        if not triage_ticket:
            flash('Senha de triagem não encontrada. Verifique o código informado.', 'danger')
            return render_template('patients/register.html', senha_triagem=senha_triagem)
        if triage_ticket['patient_id']:
            flash('Esta senha de triagem já está vinculada a outro paciente.', 'danger')
            return render_template('patients/register.html', senha_triagem=senha_triagem)
        if triage_ticket['status'] == 'Cancelada':
            flash('Esta senha de triagem está cancelada e não pode iniciar atendimento.', 'danger')
            return render_template('patients/register.html', senha_triagem=senha_triagem)

        # Coleta de dados do formulário
        data = {
            'cns': request.form.get('cns'),
            'nome': request.form.get('nome'),
            'rg': request.form.get('rg'),
            'cpf': request.form.get('cpf'),
            'profissao': request.form.get('profissao'),
            'endereco_residencial': request.form.get('endereco_residencial'),
            'endereco_comercial': request.form.get('endereco_comercial'),
            'cd_anterior': request.form.get('cd_anterior'),
            'endereco_comercial_adicional': request.form.get('endereco_comercial_adicional'),
            'email': request.form.get('email'),
            'genero': request.form.get('genero'),
            'data_nascimento': request.form.get('data_nascimento'),
            'nacionalidade': request.form.get('nacionalidade'),
            'celular': request.form.get('celular'),
            'estado_civil': request.form.get('estado_civil'),
            'atendido_em': request.form.get('atendido_em'),
            'nome_responsavel': request.form.get('nome_responsavel'),
            'rg_responsavel': request.form.get('rg_responsavel'),
            'telefone_expedidor_responsavel': request.form.get('telefone_expedidor_responsavel'),
            'email_responsavel': request.form.get('email_responsavel')
        }
        
        try:
            patient_id = execute('''
                WITH available_ticket AS (
                    SELECT id
                    FROM triagem_senhas
                    WHERE id = %s AND patient_id IS NULL AND status != 'Cancelada'
                    FOR UPDATE
                ),
                new_patient AS (
                    INSERT INTO patients (
                        cns, nome, rg, cpf, profissao, endereco_residencial, endereco_comercial,
                        cd_anterior, endereco_comercial_adicional, email, genero, data_nascimento,
                        nacionalidade, celular, estado_civil, atendido_em, nome_responsavel,
                        rg_responsavel, telefone_expedidor_responsavel, email_responsavel
                    )
                    SELECT %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    WHERE EXISTS (SELECT 1 FROM available_ticket)
                    RETURNING id
                )
                UPDATE triagem_senhas
                SET status = 'Vinculada',
                    patient_id = (SELECT id FROM new_patient),
                    vinculada_em = CURRENT_TIMESTAMP
                WHERE id = (SELECT id FROM available_ticket)
                RETURNING patient_id as id
            ''', (triage_ticket['id'], *list(data.values())))
            if not patient_id:
                flash('A senha foi vinculada por outro atendimento. Atualize e tente novamente.', 'danger')
                return render_template('patients/register.html', senha_triagem=senha_triagem)

            flash('Paciente cadastrado com sucesso!', 'success')
            return redirect(url_for('patients.view_patient', id=patient_id))
        except Exception as e:
            flash(f'Erro ao cadastrar paciente: {str(e)}', 'danger')
            
    return render_template('patients/register.html', senha_triagem=senha_triagem)
@patients_bp.route('/list')
@login_required
def list_patients():
    q = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    per_page = 30
    offset = (page - 1) * per_page
    
    if q:
        search_term = f'%{q}%'
        where_clause = """
            WHERE p.nome ILIKE %s OR p.cpf ILIKE %s OR p.cns ILIKE %s
               OR p.celular ILIKE %s OR ts.codigo ILIKE %s
               OR e.nome ILIKE %s OR m.nome ILIKE %s
        """
        params = (search_term, search_term, search_term, search_term, search_term, search_term, search_term)
        
        try:
            date_term = datetime.strptime(q, "%d/%m/%Y").strftime("%Y-%m-%d")
            where_clause += " OR data_nascimento = %s"
            params = params + (date_term,)
        except ValueError:
            pass
    else:
        where_clause = ""
        params = ()
        
    patients = query(f"""
        SELECT p.id, p.nome, p.cpf, ts.codigo as senha_triagem,
               e.nome as especialidade_nome, m.codigo as municipio_codigo
        FROM patients p
        LEFT JOIN triagem_senhas ts ON ts.patient_id = p.id
        LEFT JOIN especialidades e ON ts.especialidade_id = e.id
        LEFT JOIN municipios m ON ts.municipio_id = m.id
        {where_clause}
        ORDER BY p.id DESC
        LIMIT %s OFFSET %s
    """, (*params, per_page, offset))
    
    total_count = query(f"""
        SELECT COUNT(*) as count
        FROM patients p
        LEFT JOIN triagem_senhas ts ON ts.patient_id = p.id
        LEFT JOIN especialidades e ON ts.especialidade_id = e.id
        LEFT JOIN municipios m ON ts.municipio_id = m.id
        {where_clause}
    """, params, one=True)['count']
    total_pages = math.ceil(total_count / per_page)
    
    return render_template('patients/list.html', patients=patients, query=q, page=page, total_pages=total_pages)

@patients_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_patient(id):
    patient = query("SELECT * FROM patients WHERE id = %s", (id,), one=True)
    if not patient:
        flash('Paciente não encontrado.', 'danger')
        return redirect(url_for('patients.list_patients'))
        
    if request.method == 'POST':
        password = request.form.get('confirm_password')
        
        # Verificar senha do usuário logado
        user_data = query("SELECT password FROM users WHERE id = %s", (current_user.id,), one=True)
        if not check_password_hash(user_data['password'], password):
            flash('Senha de confirmação incorreta.', 'danger')
            return render_template('patients/edit.html', patient=patient)
            
        data = {
            'cns': request.form.get('cns'),
            'nome': request.form.get('nome'),
            'rg': request.form.get('rg'),
            'cpf': request.form.get('cpf'),
            'profissao': request.form.get('profissao'),
            'endereco_residencial': request.form.get('endereco_residencial'),
            'endereco_comercial': request.form.get('endereco_comercial'),
            'cd_anterior': request.form.get('cd_anterior'),
            'endereco_comercial_adicional': request.form.get('endereco_comercial_adicional'),
            'email': request.form.get('email'),
            'genero': request.form.get('genero'),
            'data_nascimento': request.form.get('data_nascimento'),
            'nacionalidade': request.form.get('nacionalidade'),
            'celular': request.form.get('celular'),
            'estado_civil': request.form.get('estado_civil'),
            'atendido_em': request.form.get('atendido_em'),
            'nome_responsavel': request.form.get('nome_responsavel'),
            'rg_responsavel': request.form.get('rg_responsavel'),
            'telefone_expedidor_responsavel': request.form.get('telefone_expedidor_responsavel'),
            'email_responsavel': request.form.get('email_responsavel'),
            'id': id
        }
        
        try:
            execute('''
                UPDATE patients SET 
                    cns=%s, nome=%s, rg=%s, cpf=%s, profissao=%s, endereco_residencial=%s, endereco_comercial=%s,
                    cd_anterior=%s, endereco_comercial_adicional=%s, email=%s, genero=%s, data_nascimento=%s,
                    nacionalidade=%s, celular=%s, estado_civil=%s, atendido_em=%s, nome_responsavel=%s,
                    rg_responsavel=%s, telefone_expedidor_responsavel=%s, email_responsavel=%s
                WHERE id=%s
            ''', list(data.values()))
            flash('Dados do paciente atualizados!', 'success')
            return redirect(url_for('patients.list_patients'))
        except Exception as e:
            flash(f'Erro ao atualizar: {str(e)}', 'danger')
            
    return render_template('patients/edit.html', patient=patient)

from services.patient_service import PatientService

@patients_bp.route('/view/<int:id>')
@login_required
def view_patient(id):
    data = PatientService.get_patient_basic_info(id)
    if not data or not data.get('patient'):
        flash('Paciente não encontrado.', 'danger')
        return redirect(url_for('patients.list_patients'))
        
    return render_template('patients/view.html', **data)

from extensions import cache

@cache.cached(timeout=600, key_prefix='students_list')
def get_students_cached():
    # Retorna TSBs e Dentistas — quem pode executar procedimentos
    return query("SELECT id, username, full_name FROM users WHERE role IN (%s, %s) ORDER BY full_name ASC", (Role.TSB, Role.DENTISTA))

@patients_bp.route('/view/<int:id>/tab/<tab_name>')
@login_required
def get_tab_content(id, tab_name):
    # Dicionário de mapeamento de abas para métodos de serviço e seus respectivos templates parciais
    tab_mapping = {
        'tab-anamnese': {
            'service': PatientService.get_patient_anamnesis,
            'template': 'patients/includes/_tab_anamnese.html',
            'context_key': 'anamnesis'
        },
        'tab-exames': {
            'service': PatientService.get_patient_exams,
            'template': 'patients/includes/_tab_exames.html',
            'context_key': 'exams'
        },
        'tab-atendimento': {
            'service': PatientService.get_patient_appointments,
            'template': 'patients/includes/_tab_atendimento.html',
            'context_key': 'appointments'
        },
        'tab-tratamento': {
            'service': PatientService.get_patient_treatments,
            'template': 'patients/includes/_tab_tratamento.html',
            'is_dict': True
        },
        'tab-endodontia': {
            'service': PatientService.get_patient_endodontia,
            'template': 'patients/includes/_tab_endodontia.html',
            'context_key': 'endodontia_elements'
        },
        'tab-protese': {
            'service': PatientService.get_patient_prosthesis,
            'template': 'patients/includes/_tab_protese.html',
            'is_dict': True
        },
        'tab-receituario': {
            'service': PatientService.get_patient_documents,
            'template': 'patients/includes/_tab_receituario.html',
            'is_dict': True
        },
        'tab-atestado': {
            'service': PatientService.get_patient_documents,
            'template': 'patients/includes/_tab_atestado.html',
            'is_dict': True
        }
    }

    if tab_name not in tab_mapping:
        return "Aba não encontrada.", 404

    config = tab_mapping[tab_name]
    data = config['service'](id)
    
    # Criar o contexto para a renderização do template
    context = PatientService.get_patient_basic_info(id)
    if not context:
        return "Paciente não encontrado.", 404
        
    if config.get('is_dict'):
        context.update(data)
    else:
        context[config['context_key']] = data
        
    # Adicionar alunos se for uma aba que precisa (atendimento, tratamento, endodontia, protese)
    if tab_name in ['tab-atendimento', 'tab-tratamento', 'tab-endodontia', 'tab-protese']:
        context['students'] = get_students_cached()

    context['now'] = datetime.now()

    return render_template(config['template'], **context)

@patients_bp.route('/tcle/<int:id>', methods=['GET', 'POST'])
@login_required
def patient_tcle(id):
    patient = query("SELECT * FROM patients WHERE id = %s", (id,), one=True)
    if not patient:
        flash('Paciente não encontrado.', 'danger')
        return redirect(url_for('patients.list_patients'))

    # Check if a TCLE is already signed
    existing_tcle = query('''
        SELECT t.*, u.username, u.full_name, u.cro, u.cro_uf 
        FROM patient_tcle t 
        JOIN users u ON t.aluno_id = u.id 
        WHERE t.patient_id = %s 
        ORDER BY t.data_assinatura DESC LIMIT 1
    ''', (id,), one=True)

    if existing_tcle:
        return render_template('patients/tcle_print.html', patient=patient, tcle=existing_tcle)

    if request.method == 'POST':
        assinatura = request.form.get('assinatura_base64')
        if not assinatura:
            flash('A assinatura do paciente é obrigatória.', 'danger')
            return render_template('patients/tcle.html', patient=patient)

        try:
            execute('''
                INSERT INTO patient_tcle (patient_id, aluno_id, assinatura_base64)
                VALUES (%s, %s, %s)
            ''', (id, current_user.id, assinatura))
            flash('Termo de Consentimento assinado com sucesso!', 'success')
            return redirect(url_for('patients.view_patient', id=id))
        except Exception as e:
            flash(f'Erro ao salvar termo: {str(e)}', 'danger')

    return render_template('patients/tcle.html', patient=patient)

@patients_bp.route('/<int:id>/treatment/add', methods=['POST'])
@login_required
def add_treatment(id):
    dente = request.form.get('dente')
    descricao = request.form.get('descricao')
    
    if not descricao:
        flash('Por favor, preencha o procedimento.', 'danger')
        return redirect(url_for('patients.view_patient', id=id) + '#tab-tratamento')
        
    try:
        execute('''
            INSERT INTO tratamento_procedimentos (patient_id, dente, descricao)
            VALUES (%s, %s, %s)
        ''', (id, dente, descricao))
        flash('Procedimento adicionado ao plano de tratamento.', 'success')
    except Exception as e:
        flash(f'Erro ao adicionar procedimento: {str(e)}', 'danger')
        
    return redirect(url_for('patients.view_patient', id=id) + '#tab-tratamento')

@patients_bp.route('/<int:id>/treatment/<int:proc_id>/edit', methods=['POST'])
@login_required
def edit_treatment(id, proc_id):
    dente = request.form.get('dente')
    descricao = request.form.get('descricao')
    
    if not descricao:
        flash('Por favor, preencha o procedimento.', 'danger')
        return redirect(url_for('patients.view_patient', id=id) + '#tab-tratamento')
        
    try:
        execute('''
            UPDATE tratamento_procedimentos 
            SET dente = %s, descricao = %s
            WHERE id = %s AND patient_id = %s
        ''', (dente, descricao, proc_id, id))
        flash('Procedimento atualizado com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao atualizar procedimento: {str(e)}', 'danger')
        
    return redirect(url_for('patients.view_patient', id=id) + '#tab-tratamento')

@patients_bp.route('/<int:id>/treatment/<int:proc_id>/delete', methods=['POST'])
@login_required
def delete_treatment(id, proc_id):
    try:
        execute('DELETE FROM tratamento_procedimentos WHERE id = %s AND patient_id = %s', (proc_id, id))
        flash('Procedimento excluído com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao excluir procedimento: {str(e)}', 'danger')
        
    return redirect(url_for('patients.view_patient', id=id) + '#tab-tratamento')
@patients_bp.route('/<int:id>/treatment/<int:proc_id>/sign', methods=['POST'])
@login_required
def sign_treatment(id, proc_id):
    username = request.form.get('prof_username')
    password = request.form.get('prof_password')
    
    if not username or not password:
        flash('Usuário e senha são obrigatórios para assinar.', 'danger')
        return redirect(url_for('patients.view_patient', id=id) + '#tab-tratamento')
        
    # Verifica credenciais do professor
    prof = query("SELECT id, password, role FROM users WHERE username = %s", (username,), one=True)
    
    if not prof or not check_password_hash(prof['password'], password):
        flash('Credenciais inválidas. Assinatura não realizada.', 'danger')
        return redirect(url_for('patients.view_patient', id=id) + '#tab-tratamento')
        
    # No sistema atual, admin ou user podem assinar, 
    # se houver regra estrita de 'admin' apenas, pode-se checar prof['role'] == 'admin'
    
    try:
        execute('''
            UPDATE tratamento_procedimentos 
            SET professor_id = %s, status = 'Concluído'
            WHERE id = %s AND patient_id = %s
        ''', (prof['id'], proc_id, id))
        
        # Busca o procedimento para pegar os detalhes
        proc = query("SELECT dente, descricao FROM tratamento_procedimentos WHERE id = %s", (proc_id,), one=True)
        obs = f"Dente {proc['dente']}: {proc['descricao']}" if proc['dente'] else proc['descricao']
        
        # Importa automaticamente para a aba Atendimento (Evolução)
        # Data fica em branco até que paciente também assine
        execute('''
            INSERT INTO atendimentos (patient_id, data, observacoes, created_by, professor_id, status)
            VALUES (%s, NULL, %s, %s, %s, 'Concluído')
        ''', (id, obs, current_user.id, prof['id']))
        
        flash('Procedimento assinado e importado para evolução!', 'success')
    except Exception as e:
        flash(f'Erro ao assinar procedimento: {str(e)}', 'danger')
        
    return redirect(url_for('patients.view_patient', id=id) + '#tab-tratamento')

@patients_bp.route('/<int:id>/atendimento/add', methods=['POST'])
@login_required
def add_atendimento(id):
    data_sessao = request.form.get('data')
    observacoes = request.form.get('observacoes')
    
    if not all([data_sessao, observacoes]):
        flash('Por favor, preencha a data e as observações (Evolução).', 'danger')
        return redirect(url_for('patients.view_patient', id=id) + '#tab-atendimento')
        
    try:
        execute('''
            INSERT INTO atendimentos (patient_id, data, observacoes, created_by, status)
            VALUES (%s, %s, %s, %s, 'Pendente')
        ''', (id, data_sessao, observacoes, current_user.id))
        flash('Evolução clínica registrada com sucesso.', 'success')
    except Exception as e:
        flash(f'Erro ao registrar evolução: {str(e)}', 'danger')
        
    return redirect(url_for('patients.view_patient', id=id) + '#tab-atendimento')

@patients_bp.route('/<int:id>/atendimento/<int:appt_id>/sign_patient', methods=['POST'])
@login_required
def sign_patient_atendimento(id, appt_id):
    assinatura_base64 = request.form.get('assinatura_base64')
    
    if not assinatura_base64:
        flash('Nenhuma assinatura fornecida.', 'danger')
        return redirect(url_for('patients.view_patient', id=id) + '#tab-atendimento')
        
    try:
        execute('''
            UPDATE atendimentos 
            SET assinatura_paciente_base64 = %s
            WHERE id = %s AND patient_id = %s
        ''', (assinatura_base64, appt_id, id))
        
        # Verifica se já tem assinatura do professor e do aluno executor para gerar a data
        appt = query("SELECT data, professor_id, aluno_executor_id FROM atendimentos WHERE id = %s", (appt_id,), one=True)
        if appt['professor_id'] and appt['aluno_executor_id'] and (not appt['data'] or appt['data'] == ''):
            execute("UPDATE atendimentos SET data = %s WHERE id = %s", (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), appt_id))
            
        flash('Assinatura do paciente registrada com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao registrar assinatura: {str(e)}', 'danger')
        
    return redirect(url_for('patients.view_patient', id=id) + '#tab-atendimento')

@patients_bp.route('/<int:id>/atendimento/<int:appt_id>/sign_student', methods=['POST'])
@login_required
def sign_student_atendimento(id, appt_id):
    username = request.form.get('student_username')
    password = request.form.get('student_password')
    
    if not username or not password:
        flash('Usuário e senha são obrigatórios para assinar.', 'danger')
        return redirect(url_for('patients.view_patient', id=id) + '#tab-atendimento')
        
    # Verifica credenciais do aluno
    user = query("SELECT id, password, role FROM users WHERE username = %s", (username,), one=True)
    
    if not user or not check_password_hash(user['password'], password):
        flash('Credenciais inválidas. Assinatura não realizada.', 'danger')
        return redirect(url_for('patients.view_patient', id=id) + '#tab-atendimento')
        
    try:
        execute('''
            UPDATE atendimentos 
            SET aluno_executor_id = %s
            WHERE id = %s AND patient_id = %s
        ''', (user['id'], appt_id, id))
        
        # Verifica se já tem assinatura do professor e do paciente para gerar a data
        appt = query("SELECT data, professor_id, assinatura_paciente_base64 FROM atendimentos WHERE id = %s", (appt_id,), one=True)
        if appt['professor_id'] and appt['assinatura_paciente_base64'] and (not appt['data'] or appt['data'] == ''):
            execute("UPDATE atendimentos SET data = %s WHERE id = %s", (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), appt_id))
            
        flash('Assinatura do profissional executor registrada com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao registrar assinatura: {str(e)}', 'danger')
        
    return redirect(url_for('patients.view_patient', id=id) + '#tab-atendimento')

@patients_bp.route('/<int:id>/atendimento/<int:appt_id>/edit', methods=['POST'])
@login_required
def edit_atendimento(id, appt_id):
    data_sessao = request.form.get('data')
    observacoes = request.form.get('observacoes')
    
    if not all([data_sessao, observacoes]):
        flash('Data e observações são obrigatórias.', 'danger')
        return redirect(url_for('patients.view_patient', id=id) + '#tab-atendimento')
        
    # Check permission
    appt = query("SELECT created_by, professor_id FROM atendimentos WHERE id = %s", (appt_id,), one=True)
    if not appt or (current_user.id != appt['created_by'] and current_user.id != appt['professor_id'] and not current_user.is_admin):
        flash('Sem permissão para editar este atendimento.', 'danger')
        return redirect(url_for('patients.view_patient', id=id) + '#tab-atendimento')
        
    try:
        execute('''
            UPDATE atendimentos 
            SET data = %s, observacoes = %s
            WHERE id = %s AND patient_id = %s
        ''', (data_sessao, observacoes, appt_id, id))
        flash('Evolução clínica atualizada com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao atualizar evolução: {str(e)}', 'danger')
        
    return redirect(url_for('patients.view_patient', id=id) + '#tab-atendimento')

@patients_bp.route('/<int:id>/atendimento/<int:appt_id>/delete', methods=['POST'])
@login_required
def delete_atendimento(id, appt_id):
    # Check permission
    appt = query("SELECT created_by, professor_id FROM atendimentos WHERE id = %s", (appt_id,), one=True)
    if not appt or (current_user.id != appt['created_by'] and current_user.id != appt['professor_id'] and not current_user.is_admin):
        flash('Sem permissão para excluir este atendimento.', 'danger')
        return redirect(url_for('patients.view_patient', id=id) + '#tab-atendimento')
        
    try:
        execute('DELETE FROM atendimentos WHERE id = %s AND patient_id = %s', (appt_id, id))
        flash('Evolução clínica excluída com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao excluir evolução: {str(e)}', 'danger')
        
    return redirect(url_for('patients.view_patient', id=id) + '#tab-atendimento')

@patients_bp.route('/<int:id>/atendimento/<int:appt_id>/sign', methods=['POST'])
@login_required
def sign_atendimento(id, appt_id):
    username = request.form.get('prof_username')
    password = request.form.get('prof_password')
    
    if not username or not password:
        flash('Usuário e senha são obrigatórios para assinar.', 'danger')
        return redirect(url_for('patients.view_patient', id=id) + '#tab-atendimento')
        
    # Verifica credenciais do professor
    prof = query("SELECT id, password, role FROM users WHERE username = %s", (username,), one=True)
    
    if not prof or not check_password_hash(prof['password'], password):
        flash('Credenciais inválidas. Assinatura não realizada.', 'danger')
        return redirect(url_for('patients.view_patient', id=id) + '#tab-atendimento')
        
    try:
        execute('''
            UPDATE atendimentos 
            SET professor_id = %s, status = 'Concluído'
            WHERE id = %s AND patient_id = %s
        ''', (prof['id'], appt_id, id))
        
        # Verifica se já tem assinatura do paciente e do aluno executor para gerar a data
        appt = query("SELECT data, assinatura_paciente_base64, aluno_executor_id FROM atendimentos WHERE id = %s", (appt_id,), one=True)
        if appt['assinatura_paciente_base64'] and appt['aluno_executor_id'] and (not appt['data'] or appt['data'] == ''):
            execute("UPDATE atendimentos SET data = %s WHERE id = %s", (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), appt_id))
            
        flash('Evolução clínica validada pelo dentista com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao assinar evolução: {str(e)}', 'danger')
        
    return redirect(url_for('patients.view_patient', id=id) + '#tab-atendimento')

@patients_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_patient(id):
    password = request.form.get('password')
    user_data = query("SELECT password FROM users WHERE id = %s", (current_user.id,), one=True)
    
    if not check_password_hash(user_data['password'], password):
        flash('Senha incorreta. Exclusão não realizada.', 'danger')
        return redirect(url_for('patients.list_patients'))
        
    try:
        execute_transaction([
            ('DELETE FROM exam_imagem_arquivos WHERE exam_id IN (SELECT id FROM exams WHERE patient_id = %s)', (id,)),
            ('DELETE FROM exam_imagem WHERE exam_id IN (SELECT id FROM exams WHERE patient_id = %s)', (id,)),
            ('DELETE FROM exam_fisico WHERE exam_id IN (SELECT id FROM exams WHERE patient_id = %s)', (id,)),
            ('DELETE FROM exam_odontograma WHERE exam_id IN (SELECT id FROM exams WHERE patient_id = %s)', (id,)),
            ('DELETE FROM exam_controle_placa WHERE exam_id IN (SELECT id FROM exams WHERE patient_id = %s)', (id,)),
            ('DELETE FROM exam_periograma WHERE exam_id IN (SELECT id FROM exams WHERE patient_id = %s)', (id,)),
            ('DELETE FROM exams WHERE patient_id = %s', (id,)),
            ('DELETE FROM anamnesis WHERE patient_id = %s', (id,)),
            ('DELETE FROM atendimentos WHERE patient_id = %s', (id,)),
            ('DELETE FROM planos_tratamento WHERE patient_id = %s', (id,)),
            ('DELETE FROM tratamento_procedimentos WHERE patient_id = %s', (id,)),
            ('DELETE FROM prosthesis_pagamentos WHERE prosthesis_id IN (SELECT id FROM prosthesis WHERE patient_id = %s)', (id,)),
            ('DELETE FROM prosthesis_etapas WHERE prosthesis_id IN (SELECT id FROM prosthesis WHERE patient_id = %s)', (id,)),
            ('DELETE FROM prosthesis WHERE patient_id = %s', (id,)),
            ('DELETE FROM endodontia_canais WHERE endodontia_id IN (SELECT id FROM endodontia WHERE patient_id = %s)', (id,)),
            ('DELETE FROM endodontia_followup WHERE endodontia_id IN (SELECT id FROM endodontia WHERE patient_id = %s)', (id,)),
            ('DELETE FROM endodontia WHERE patient_id = %s', (id,)),
            ('DELETE FROM receituarios WHERE patient_id = %s', (id,)),
            ('DELETE FROM atestados WHERE patient_id = %s', (id,)),
            ('DELETE FROM patient_tcle WHERE patient_id = %s', (id,)),
            ('DELETE FROM consultas WHERE patient_id = %s', (id,)),
            ("UPDATE triagem_senhas SET patient_id = NULL, status = 'Disponível', vinculada_em = NULL WHERE patient_id = %s", (id,)),
            ('DELETE FROM patients WHERE id = %s', (id,)),
        ])
        flash('Paciente excluído com sucesso.', 'success')
    except Exception as e:
        flash(f'Erro ao excluir: {str(e)}', 'danger')
        
    return redirect(url_for('patients.list_patients'))

@patients_bp.route('/pending-treatments')
@login_required
def pending_treatments():
    q = request.args.get('q', '')
    
    if q:
        search_term = f'%{q}%'
        where_clause = "WHERE tp.status = 'Pendente' AND (p.nome LIKE %s OR p.cpf LIKE %s)"
        params = (search_term, search_term)
    else:
        where_clause = "WHERE tp.status = 'Pendente'"
        params = ()
        
    # Agrupa os procedimentos pendentes por paciente
    # Para simplificar a view inicial: trazemos cada procedimento com o nome do paciente, ou trazemos os pacientes distintos
    
    query_sql = f"""
        SELECT tp.*, p.nome as patient_name, p.celular as patient_phone, p.cpf as patient_cpf
        FROM tratamento_procedimentos tp
        JOIN patients p ON tp.patient_id = p.id
        {where_clause}
        ORDER BY tp.criado_em DESC
    """
    pending_procs = query(query_sql, params)
    
    # Organiza os procedimentos em um dicionário agrupado pelo paciente: { patient_id: { 'patient_data': {...}, 'procedures': [...] } }
    grouped_patients = {}
    for row in pending_procs:
        pid = row['patient_id']
        if pid not in grouped_patients:
            grouped_patients[pid] = {
                'id': pid,
                'name': row['patient_name'],
                'cpf': row['patient_cpf'],
                'phone': row['patient_phone'],
                'procedures': []
            }
        grouped_patients[pid]['procedures'].append(row)
        
    patients_list = list(grouped_patients.values())
    
    return render_template('patients/pending_treatments.html', grouped_patients=patients_list, query=q)

@patients_bp.route('/<int:id>/exam/<int:exam_id>/validate', methods=['POST'])
@login_required
def validate_exam(id, exam_id):
    username = request.form.get('prof_username')
    password = request.form.get('prof_password')
    
    if not username or not password:
        flash('Usuário e senha são obrigatórios para validar o exame.', 'danger')
        return redirect(url_for('patients.view_patient', id=id))
        
    prof = query("SELECT id, password, role FROM users WHERE username = %s", (username,), one=True)
    
    # Apenas dentista ou admin podem validar exames
    if not prof or not check_password_hash(prof['password'], password) or prof['role'] not in [Role.DENTISTA, Role.ADMIN]:
        flash('Credenciais inválidas ou usuário sem permissão para validar exames.', 'danger')
        return redirect(url_for('patients.view_patient', id=id))
        
    try:
        execute('''
            UPDATE exams 
            SET professor_id = %s, data_validacao = CURRENT_TIMESTAMP
            WHERE id = %s AND patient_id = %s
        ''', (prof['id'], exam_id, id))
        flash('Exame validado pelo dentista com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao validar exame: {str(e)}', 'danger')
        
    return redirect(url_for('patients.view_patient', id=id))
