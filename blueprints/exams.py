import io
import json
import mimetypes
import os
import re

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import login_required, current_user
from database import execute, query
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
from constants import can_sign_clinical_document
from services.security_service import audit_log, permission_required
from services.visual_media_service import build_exam_image_metadata
from services.clinical_lab_exam_service import (
    CLINICAL_LAB_EXAM_TYPES,
    CLINICAL_LAB_MAX_FILES,
    CLINICAL_LAB_MAX_FILE_SIZE,
    build_clinical_lab_caption,
    get_clinical_lab_exam_label,
    is_clinical_lab_image,
    prepare_clinical_lab_uploads,
)
from services.google_drive_service import get_drive_service
from services.exam_file_sync_service import (
    enqueue_exam_file_sync,
    get_exam_file_sync_status,
    remove_staged_file,
    stage_uploaded_file,
)
from services.protected_file_delivery_service import (
    ensure_cached_drive_file,
    get_or_create_image_derivative,
    protected_local_file_response,
)

exams_bp = Blueprint('exams', __name__, url_prefix='/exams')

IMAGE_EXAM_TYPE_RULES = {
    'Periapical': {'scope': 'Elemento', 'category': 'radiografia'},
    'Bite-wing': {'scope': 'Quadrante', 'category': 'radiografia'},
    'Oclusal': {'scope': 'Arcada', 'category': 'radiografia'},
    'Panorâmica': {'scope': 'Complexo Maxilomandibular', 'category': 'radiografia'},
    'Telerradiografia': {'scope': 'Complexo Maxilomandibular', 'category': 'radiografia'},
    'Tomografia': {'scope': 'Complexo Maxilomandibular', 'category': 'cbct'},
    'Ultrassonografia': {'scope': 'Outro', 'category': 'documento_complementar'},
    'Ressonância': {'scope': 'Outro', 'category': 'documento_complementar'},
    'Fotografia Clínica': {'scope': 'Outro', 'category': 'intraoral'},
    'Outro': {'scope': 'Outro', 'category': 'documento_complementar'},
}
IMAGE_UPLOAD_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
IMAGE_UPLOAD_MAX_FILES = 12
IMAGE_UPLOAD_MAX_FILE_SIZE = 25 * 1024 * 1024


def infer_image_exam_scope(tipo_imagem):
    """Escolhe um escopo clínico seguro sem obrigar o usuário a preencher outro campo."""
    return IMAGE_EXAM_TYPE_RULES.get(tipo_imagem, IMAGE_EXAM_TYPE_RULES['Outro'])['scope']


def infer_image_visual_category(tipo_imagem):
    return IMAGE_EXAM_TYPE_RULES.get(tipo_imagem, IMAGE_EXAM_TYPE_RULES['Outro'])['category']


def build_image_upload_caption(tipo_imagem, filename, supplied_caption=None):
    caption = str(supplied_caption or '').strip()
    return caption or f'{tipo_imagem or "Exame de imagem"} — {filename}'


def image_count_label(total, *, saved=False):
    noun = 'imagem' if total == 1 else 'imagens'
    if not saved:
        return f'{total} {noun}'
    adjective = 'salva' if total == 1 else 'salvas'
    return f'{total} {noun} {adjective}'


def _wants_json_response():
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or request.accept_mimetypes.best == 'application/json'
    )


def _uploaded_file_size(file):
    declared_size = getattr(file, 'content_length', None)
    if declared_size:
        return declared_size
    try:
        position = file.stream.tell()
        file.stream.seek(0, os.SEEK_END)
        size = file.stream.tell()
        file.stream.seek(position)
        return size
    except (AttributeError, OSError):
        return None


