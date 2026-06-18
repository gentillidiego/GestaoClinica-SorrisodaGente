from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from database import execute, query
from werkzeug.security import check_password_hash
import json
import re
from constants import can_sign_clinical_document
from services.security_service import audit_log, permission_required
from services.sensitive_file_service import sensitive_file_response
from services.visual_media_service import build_exam_image_metadata
from services.google_drive_service import get_drive_service, ensure_patient_drive_folder, upload_file_in_memory, download_file_in_memory
import io
from flask import Response
import mimetypes

exams_bp = Blueprint('exams', __name__, url_prefix='/exams')

@exams_bp.route('/list/<int:anamnesis_id>')
@login_required
def list_exams(anamnesis_id):
    anamnesis = query("SELECT a.*, p.nome as patient_name FROM anamnesis a JOIN patients p ON a.patient_id = p.id WHERE a.id = %s", (anamnesis_id,), one=True)
    if not anamnesis:
        flash('Anamnese não encontrada.', 'danger')
        return redirect(url_for('anamnesis.search'))
    
    exams_list = query("SELECT * FROM exams WHERE anamnesis_id = %s ORDER BY data_criacao DESC", (anamnesis_id,))
    return render_template('exams/list.html', anamnesis=anamnesis, exams=exams_list)

@exams_bp.route('/check-anamnesis/<int:patient_id>')
@login_required
def check_anamnesis(patient_id):
    """Verifica se o paciente tem anamnese antes de criar exame."""
    anamnesis = query("SELECT id FROM anamnesis WHERE patient_id = %s ORDER BY id DESC LIMIT 1", (patient_id,), one=True)
    if not anamnesis:
        flash('Uma anamnese é necessária antes de realizar exames. Por favor, preencha o formulário abaixo.', 'warning')
        return redirect(url_for('anamnesis.form', patient_id=patient_id))
    
    return redirect(url_for('exams.select_type', anamnesis_id=anamnesis['id']))

@exams_bp.route('/create/<int:anamnesis_id>')
@login_required
def select_type(anamnesis_id):
    anamnesis = query("SELECT a.*, p.nome as patient_name FROM anamnesis a JOIN patients p ON a.patient_id = p.id WHERE a.id = %s", (anamnesis_id,), one=True)
    if not anamnesis:
        flash('Anamnese não encontrada.', 'danger')
        return redirect(url_for('anamnesis.search'))
        
    return render_template('exams/select_type.html', anamnesis=anamnesis)

# Placeholders para as rotas específicas que serão detalhadas pelo usuário
def _get_fisico_data():
    return (
        request.form.get('estado_geral'),
        request.form.get('peso_referido'),
        request.form.get('altura'),
        request.form.get('pulso'),
        request.form.get('freq_cardiaca'),
        request.form.get('pa_x'),
        request.form.get('lesao_presenca'),
        request.form.get('diagramas_pontos'),
        request.form.get('exame_extrabucal'),
        request.form.get('exame_intrabucal'),
        request.form.get('hipoteses_diagnosticas'),
        1 if 'imagem_periapical' in request.form else 0,
        1 if 'imagem_oclusal' in request.form else 0,
        1 if 'imagem_panoramica' in request.form else 0,
        1 if 'imagem_tomografia' in request.form else 0,
        request.form.get('imagem_outros'),
        request.form.get('imagem_resultado'),
        1 if 'hema_hemograma' in request.form else 0,
        1 if 'hema_coagulograma' in request.form else 0,
        1 if 'hema_glicemia' in request.form else 0,
        request.form.get('hema_outros'),
        request.form.get('hema_resultado'),
        1 if 'histo_incisional' in request.form else 0,
        1 if 'histo_excisional' in request.form else 0,
        request.form.get('diagnostico_definitivo')
    )

