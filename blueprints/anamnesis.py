from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from database import execute, query

anamnesis_bp = Blueprint('anamnesis', __name__, url_prefix='/anamnesis')

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
            values.append(request.form.get(field))
            
        try:
            placeholders = ', '.join(['%s'] * len(fields))
            columns = ', '.join(fields)
            execute(f'INSERT INTO anamnesis ({columns}) VALUES ({placeholders})', values)
            flash('Anamnese salva com sucesso!', 'success')
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            flash(f'Erro ao salvar anamnese: {str(e)}', 'danger')

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
        SELECT a.*, p.nome as patient_name, p.cpf as patient_cpf, p.data_nascimento as patient_birth
        FROM anamnesis a
        JOIN patients p ON a.patient_id = p.id
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
    anamnesis = query("SELECT a.*, p.nome as patient_name FROM anamnesis a JOIN patients p ON a.patient_id = p.id WHERE a.id = %s", (id,), one=True)
    if not anamnesis:
        flash('Anamnese não encontrada.', 'danger')
        return redirect(url_for('anamnesis.list_completed'))

    if request.method == 'POST':
        password = request.form.get('confirm_password')
        user_data = query("SELECT password FROM users WHERE id = %s", (current_user.id,), one=True)
        
        if not check_password_hash(user_data['password'], password):
            flash('Senha de confirmação incorreta.', 'danger')
            return render_template('anamnesis/edit_anamnesis.html', a=anamnesis)

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
        values = [request.form.get(f) for f in fields]
        values.append(id)
        
        try:
            execute(f"UPDATE anamnesis SET {set_clause} WHERE id=%s", values)
            flash('Anamnese atualizada com sucesso!', 'success')
            return redirect(url_for('anamnesis.view_anamnesis', id=id))
        except Exception as e:
            flash(f'Erro ao atualizar: {str(e)}', 'danger')

    return render_template('anamnesis/edit_anamnesis.html', a=anamnesis)