def prepare_image_uploads(files):
    """Valida o lote inteiro antes de iniciar qualquer gravação no Drive."""
    valid_files = [file for file in files if file and file.filename]
    if not valid_files:
        raise ValueError('Selecione pelo menos uma imagem.')
    if len(valid_files) > IMAGE_UPLOAD_MAX_FILES:
        raise ValueError(f'Envie no máximo {IMAGE_UPLOAD_MAX_FILES} imagens por vez.')

    prepared_files = []
    for index, file in enumerate(valid_files, start=1):
        safe_name = secure_filename(file.filename)
        ext = os.path.splitext(safe_name)[1].lower()
        if ext not in IMAGE_UPLOAD_EXTENSIONS:
            raise ValueError(
                f'O arquivo “{file.filename}” não é compatível. Use JPG, PNG ou WEBP.'
            )

        mime_type = (file.mimetype or '').lower()
        if mime_type and mime_type != 'application/octet-stream' and not mime_type.startswith('image/'):
            raise ValueError(f'O arquivo “{file.filename}” não foi reconhecido como imagem.')

        size = _uploaded_file_size(file)
        if size is not None and size > IMAGE_UPLOAD_MAX_FILE_SIZE:
            raise ValueError(f'O arquivo “{file.filename}” ultrapassa o limite de 25 MB.')

        if not safe_name:
            safe_name = f'imagem-{index}{ext}'
        prepared_files.append((file, safe_name, ext, file.filename))
    return prepared_files

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
        wants_json = _wants_json_response()
        tipo_imagem = (request.form.get('tipo_imagem') or '').strip()
        escopo = (request.form.get('escopo') or '').strip() or infer_image_exam_scope(tipo_imagem)
        detalhe_escopo = (request.form.get('detalhe_escopo') or '').strip()
        observacoes = (request.form.get('observacoes') or '').strip()

        if tipo_imagem not in IMAGE_EXAM_TYPE_RULES:
            message = 'Selecione um tipo de exame de imagem válido.'
            if wants_json:
                return jsonify({'success': False, 'error': message}), 400
            flash(message, 'warning')
            return redirect(request.url)

        resumo_clinico = f"{tipo_imagem} - {escopo}"
        if detalhe_escopo and escopo != 'Complexo Maxilomandibular':
            resumo_clinico += f" ({detalhe_escopo})"

        if exam_id:
            execute("UPDATE exam_imagem SET tipo_imagem=%s, escopo=%s, detalhe_escopo=%s, observacoes=%s WHERE exam_id=%s",
                    (tipo_imagem, escopo, detalhe_escopo, observacoes, exam_id))
            execute("UPDATE exams SET resumo_clinico=%s WHERE id=%s", (resumo_clinico, exam_id))
            if not wants_json:
                flash('Exame de Imagem atualizado com sucesso!', 'success')
        else:
            new_exam_id = execute("INSERT INTO exams (anamnesis_id, patient_id, tipo, resumo_clinico) VALUES (%s, %s, %s, %s) RETURNING id",
                                  (anamnesis_id, anamnesis['patient_id'], 'imagem', resumo_clinico))
            execute("INSERT INTO exam_imagem (exam_id, tipo_imagem, escopo, detalhe_escopo, observacoes) VALUES (%s, %s, %s, %s, %s)",
                    (new_exam_id, tipo_imagem, escopo, detalhe_escopo, observacoes))
            if not wants_json:
                flash('Exame de Imagem criado com sucesso!', 'success')
            exam_id = new_exam_id

        if wants_json:
            return jsonify({
                'success': True,
                'exam_id': exam_id,
                'upload_url': url_for('exams.upload_imagem', exam_id=exam_id),
                'view_url': url_for(
                    'exams.imagem',
                    anamnesis_id=anamnesis_id,
                    exam_id=exam_id,
                ),
                'message': 'Dados do exame salvos.',
            })
        
        # Redireciona para a própria página para possibilitar o upload de imediato
        return redirect(url_for('exams.imagem', anamnesis_id=anamnesis_id, exam_id=exam_id))

    return render_template('exams/imagem.html', anamnesis=dict(anamnesis), exam_data=exam_data, imagens=imagens)