@exams_bp.route('/fisico/<int:anamnesis_id>', methods=['GET', 'POST'])
@exams_bp.route('/fisico/<int:anamnesis_id>/<int:exam_id>', methods=['GET', 'POST'])
@login_required
def fisico(anamnesis_id, exam_id=None):
    anamnesis = query("SELECT a.*, p.nome as patient_name FROM anamnesis a JOIN patients p ON a.patient_id = p.id WHERE a.id = %s", (anamnesis_id,), one=True)
    if not anamnesis:
        flash('Anamnese não encontrada.', 'danger')
        return redirect(url_for('anamnesis.search'))

    exam_data = None
    if exam_id:
        exam_data = query("SELECT * FROM exam_fisico WHERE exam_id = %s", (exam_id,), one=True)

    if request.method == 'POST':
        # Se for edição
        if exam_id:
            execute("""
                UPDATE exam_fisico SET 
                    estado_geral=%s, peso_referido=%s, altura=%s, pulso=%s, freq_cardiaca=%s, pa_x=%s, 
                    lesao_presenca=%s, diagramas_pontos=%s, exame_extrabucal=%s, exame_intrabucal=%s, 
                    hipoteses_diagnosticas=%s, imagem_periapical=%s, imagem_oclusal=%s, 
                    imagem_panoramica=%s, imagem_tomografia=%s, imagem_outros=%s, imagem_resultado=%s, 
                    hema_hemograma=%s, hema_coagulograma=%s, hema_glicemia=%s, hema_outros=%s, 
                    hema_resultado=%s, histo_incisional=%s, histo_excisional=%s, diagnostico_definitivo=%s
                WHERE exam_id=%s
            """, (*_get_fisico_data(), exam_id))
            flash('Exame Físico atualizado com sucesso!', 'success')
        else:
            # Criar novo
            new_exam_id = execute("INSERT INTO exams (anamnesis_id, patient_id, tipo) VALUES (%s, %s, %s) RETURNING id", 
                             (anamnesis_id, anamnesis['patient_id'], 'fisico'))
            
            execute("""
                INSERT INTO exam_fisico (
                    exam_id, estado_geral, peso_referido, altura, pulso, freq_cardiaca, pa_x, 
                    lesao_presenca, diagramas_pontos, exame_extrabucal, exame_intrabucal, 
                    hipoteses_diagnosticas, imagem_periapical, imagem_oclusal, 
                    imagem_panoramica, imagem_tomografia, imagem_outros, imagem_resultado, 
                    hema_hemograma, hema_coagulograma, hema_glicemia, hema_outros, 
                    hema_resultado, histo_incisional, histo_excisional, diagnostico_definitivo
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (new_exam_id, *_get_fisico_data()))
            flash('Exame Físico salvo com sucesso!', 'success')
        
        return redirect(url_for('patients.view_patient', id=anamnesis['patient_id']))

    return render_template('exams/fisico.html', anamnesis=anamnesis, exam_data=exam_data)

@exams_bp.route('/odontograma/<int:anamnesis_id>', methods=['GET', 'POST'])
@exams_bp.route('/odontograma/<int:anamnesis_id>/<int:exam_id>', methods=['GET', 'POST'])
@login_required
def odontograma(anamnesis_id, exam_id=None):
    anamnesis = query("SELECT a.*, p.nome as patient_name FROM anamnesis a JOIN patients p ON a.patient_id = p.id WHERE a.id = %s", (anamnesis_id,), one=True)
    if not anamnesis:
        flash('Anamnese não encontrada.', 'danger')
        return redirect(url_for('anamnesis.search'))

    exam_data = None
    if exam_id:
        exam_data = query("SELECT * FROM exam_odontograma WHERE exam_id = %s", (exam_id,), one=True)

    if request.method == 'POST':
        dentes_data = request.form.get('dentes_data')
        notas_dentes = request.form.get('notas_dentes')
        observacoes = request.form.get('observacoes')

        if exam_id:
            # Upsert logic: check if record exists in exam_odontograma
            exists = query("SELECT 1 FROM exam_odontograma WHERE exam_id = %s", (exam_id,), one=True)
            if exists:
                execute("UPDATE exam_odontograma SET dentes_data=%s, notas_dentes=%s, observacoes=%s WHERE exam_id=%s", 
                       (dentes_data, notas_dentes, observacoes, exam_id))
            else:
                execute("INSERT INTO exam_odontograma (exam_id, dentes_data, notas_dentes, observacoes) VALUES (%s, %s, %s, %s)", 
                       (exam_id, dentes_data, notas_dentes, observacoes))
            flash('Odontograma atualizado com sucesso!', 'success')
        else:
            # Criar novo
            new_exam_id = execute("INSERT INTO exams (anamnesis_id, patient_id, tipo) VALUES (%s, %s, %s) RETURNING id", 
                             (anamnesis_id, anamnesis['patient_id'], 'odontograma'))
            
            execute("INSERT INTO exam_odontograma (exam_id, dentes_data, notas_dentes, observacoes) VALUES (%s, %s, %s, %s)", 
                   (new_exam_id, dentes_data, notas_dentes, observacoes))
            flash('Odontograma salvo com sucesso!', 'success')
            exam_id = new_exam_id
        
        return redirect(url_for('patients.view_patient', id=anamnesis['patient_id']))

    return render_template('exams/odontograma.html', anamnesis=anamnesis, exam_data=exam_data)

@exams_bp.route('/controle_placa/<int:anamnesis_id>', methods=['GET', 'POST'])
@exams_bp.route('/controle_placa/<int:anamnesis_id>/<int:exam_id>', methods=['GET', 'POST'])
@login_required
def controle_placa(anamnesis_id, exam_id=None):
    anamnesis = query("SELECT a.*, p.nome as patient_name FROM anamnesis a JOIN patients p ON a.patient_id = p.id WHERE a.id = %s", (anamnesis_id,), one=True)
    if not anamnesis:
        flash('Anamnese não encontrada.', 'danger')
        return redirect(url_for('anamnesis.search'))

    exam_data = None
    if exam_id:
        exam_data = query("SELECT * FROM exam_controle_placa WHERE exam_id = %s", (exam_id,), one=True)

    if request.method == 'POST':
        data_faces = request.form.get('data_faces')
        num_dentes = request.form.get('num_dentes')
        num_faces_placa = request.form.get('num_faces_placa')
        indice_placa = request.form.get('indice_placa')
        psr_data = request.form.get('psr_data')
        condicao_periodontal = request.form.get('condicao_periodontal')

        if exam_id:
            execute("""
                UPDATE exam_controle_placa SET 
                    data_faces=%s, num_dentes=%s, num_faces_placa=%s, indice_placa=%s, 
                    psr_data=%s, condicao_periodontal=%s 
                WHERE exam_id=%s
            """, (data_faces, num_dentes, num_faces_placa, indice_placa, psr_data, condicao_periodontal, exam_id))
            flash('Controle de Placa atualizado!', 'success')
        else:
            new_exam_id = execute("INSERT INTO exams (anamnesis_id, patient_id, tipo) VALUES (%s, %s, %s) RETURNING id", 
                             (anamnesis_id, anamnesis['patient_id'], 'controle_placa'))
            execute("""
                INSERT INTO exam_controle_placa (
                    exam_id, data_faces, num_dentes, num_faces_placa, indice_placa, 
                    psr_data, condicao_periodontal
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (new_exam_id, data_faces, num_dentes, num_faces_placa, indice_placa, psr_data, condicao_periodontal))
            flash('Controle de Placa salvo!', 'success')
        
        return redirect(url_for('patients.view_patient', id=anamnesis['patient_id']))

    return render_template('exams/controle_placa.html', anamnesis=anamnesis, exam_data=exam_data)

# Lógica clínica extraída para módulo de serviço dedicado
from services.periodontal_diagnosis import determinar_grau_periodontal, calculate_periograma_diagnosis

@exams_bp.route('/periograma/<int:anamnesis_id>', methods=['GET', 'POST'])
@exams_bp.route('/periograma/<int:anamnesis_id>/<int:exam_id>', methods=['GET', 'POST'])
@login_required
def periograma(anamnesis_id, exam_id=None):
    anamnesis = query("SELECT a.*, p.nome as patient_name FROM anamnesis a JOIN patients p ON a.patient_id = p.id WHERE a.id = %s", (anamnesis_id,), one=True)
    if not anamnesis:
        flash('Anamnese não encontrada.', 'danger')
        return redirect(url_for('anamnesis.search'))

    exam_data = None
    if exam_id:
        exam_data = query("SELECT * FROM exam_periograma WHERE exam_id = %s", (exam_id,), one=True)

    if request.method == 'POST':
        fase = request.form.get('fase')
        medicoes_data = request.form.get('medicoes_data')
        diagnostico = request.form.get('diagnostico')

        if not medicoes_data:
            medicoes_data = "{}"
            
        ai_diag, ai_just = calculate_periograma_diagnosis(medicoes_data, anamnesis)
        ia_header = "DIAGNÓSTICO IA: "
        new_ia_text = f"{ia_header}{ai_diag}\nJUSTIFICATIVA: {ai_just}"

        if not diagnostico or diagnostico.strip() == "":
            diagnostico = new_ia_text
        else:
            # Se já existe um diagnóstico IA, vamos substituir pela versão atualizada
            if ia_header in diagnostico:
                # Tenta encontrar o bloco da IA (até o fim do texto ou próximo bloco)
                parts = re.split(f"({ia_header}.*)", diagnostico, flags=re.DOTALL)
                if len(parts) >= 2:
                    diagnostico = parts[0].strip() + ("\n\n" if parts[0].strip() else "") + new_ia_text
                else:
                    diagnostico = diagnostico + "\n\n" + new_ia_text
            else:
                # Apenas anexa se não encontrar o header
                diagnostico = diagnostico.strip() + "\n\n" + new_ia_text

        if exam_id:
            execute("UPDATE exam_periograma SET fase=%s, medicoes_data=%s, diagnostico=%s WHERE exam_id=%s", 
                   (fase, medicoes_data, diagnostico, exam_id))
            flash('Periograma atualizado!', 'success')
        else:
            new_exam_id = execute("INSERT INTO exams (anamnesis_id, patient_id, tipo) VALUES (%s, %s, %s) RETURNING id", 
                             (anamnesis_id, anamnesis['patient_id'], 'periograma'))
            execute("INSERT INTO exam_periograma (exam_id, fase, medicoes_data, diagnostico) VALUES (%s, %s, %s, %s)", 
                   (new_exam_id, fase, medicoes_data, diagnostico))
            flash('Periograma salvo!', 'success')
        
        return redirect(url_for('patients.view_patient', id=anamnesis['patient_id']))

    return render_template('exams/periograma.html', anamnesis=dict(anamnesis), exam_data=exam_data)

@exams_bp.route('/imagem/<int:anamnesis_id>', methods=['GET', 'POST'])
@exams_bp.route('/imagem/<int:anamnesis_id>/<int:exam_id>', methods=['GET', 'POST'])
@login_required
def imagem(anamnesis_id, exam_id=None):
    anamnesis = query("SELECT a.*, p.nome as patient_name FROM anamnesis a JOIN patients p ON a.patient_id = p.id WHERE a.id = %s", (anamnesis_id,), one=True)
    if not anamnesis:
        flash('Anamnese não encontrada.', 'danger')
        return redirect(url_for('anamnesis.search'))

    exam_data = None
    imagens = []
    if exam_id:
        exam_data = query("SELECT * FROM exam_imagem WHERE exam_id = %s", (exam_id,), one=True)
        imagens = query("SELECT * FROM exam_imagem_arquivos WHERE exam_id = %s ORDER BY data_upload ASC", (exam_id,))

    if request.method == 'POST':
        tipo_imagem = request.form.get('tipo_imagem')
        escopo = request.form.get('escopo')
        detalhe_escopo = request.form.get('detalhe_escopo', '')
        observacoes = request.form.get('observacoes', '')

        if not tipo_imagem or not escopo:
            flash('Tipo de Imagem e Escopo são obrigatórios.', 'warning')
            return redirect(request.url)

        resumo_clinico = f"{tipo_imagem} - {escopo}"
        if detalhe_escopo and escopo != 'Complexo Maxilomandibular':
            resumo_clinico += f" ({detalhe_escopo})"

        if exam_id:
            execute("UPDATE exam_imagem SET tipo_imagem=%s, escopo=%s, detalhe_escopo=%s, observacoes=%s WHERE exam_id=%s",
                    (tipo_imagem, escopo, detalhe_escopo, observacoes, exam_id))
            execute("UPDATE exams SET resumo_clinico=%s WHERE id=%s", (resumo_clinico, exam_id))
            flash('Exame de Imagem atualizado com sucesso!', 'success')
        else:
            new_exam_id = execute("INSERT INTO exams (anamnesis_id, patient_id, tipo, resumo_clinico) VALUES (%s, %s, %s, %s) RETURNING id",
                                  (anamnesis_id, anamnesis['patient_id'], 'imagem', resumo_clinico))
            execute("INSERT INTO exam_imagem (exam_id, tipo_imagem, escopo, detalhe_escopo, observacoes) VALUES (%s, %s, %s, %s, %s)",
                    (new_exam_id, tipo_imagem, escopo, detalhe_escopo, observacoes))
            flash('Exame de Imagem criado com sucesso!', 'success')
            exam_id = new_exam_id
        
        # Redireciona para a própria página para possibilitar o upload de imediato
        return redirect(url_for('exams.imagem', anamnesis_id=anamnesis_id, exam_id=exam_id))

    return render_template('exams/imagem.html', anamnesis=dict(anamnesis), exam_data=exam_data, imagens=imagens)

import os
import uuid
from werkzeug.utils import secure_filename
from flask import jsonify

@exams_bp.route('/imagem/<int:exam_id>/upload', methods=['POST'])
@login_required
def upload_imagem(exam_id):
    if 'images' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado.'}), 400
    
    files = request.files.getlist('images')
    if not files or files[0].filename == '':
        return jsonify({'error': 'Nenhum arquivo selecionado.'}), 400

    exam = query(
        """
        SELECT e.id, e.patient_id
        FROM exams e
        JOIN patients p ON p.id = e.patient_id
        WHERE e.id = %s
        """,
        (exam_id,),
        one=True,
    )
    if not exam:
        return jsonify({'error': 'Exame não encontrado.'}), 404

    metadata = build_exam_image_metadata(request.form)
    if not metadata['caption']:
        return jsonify({'error': 'A legenda da imagem é obrigatória.'}), 400

    allowed_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
    prepared_files = []
    for file in files:
        original_filename = secure_filename(file.filename)
        ext = os.path.splitext(original_filename)[1].lower()
        if ext not in allowed_extensions:
            return jsonify({'error': 'Formato inválido. Use JPG, PNG ou WEBP.'}), 400
        prepared_files.append((file, original_filename, ext))

    service = get_drive_service()
    folder_info = ensure_patient_drive_folder(exam['patient_id'], service)
    folder_id = folder_info['id']
    
    saved_files = []
    
    for file, original_filename, ext in prepared_files:
        if file:
            # Upload para o GDrive em memória
            drive_file = upload_file_in_memory(
                service=service,
                file_stream=file.stream,
                filename=original_filename,
                mime_type=file.mimetype,
                parent_id=folder_id
            )
            gdrive_file_id = f"gdrive://{drive_file['id']}"
            
            # Save to database
            arquivo_id = execute(
                """
                INSERT INTO exam_imagem_arquivos (
                    exam_id, patient_id, filename, file_path, visual_category,
                    caption, clinical_context, comparison_label, comparison_group,
                    taken_at, uploaded_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NULLIF(%s, '')::timestamp, %s)
                RETURNING id
                """,
                (
                    exam_id,
                    exam['patient_id'],
                    original_filename,
                    gdrive_file_id,
                    metadata['visual_category'],
                    metadata['caption'],
                    metadata['clinical_context'],
                    metadata['comparison_label'],
                    metadata['comparison_group'],
                    metadata['taken_at'] or '',
                    current_user.id,
                )
            )
            saved_files.append({
                'id': arquivo_id,
                'filename': original_filename,
                'url': url_for('exams.serve_imagem', arquivo_id=arquivo_id),
                'caption': metadata['caption'],
                'visual_category': metadata['visual_category'],
                'comparison_label': metadata['comparison_label'],
            })

    audit_log(
        action='visual_media_uploaded',
        module='visual_media',
        entity_type='exam_imagem_arquivos',
        entity_id=exam_id,
        patient_id=exam['patient_id'],
        details={
            'source': 'exam_image',
            'exam_id': exam_id,
            'files': [file_data['id'] for file_data in saved_files],
            'visual_category': metadata['visual_category'],
            'comparison_label': metadata['comparison_label'],
            'comparison_group': metadata['comparison_group'],
        },
    )
            
    return jsonify({'success': True, 'files': saved_files})

@exams_bp.route('/imagem/arquivo/<int:arquivo_id>')
@login_required
@permission_required('patients:view')
def serve_imagem(arquivo_id):
    arquivo = query(
        """
        SELECT a.*, e.patient_id
        FROM exam_imagem_arquivos a
        JOIN exams e ON e.id = a.exam_id
        JOIN patients p ON p.id = e.patient_id
        WHERE a.id = %s
          AND COALESCE(a.active, TRUE) = TRUE
        """,
        (arquivo_id,),
        one=True,
    )
    if not arquivo:
        return "Arquivo não encontrado", 404

    audit_log(
        action='visual_media_file_viewed',
        module='visual_media',
        entity_type='exam_imagem_arquivos',
        entity_id=arquivo_id,
        patient_id=arquivo['patient_id'],
        details={'filename': arquivo.get('filename'), 'caption': arquivo.get('caption')},
    )

    if str(arquivo['file_path']).startswith('gdrive://'):
        gdrive_id = str(arquivo['file_path']).replace('gdrive://', '')
        service = get_drive_service()
        try:
            file_bytes = download_file_in_memory(service, gdrive_id)
            mime_type, _ = mimetypes.guess_type(arquivo['filename'])
            return Response(file_bytes, mimetype=mime_type or 'application/octet-stream')
        except Exception as e:
            return f"Erro ao baixar arquivo do Drive: {str(e)}", 500
    else:
        if not os.path.exists(arquivo['file_path']):
            return "Arquivo local não encontrado", 404
        return sensitive_file_response(arquivo['file_path'])

@exams_bp.route('/delete/<int:exam_id>', methods=['POST'])
@login_required
def delete_exam(exam_id):
    # Verificação de login e senha (recebidos via POST)
    username = request.form.get('prof_username')
    password = request.form.get('prof_password')
    
    if not username or not password:
        flash('Usuário e senha são obrigatórios para exclusão.', 'danger')
        return redirect(request.referrer or url_for('patients.list'))
        
    # Validar usuário que está autorizando a exclusão
    prof = query("SELECT * FROM users WHERE username = %s", (username,), one=True)
    if not prof or not check_password_hash(prof['password'], password):
        flash('Usuário ou senha inválidos para autorização.', 'danger')
        return redirect(request.referrer or url_for('patients.list'))
        
    if not can_sign_clinical_document(prof['role']):
        flash('O usuário informado não tem permissão para excluir exames.', 'danger')
        return redirect(request.referrer or url_for('patients.list'))

    # Buscar o exame para garantir que existe e pegar o tipo
    exam = query("SELECT * FROM exams WHERE id = %s", (exam_id,), one=True)
    if not exam:
        flash('Exame não encontrado.', 'danger')
        return redirect(request.referrer or url_for('patients.list'))

    # Excluir dados específicos dependendo do tipo
    # (Embora FKs devam ser CASCADE, vamos garantir a limpeza manual se necessário)
    if exam['tipo'] == 'fisico':
        execute("DELETE FROM exam_fisico WHERE exam_id = %s", (exam_id,))
    elif exam['tipo'] == 'odontograma':
        execute("DELETE FROM exam_odontograma WHERE exam_id = %s", (exam_id,))
    elif exam['tipo'] == 'periograma':
        execute("DELETE FROM exam_periograma WHERE exam_id = %s", (exam_id,))
    elif exam['tipo'] == 'imagem':
        execute("DELETE FROM exam_imagem WHERE exam_id = %s", (exam_id,))

    # Excluir da tabela principal
    execute("DELETE FROM exams WHERE id = %s", (exam_id,))
    
    flash('Exame excluído com sucesso!', 'success')
    return redirect(request.referrer or url_for('patients.list'))