@exams_bp.route('/imagem/<int:exam_id>/upload', methods=['POST'])
@login_required
def upload_imagem(exam_id):
    max_batch_size = (IMAGE_UPLOAD_MAX_FILES * IMAGE_UPLOAD_MAX_FILE_SIZE) + (2 * 1024 * 1024)
    if request.content_length and request.content_length > max_batch_size:
        return jsonify({
            'success': False,
            'error': (
                f'O lote ultrapassa o limite permitido. Envie no máximo '
                f'{IMAGE_UPLOAD_MAX_FILES} imagens de até 25 MB cada.'
            ),
        }), 413

    if 'images' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado.'}), 400
    
    files = request.files.getlist('images')
    if not files or files[0].filename == '':
        return jsonify({'error': 'Nenhum arquivo selecionado.'}), 400

    exam = query(
        """
        SELECT e.id, e.patient_id, ei.tipo_imagem
        FROM exams e
        JOIN exam_imagem ei ON ei.exam_id = e.id
        JOIN patients p ON p.id = e.patient_id
        WHERE e.id = %s
        """,
        (exam_id,),
        one=True,
    )
    if not exam:
        return jsonify({'error': 'Exame não encontrado.'}), 404

    metadata = build_exam_image_metadata(request.form)
    if not request.form.get('visual_category'):
        metadata['visual_category'] = infer_image_visual_category(exam['tipo_imagem'])

    try:
        prepared_files = prepare_image_uploads(files)
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400

    saved_files = []
    failed_files = []
    
    for file, original_filename, _ext, client_filename in prepared_files:
        staged_path = None
        try:
            staged_path = stage_uploaded_file(
                file,
                'exam_image',
                exam['patient_id'],
                exam_id,
                original_filename,
            )
            caption = build_image_upload_caption(
                exam['tipo_imagem'],
                original_filename,
                metadata['caption'],
            )
            
            # Save to database
            arquivo_id = execute(
                """
                INSERT INTO exam_imagem_arquivos (
                    exam_id, patient_id, filename, file_path, visual_category,
                    caption, clinical_context, comparison_label, comparison_group,
                    taken_at, uploaded_by, staging_path, storage_status,
                    storage_updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    NULLIF(%s, '')::timestamp, %s, %s, 'pending', NOW()
                )
                RETURNING id
                """,
                (
                    exam_id,
                    exam['patient_id'],
                    original_filename,
                    staged_path,
                    metadata['visual_category'],
                    caption,
                    metadata['clinical_context'],
                    metadata['comparison_label'],
                    metadata['comparison_group'],
                    metadata['taken_at'] or '',
                    current_user.id,
                    staged_path,
                )
            )
            try:
                enqueue_exam_file_sync('exam_image', arquivo_id)
            except Exception as exc:
                current_app.logger.exception(
                    'Imagem %s salva localmente, mas ainda não reenfileirada',
                    arquivo_id,
                )
                try:
                    execute(
                        """
                        UPDATE exam_imagem_arquivos
                        SET storage_error = %s,
                            storage_updated_at = NOW()
                        WHERE id = %s
                        """,
                        (f'Aguardando reconciliação automática: {str(exc)[-500:]}', arquivo_id),
                    )
                except Exception:
                    current_app.logger.exception(
                        'Falha ao registrar espera de sincronização da imagem %s',
                        arquivo_id,
                    )
            saved_files.append({
                'id': arquivo_id,
                'filename': original_filename,
                'client_filename': client_filename,
                'url': url_for('exams.serve_imagem', arquivo_id=arquivo_id),
                'thumbnail_url': url_for(
                    'exams.serve_imagem_thumbnail',
                    arquivo_id=arquivo_id,
                ),
                'preview_url': url_for(
                    'exams.serve_imagem_preview',
                    arquivo_id=arquivo_id,
                ),
                'caption': caption,
                'visual_category': metadata['visual_category'],
                'comparison_label': metadata['comparison_label'],
                'storage_status': 'pending',
                'storage_label': 'Salva no prontuário · sincronizando com o Drive',
                'status_url': url_for(
                    'exams.status_imagem_arquivo',
                    arquivo_id=arquivo_id,
                ),
            })
        except Exception:
            current_app.logger.exception(
                'Falha no upload do arquivo %s para o exame %s',
                original_filename,
                exam_id,
            )
            if staged_path:
                remove_staged_file(staged_path)
            failed_files.append({
                'filename': original_filename,
                'client_filename': client_filename,
                'error': 'Não foi possível salvar esta imagem.',
            })

    if saved_files:
        try:
            audit_log(
                action='visual_media_staged',
                module='visual_media',
                entity_type='exam_imagem_arquivos',
                entity_id=exam_id,
                patient_id=exam['patient_id'],
                details={
                    'source': 'exam_image',
                    'exam_id': exam_id,
                    'files': [file_data['id'] for file_data in saved_files],
                    'failed_files': [file_data['filename'] for file_data in failed_files],
                    'visual_category': metadata['visual_category'],
                    'comparison_label': metadata['comparison_label'],
                    'comparison_group': metadata['comparison_group'],
                    'storage_status': 'pending',
                },
            )
        except Exception:
            current_app.logger.exception(
                'Falha ao registrar auditoria do staging do exame de imagem %s',
                exam_id,
            )

    if failed_files:
        status_code = 207 if saved_files else 502
        return jsonify({
            'success': False,
            'partial': bool(saved_files),
            'files': saved_files,
            'failed_files': failed_files,
            'error': (
                f'{image_count_label(len(saved_files), saved=True)}; '
                f'{image_count_label(len(failed_files))} '
                f'{"não concluída" if len(failed_files) == 1 else "não concluídas"}.'
                if saved_files
                else 'Não foi possível salvar as imagens. Tente novamente.'
            ),
        }), status_code

    return jsonify({
        'success': True,
        'files': saved_files,
        'total': len(saved_files),
        'message': (
            f'{image_count_label(len(saved_files), saved=True)} no prontuário. '
            'A cópia para o Google Drive continuará em segundo plano.'
        ),
    })


@exams_bp.route('/imagem/arquivo/<int:arquivo_id>/status')
@login_required
@permission_required('patients:view')
def status_imagem_arquivo(arquivo_id):
    status = get_exam_file_sync_status('exam_image', arquivo_id)
    if not status:
        return jsonify({'success': False, 'error': 'Arquivo não encontrado.'}), 404
    return jsonify({'success': True, **status})


def _resolve_exam_file_original(arquivo):
    for candidate in (
        arquivo.get('staging_path'),
        arquivo.get('file_path'),
    ):
        if candidate and not str(candidate).startswith('gdrive://') and os.path.isfile(candidate):
            return candidate

    file_path = str(arquivo.get('file_path') or '')
    if file_path.startswith('gdrive://'):
        drive_id = file_path.replace('gdrive://', '', 1)
        return ensure_cached_drive_file(get_drive_service(), drive_id)
    return None


def _get_image_exam_file(arquivo_id):
    return query(
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


@exams_bp.route('/imagem/arquivo/<int:arquivo_id>/thumbnail')
@login_required
@permission_required('patients:view')
def serve_imagem_thumbnail(arquivo_id):
    arquivo = _get_image_exam_file(arquivo_id)
    if not arquivo:
        return 'Arquivo não encontrado', 404
    try:
        original_path = _resolve_exam_file_original(arquivo)
        derivative = get_or_create_image_derivative(
            'exam_image',
            arquivo_id,
            'thumbnail',
            original_path,
        )
        return protected_local_file_response(
            derivative,
            mimetype='image/webp',
            download_name=f'thumbnail-{arquivo["filename"]}.webp',
            max_age=7 * 86400,
        )
    except Exception:
        current_app.logger.exception('Falha ao gerar miniatura da imagem %s', arquivo_id)
        return 'Miniatura indisponível', 502


@exams_bp.route('/imagem/arquivo/<int:arquivo_id>/preview')
@login_required
@permission_required('patients:view')
def serve_imagem_preview(arquivo_id):
    arquivo = _get_image_exam_file(arquivo_id)
    if not arquivo:
        return 'Arquivo não encontrado', 404
    try:
        original_path = _resolve_exam_file_original(arquivo)
        derivative = get_or_create_image_derivative(
            'exam_image',
            arquivo_id,
            'preview',
            original_path,
        )
        return protected_local_file_response(
            derivative,
            mimetype='image/webp',
            download_name=f'preview-{arquivo["filename"]}.webp',
            max_age=7 * 86400,
        )
    except Exception:
        current_app.logger.exception('Falha ao gerar prévia da imagem %s', arquivo_id)
        return 'Prévia indisponível', 502


@exams_bp.route('/imagem/arquivo/<int:arquivo_id>')
@login_required
@permission_required('patients:view')
def serve_imagem(arquivo_id):
    arquivo = _get_image_exam_file(arquivo_id)
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

    try:
        original_path = _resolve_exam_file_original(arquivo)
        if not original_path:
            return 'Arquivo não encontrado', 404
        mime_type, _ = mimetypes.guess_type(arquivo['filename'])
        return protected_local_file_response(
            original_path,
            mimetype=mime_type or 'application/octet-stream',
            download_name=arquivo['filename'],
            max_age=86400,
        )
    except Exception:
        current_app.logger.exception('Falha ao abrir imagem original %s', arquivo_id)
        return 'Não foi possível abrir o arquivo.', 502


def _clinical_lab_file_count_label(total, *, saved=False):
    noun = 'arquivo' if total == 1 else 'arquivos'
    if not saved:
        return f'{total} {noun}'
    adjective = 'salvo' if total == 1 else 'salvos'
    return f'{total} {noun} {adjective}'


@exams_bp.route('/clinico-laboratorial/<int:anamnesis_id>', methods=['GET', 'POST'])
@exams_bp.route(
    '/clinico-laboratorial/<int:anamnesis_id>/<int:exam_id>',
    methods=['GET', 'POST'],
)
@login_required
def clinico_laboratorial(anamnesis_id, exam_id=None):
    anamnesis = query(
        """
        SELECT a.*, p.nome AS patient_name
        FROM anamnesis a
        JOIN patients p ON p.id = a.patient_id
        WHERE a.id = %s
        """,
        (anamnesis_id,),
        one=True,
    )
    if not anamnesis:
        flash('Anamnese não encontrada.', 'danger')
        return redirect(url_for('anamnesis.search'))

    exam_data = None
    arquivos = []
    if exam_id:
        exam_data = query(
            """
            SELECT cl.*
            FROM exam_clinico_laboratorial cl
            JOIN exams e ON e.id = cl.exam_id
            WHERE cl.exam_id = %s
              AND e.anamnesis_id = %s
            """,
            (exam_id, anamnesis_id),
            one=True,
        )
        if not exam_data:
            flash('Exame clínico/laboratorial não encontrado.', 'danger')
            return redirect(url_for('patients.view_patient', id=anamnesis['patient_id']))
        arquivo_rows = query(
            """
            SELECT *
            FROM exam_clinico_laboratorial_arquivos
            WHERE exam_id = %s
              AND COALESCE(active, TRUE) = TRUE
            ORDER BY data_upload ASC, id ASC
            """,
            (exam_id,),
        )
        arquivos = []
        for row in arquivo_rows:
            item = dict(row)
            item['is_image'] = is_clinical_lab_image(
                item.get('filename'),
                item.get('mime_type'),
            )
            arquivos.append(item)

    if request.method == 'POST':
        wants_json = _wants_json_response()
        categoria = (request.form.get('categoria') or '').strip()
        laboratorio = (request.form.get('laboratorio') or '').strip()
        data_coleta = (request.form.get('data_coleta') or '').strip()
        observacoes = (request.form.get('observacoes') or '').strip()

        if categoria not in CLINICAL_LAB_EXAM_TYPES:
            message = 'Selecione um tipo de exame clínico/laboratorial válido.'
            if wants_json:
                return jsonify({'success': False, 'error': message}), 400
            flash(message, 'warning')
            return redirect(request.url)

        resumo_clinico = get_clinical_lab_exam_label(categoria)
        if laboratorio:
            resumo_clinico += f' — {laboratorio}'

        if exam_id:
            execute(
                """
                UPDATE exam_clinico_laboratorial
                SET categoria = %s,
                    laboratorio = %s,
                    data_coleta = NULLIF(%s, '')::date,
                    observacoes = %s
                WHERE exam_id = %s
                """,
                (categoria, laboratorio, data_coleta, observacoes, exam_id),
            )
            execute(
                "UPDATE exams SET resumo_clinico = %s WHERE id = %s",
                (resumo_clinico, exam_id),
            )
            if not wants_json:
                flash('Exame clínico/laboratorial atualizado com sucesso!', 'success')
        else:
            exam_id = execute(
                """
                INSERT INTO exams (anamnesis_id, patient_id, tipo, resumo_clinico)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (
                    anamnesis_id,
                    anamnesis['patient_id'],
                    'clinico_laboratorial',
                    resumo_clinico,
                ),
            )
            execute(
                """
                INSERT INTO exam_clinico_laboratorial (
                    exam_id, categoria, laboratorio, data_coleta, observacoes
                )
                VALUES (%s, %s, %s, NULLIF(%s, '')::date, %s)
                """,
                (exam_id, categoria, laboratorio, data_coleta, observacoes),
            )
            if not wants_json:
                flash('Exame clínico/laboratorial criado com sucesso!', 'success')

        if wants_json:
            return jsonify({
                'success': True,
                'exam_id': exam_id,
                'upload_url': url_for(
                    'exams.upload_clinico_laboratorial',
                    exam_id=exam_id,
                ),
                'view_url': url_for(
                    'exams.clinico_laboratorial',
                    anamnesis_id=anamnesis_id,
                    exam_id=exam_id,
                ),
                'message': 'Dados do exame salvos.',
            })

        return redirect(
            url_for(
                'exams.clinico_laboratorial',
                anamnesis_id=anamnesis_id,
                exam_id=exam_id,
            )
        )

    return render_template(
        'exams/clinico_laboratorial.html',
        anamnesis=dict(anamnesis),
        exam_data=exam_data,
        arquivos=arquivos,
        exam_types=CLINICAL_LAB_EXAM_TYPES,
    )


@exams_bp.route('/clinico-laboratorial/<int:exam_id>/upload', methods=['POST'])
@login_required
def upload_clinico_laboratorial(exam_id):
    max_batch_size = (
        CLINICAL_LAB_MAX_FILES * CLINICAL_LAB_MAX_FILE_SIZE
    ) + (2 * 1024 * 1024)
    if request.content_length and request.content_length > max_batch_size:
        return jsonify({
            'success': False,
            'error': (
                f'O lote ultrapassa o limite permitido. Envie no máximo '
                f'{CLINICAL_LAB_MAX_FILES} arquivos de até 25 MB cada.'
            ),
        }), 413

    if 'files' not in request.files:
        return jsonify({'success': False, 'error': 'Nenhum arquivo enviado.'}), 400
    files = request.files.getlist('files')

    exam = query(
        """
        SELECT e.id, e.patient_id, cl.categoria
        FROM exams e
        JOIN exam_clinico_laboratorial cl ON cl.exam_id = e.id
        JOIN patients p ON p.id = e.patient_id
        WHERE e.id = %s
        """,
        (exam_id,),
        one=True,
    )
    if not exam:
        return jsonify({'success': False, 'error': 'Exame não encontrado.'}), 404

    try:
        prepared_files = prepare_clinical_lab_uploads(files)
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400

    supplied_caption = (request.form.get('caption') or '').strip()
    saved_files = []
    failed_files = []

    for file, filename, _extension, client_filename in prepared_files:
        staged_path = None
        try:
            guessed_mime_type = mimetypes.guess_type(filename)[0]
            mime_type = file.mimetype
            if not mime_type or mime_type == 'application/octet-stream':
                mime_type = guessed_mime_type or 'application/octet-stream'
            staged_path = stage_uploaded_file(
                file,
                'clinical_lab',
                exam['patient_id'],
                exam_id,
                filename,
            )
            caption = build_clinical_lab_caption(
                exam['categoria'],
                filename,
                supplied_caption,
            )
            arquivo_id = execute(
                """
                INSERT INTO exam_clinico_laboratorial_arquivos (
                    exam_id, patient_id, filename, file_path, mime_type,
                    caption, uploaded_by, staging_path, storage_status,
                    storage_updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', NOW())
                RETURNING id
                """,
                (
                    exam_id,
                    exam['patient_id'],
                    filename,
                    staged_path,
                    mime_type,
                    caption,
                    current_user.id,
                    staged_path,
                ),
            )
            try:
                enqueue_exam_file_sync('clinical_lab', arquivo_id)
            except Exception as exc:
                current_app.logger.exception(
                    'Laudo %s salvo localmente, mas ainda não reenfileirado',
                    arquivo_id,
                )
                try:
                    execute(
                        """
                        UPDATE exam_clinico_laboratorial_arquivos
                        SET storage_error = %s,
                            storage_updated_at = NOW()
                        WHERE id = %s
                        """,
                        (f'Aguardando reconciliação automática: {str(exc)[-500:]}', arquivo_id),
                    )
                except Exception:
                    current_app.logger.exception(
                        'Falha ao registrar espera de sincronização do laudo %s',
                        arquivo_id,
                    )
            saved_files.append({
                'id': arquivo_id,
                'filename': filename,
                'client_filename': client_filename,
                'caption': caption,
                'mime_type': mime_type,
                'is_image': is_clinical_lab_image(filename, mime_type),
                'url': url_for(
                    'exams.serve_clinico_laboratorial_arquivo',
                    arquivo_id=arquivo_id,
                ),
                'thumbnail_url': (
                    url_for(
                        'exams.serve_clinico_laboratorial_thumbnail',
                        arquivo_id=arquivo_id,
                    )
                    if is_clinical_lab_image(filename, mime_type)
                    else None
                ),
                'preview_url': (
                    url_for(
                        'exams.serve_clinico_laboratorial_preview',
                        arquivo_id=arquivo_id,
                    )
                    if is_clinical_lab_image(filename, mime_type)
                    else None
                ),
                'storage_status': 'pending',
                'storage_label': 'Salvo no prontuário · sincronizando com o Drive',
                'status_url': url_for(
                    'exams.status_clinico_laboratorial_arquivo',
                    arquivo_id=arquivo_id,
                ),
            })
        except Exception:
            current_app.logger.exception(
                'Falha no upload do arquivo %s para o exame clínico/laboratorial %s',
                filename,
                exam_id,
            )
            if staged_path:
                remove_staged_file(staged_path)
            failed_files.append({
                'filename': filename,
                'client_filename': client_filename,
                'error': 'Não foi possível salvar este arquivo.',
            })

    if saved_files:
        try:
            audit_log(
                action='clinical_lab_files_uploaded',
                module='clinical_lab_exam',
                entity_type='exam_clinico_laboratorial_arquivos',
                entity_id=exam_id,
                patient_id=exam['patient_id'],
                details={
                    'exam_id': exam_id,
                    'category': exam['categoria'],
                    'files': [item['id'] for item in saved_files],
                    'failed_files': [item['filename'] for item in failed_files],
                    'storage_status': 'pending',
                },
            )
        except Exception:
            current_app.logger.exception(
                'Falha ao registrar auditoria do exame clínico/laboratorial %s',
                exam_id,
            )

    if failed_files:
        status_code = 207 if saved_files else 502
        failed_label = _clinical_lab_file_count_label(len(failed_files))
        return jsonify({
            'success': False,
            'partial': bool(saved_files),
            'files': saved_files,
            'failed_files': failed_files,
            'error': (
                f'{_clinical_lab_file_count_label(len(saved_files), saved=True)}; '
                f'{failed_label} '
                f'{"não concluído" if len(failed_files) == 1 else "não concluídos"}.'
                if saved_files
                else 'Não foi possível salvar os arquivos. Tente novamente.'
            ),
        }), status_code

    return jsonify({
        'success': True,
        'files': saved_files,
        'total': len(saved_files),
        'message': (
            f'{_clinical_lab_file_count_label(len(saved_files), saved=True)} '
            'no prontuário. A cópia para o Google Drive continuará em segundo plano.'
        ),
    })


@exams_bp.route('/clinico-laboratorial/arquivo/<int:arquivo_id>/status')
@login_required
@permission_required('patients:view')
def status_clinico_laboratorial_arquivo(arquivo_id):
    status = get_exam_file_sync_status('clinical_lab', arquivo_id)
    if not status:
        return jsonify({'success': False, 'error': 'Arquivo não encontrado.'}), 404
    return jsonify({'success': True, **status})


def _get_clinical_lab_file(arquivo_id):
    return query(
        """
        SELECT a.*, e.patient_id
        FROM exam_clinico_laboratorial_arquivos a
        JOIN exams e ON e.id = a.exam_id
        WHERE a.id = %s
          AND COALESCE(a.active, TRUE) = TRUE
        """,
        (arquivo_id,),
        one=True,
    )


@exams_bp.route(
    '/clinico-laboratorial/arquivo/<int:arquivo_id>/thumbnail'
)
@login_required
@permission_required('patients:view')
def serve_clinico_laboratorial_thumbnail(arquivo_id):
    arquivo = _get_clinical_lab_file(arquivo_id)
    if not arquivo or not is_clinical_lab_image(
        arquivo.get('filename'),
        arquivo.get('mime_type'),
    ):
        return 'Imagem não encontrada', 404
    try:
        original_path = _resolve_exam_file_original(arquivo)
        derivative = get_or_create_image_derivative(
            'clinical_lab',
            arquivo_id,
            'thumbnail',
            original_path,
        )
        return protected_local_file_response(
            derivative,
            mimetype='image/webp',
            download_name=f'thumbnail-{arquivo["filename"]}.webp',
            max_age=7 * 86400,
        )
    except Exception:
        current_app.logger.exception(
            'Falha ao gerar miniatura do laudo %s',
            arquivo_id,
        )
        return 'Miniatura indisponível', 502


@exams_bp.route(
    '/clinico-laboratorial/arquivo/<int:arquivo_id>/preview'
)
@login_required
@permission_required('patients:view')
def serve_clinico_laboratorial_preview(arquivo_id):
    arquivo = _get_clinical_lab_file(arquivo_id)
    if not arquivo or not is_clinical_lab_image(
        arquivo.get('filename'),
        arquivo.get('mime_type'),
    ):
        return 'Imagem não encontrada', 404
    try:
        original_path = _resolve_exam_file_original(arquivo)
        derivative = get_or_create_image_derivative(
            'clinical_lab',
            arquivo_id,
            'preview',
            original_path,
        )
        return protected_local_file_response(
            derivative,
            mimetype='image/webp',
            download_name=f'preview-{arquivo["filename"]}.webp',
            max_age=7 * 86400,
        )
    except Exception:
        current_app.logger.exception(
            'Falha ao gerar prévia do laudo %s',
            arquivo_id,
        )
        return 'Prévia indisponível', 502


@exams_bp.route('/clinico-laboratorial/arquivo/<int:arquivo_id>')
@login_required
@permission_required('patients:view')
def serve_clinico_laboratorial_arquivo(arquivo_id):
    arquivo = _get_clinical_lab_file(arquivo_id)
    if not arquivo:
        return 'Arquivo não encontrado', 404

    audit_log(
        action='clinical_lab_file_viewed',
        module='clinical_lab_exam',
        entity_type='exam_clinico_laboratorial_arquivos',
        entity_id=arquivo_id,
        patient_id=arquivo['patient_id'],
        details={
            'filename': arquivo.get('filename'),
            'caption': arquivo.get('caption'),
        },
    )

    mime_type = arquivo.get('mime_type')
    if not mime_type or mime_type == 'application/octet-stream':
        mime_type = (
            mimetypes.guess_type(arquivo['filename'])[0]
            or 'application/octet-stream'
        )
    try:
        original_path = _resolve_exam_file_original(arquivo)
        if not original_path:
            return 'Arquivo não encontrado', 404
        return protected_local_file_response(
            original_path,
            mimetype=mime_type,
            as_attachment=False,
            download_name=arquivo['filename'],
            max_age=86400,
        )
    except Exception:
        current_app.logger.exception(
            'Falha ao abrir arquivo clínico/laboratorial %s',
            arquivo_id,
        )
        return 'Não foi possível abrir o arquivo.', 502


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
    elif exam['tipo'] == 'clinico_laboratorial':
        execute(
            "DELETE FROM exam_clinico_laboratorial WHERE exam_id = %s",
            (exam_id,),
        )

    # Excluir da tabela principal
    execute("DELETE FROM exams WHERE id = %s", (exam_id,))
    
    flash('Exame excluído com sucesso!', 'success')
    return redirect(request.referrer or url_for('patients.list'))
