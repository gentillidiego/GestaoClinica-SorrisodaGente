import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen

from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash
from database import execute, query, execute_transaction
from constants import CLINICAL_EXECUTOR_ROLES, can_sign_clinical_document
from services.security_service import audit_log, permission_required
from services.sensitive_file_service import sensitive_file_response
from services.signature_evidence_service import (
    A_ROGO_DECLARATION,
    SIGNATURE_MARKER_A_ROGO,
    SIGNATURE_MODE_A_ROGO,
    SIGNATURE_MODE_CANVAS,
    build_atendimento_payload,
    build_tcle_payload,
    collect_a_rogo_witnesses,
    json_dumps,
    register_signature_event,
    validate_a_rogo_signer,
    wants_a_rogo,
)
import math
import os
from datetime import datetime

patients_bp = Blueprint('patients', __name__, url_prefix='/patients')

BRAZIL_STATES = [
    ('AL', 'Alagoas'),
    ('AC', 'Acre'),
    ('AP', 'Amapá'),
    ('AM', 'Amazonas'),
    ('BA', 'Bahia'),
    ('CE', 'Ceará'),
    ('DF', 'Distrito Federal'),
    ('ES', 'Espírito Santo'),
    ('GO', 'Goiás'),
    ('MA', 'Maranhão'),
    ('MT', 'Mato Grosso'),
    ('MS', 'Mato Grosso do Sul'),
    ('MG', 'Minas Gerais'),
    ('PA', 'Pará'),
    ('PB', 'Paraíba'),
    ('PR', 'Paraná'),
    ('PE', 'Pernambuco'),
    ('PI', 'Piauí'),
    ('RJ', 'Rio de Janeiro'),
    ('RN', 'Rio Grande do Norte'),
    ('RS', 'Rio Grande do Sul'),
    ('RO', 'Rondônia'),
    ('RR', 'Roraima'),
    ('SC', 'Santa Catarina'),
    ('SP', 'São Paulo'),
    ('SE', 'Sergipe'),
    ('TO', 'Tocantins'),
]

PATIENT_FIELDS = [
    'cns',
    'nome',
    'rg',
    'cpf',
    'profissao',
    'endereco_residencial',
    'cep_residencial',
    'endereco_logradouro',
    'endereco_numero',
    'endereco_bairro',
    'endereco_cidade',
    'endereco_estado',
    'endereco_ibge_codigo',
    'endereco_comercial',
    'cd_anterior',
    'endereco_comercial_adicional',
    'email',
    'genero',
    'data_nascimento',
    'nacionalidade',
    'celular',
    'estado_civil',
    'atendido_em',
    'nome_responsavel',
    'rg_responsavel',
    'telefone_expedidor_responsavel',
    'email_responsavel',
]


def _normalize_triage_code(value):
    return (value or '').strip().upper()


def _strip_form_data(data):
    return {
        key: value.strip() if isinstance(value, str) else value
        for key, value in data.items()
    }


def _only_digits(value):
    return ''.join(ch for ch in (value or '') if ch.isdigit())


def _normalize_uf(value):
    return (value or '').strip().upper()[:2]


def _format_cep(value):
    digits = _only_digits(value)
    if len(digits) == 8:
        return f"{digits[:5]}-{digits[5:]}"
    return (value or '').strip()


def _compose_residential_address(data):
    street = data.get('endereco_logradouro') or ''
    number = data.get('endereco_numero') or ''
    neighborhood = data.get('endereco_bairro') or ''
    city = data.get('endereco_cidade') or ''
    state = _normalize_uf(data.get('endereco_estado'))
    cep = _format_cep(data.get('cep_residencial'))

    address_parts = []
    if street and number:
        address_parts.append(f"{street}, {number}")
    elif street:
        address_parts.append(street)
    elif number:
        address_parts.append(f"Nº {number}")

    for value in (neighborhood, city):
        if value:
            address_parts.append(value)
    if state and city:
        address_parts[-1] = f"{city} - {state}"
    elif state:
        address_parts.append(state)
    if cep:
        address_parts.append(f"CEP {cep}")

    return ', '.join(address_parts)


def _build_patient_form_data():
    data = _strip_form_data({field: request.form.get(field) for field in PATIENT_FIELDS})
    data['cep_residencial'] = _format_cep(data.get('cep_residencial'))
    data['endereco_estado'] = _normalize_uf(data.get('endereco_estado'))
    data['endereco_residencial'] = (
        _compose_residential_address(data)
        or data.get('endereco_residencial')
    )
    return data


def _patient_field_values(data):
    return [data.get(field) for field in PATIENT_FIELDS]


def _fetch_json_url(url, timeout=4):
    with urlopen(url, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or 'utf-8'
        return json.loads(response.read().decode(charset))


def _local_alagoas_cities():
    rows = query("SELECT nome FROM municipios WHERE ativo = 1 ORDER BY nome")
    return [{'nome': row['nome'], 'ibge_codigo': ''} for row in rows]


def _remote_ibge_cities(uf):
    url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{quote(uf)}/municipios"
    cities = _fetch_json_url(url, timeout=5)
    return [
        {'nome': item.get('nome'), 'ibge_codigo': str(item.get('id') or '')}
        for item in sorted(cities, key=lambda row: row.get('nome') or '')
        if item.get('nome')
    ]


def _cities_for_state(uf):
    uf = _normalize_uf(uf)
    if uf == 'AL':
        return _local_alagoas_cities()
    if not uf:
        return []
    try:
        return _remote_ibge_cities(uf)
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        current_app.logger.warning('Falha ao carregar municípios do IBGE para UF %s', uf)
        return []


def _template_address_context(patient=None):
    patient = patient or {}
    selected_uf = _normalize_uf(patient.get('endereco_estado')) or 'AL'
    selected_city = patient.get('endereco_cidade') or ''
    initial_cities = (
        _local_alagoas_cities()
        if selected_uf == 'AL'
        else ([{'nome': selected_city, 'ibge_codigo': patient.get('endereco_ibge_codigo') or ''}] if selected_city else [])
    )
    return {
        'address_states': [{'uf': uf, 'nome': nome} for uf, nome in BRAZIL_STATES],
        'address_cities': initial_cities,
        'selected_address_uf': selected_uf,
    }


def _validate_patient_required_data(data):
    missing = []
    if not data.get('cns'):
        missing.append('CNS')
    if not data.get('cpf'):
        missing.append('CPF')
    if not data.get('nome'):
        missing.append('nome completo')
    if missing:
        return f"Preencha os dados obrigatórios do paciente: {', '.join(missing)}."
    return None

@patients_bp.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    if not current_user.can('patients:write'):
        flash('Acesso negado para cadastrar pacientes.', 'danger')
        return redirect(url_for('patients.list_patients'))

    if request.method == 'POST':
        data = _build_patient_form_data()
        validation_error = _validate_patient_required_data(data)
        if validation_error:
            flash(validation_error, 'danger')
            return render_template('patients/register.html', patient=data, **_template_address_context(data))
        
        try:
            patient_id = execute('''
                INSERT INTO patients (
                    cns, nome, rg, cpf, profissao, endereco_residencial,
                    cep_residencial, endereco_logradouro, endereco_numero,
                    endereco_bairro, endereco_cidade, endereco_estado, endereco_ibge_codigo,
                    endereco_comercial, cd_anterior, endereco_comercial_adicional,
                    email, genero, data_nascimento, nacionalidade, celular, estado_civil,
                    atendido_em, nome_responsavel, rg_responsavel,
                    telefone_expedidor_responsavel, email_responsavel
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', _patient_field_values(data))
            flash('Paciente cadastrado com sucesso. Agora a triagem pode associar uma ou mais senhas a este paciente.', 'success')

            return redirect(url_for('patients.view_patient', id=patient_id))
        except Exception as e:
            flash(f'Erro ao cadastrar paciente: {str(e)}', 'danger')
            return render_template('patients/register.html', patient=data, **_template_address_context(data))
            
    return render_template('patients/register.html', patient={}, **_template_address_context())


@patients_bp.route('/address/states')
@login_required
def address_states():
    return jsonify([{'uf': uf, 'nome': nome} for uf, nome in BRAZIL_STATES])


@patients_bp.route('/address/cities')
@login_required
def address_cities():
    return jsonify(_cities_for_state(request.args.get('uf')))


@patients_bp.route('/address/neighborhoods')
@login_required
def address_neighborhoods():
    uf = _normalize_uf(request.args.get('uf'))
    city = (request.args.get('city') or '').strip()
    if not city:
        return jsonify([])

    rows = query(
        """
        SELECT DISTINCT bairro
        FROM (
            SELECT NULLIF(TRIM(endereco_bairro), '') AS bairro
            FROM patients
            WHERE (%s = '' OR endereco_estado = %s)
              AND endereco_cidade ILIKE %s
            UNION
            SELECT NULLIF(TRIM(tl.neighborhood), '') AS bairro
            FROM territorial_locations tl
            LEFT JOIN municipios m ON m.id = tl.municipio_id
            WHERE tl.scope = 'bairro'
              AND tl.active = TRUE
              AND (%s = '' OR %s = 'AL')
              AND m.nome ILIKE %s
        ) bairros
        WHERE bairro IS NOT NULL
        ORDER BY bairro ASC
        LIMIT 200
        """,
        (uf, uf, city, uf, uf, city),
    )
    return jsonify([row['bairro'] for row in rows])


@patients_bp.route('/address/cep/<cep>')
@login_required
def address_cep(cep):
    digits = _only_digits(cep)
    if len(digits) != 8:
        return jsonify({'error': 'CEP inválido.'}), 400

    try:
        payload = _fetch_json_url(f"https://viacep.com.br/ws/{digits}/json/", timeout=4)
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        current_app.logger.warning('Falha ao consultar CEP %s', digits)
        return jsonify({'error': 'Serviço de CEP indisponível.'}), 502

    if payload.get('erro'):
        return jsonify({'error': 'CEP não encontrado.'}), 404

    return jsonify({
        'cep': _format_cep(payload.get('cep') or digits),
        'logradouro': payload.get('logradouro') or '',
        'bairro': payload.get('bairro') or '',
        'cidade': payload.get('localidade') or '',
        'estado': _normalize_uf(payload.get('uf')),
        'ibge_codigo': str(payload.get('ibge') or ''),
    })


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
            WHERE p.nome ILIKE %s OR p.cpf ILIKE %s OR p.cns ILIKE %s OR p.celular ILIKE %s
               OR EXISTS (
                    SELECT 1
                    FROM triagem_senhas ts
                    JOIN especialidades e ON ts.especialidade_id = e.id
                    JOIN municipios m ON ts.municipio_id = m.id
                    WHERE ts.patient_id = p.id
                      AND (ts.codigo ILIKE %s OR e.nome ILIKE %s OR m.nome ILIKE %s)
               )
        """
        params = (search_term, search_term, search_term, search_term, search_term, search_term, search_term)
        
        try:
            date_term = datetime.strptime(q, "%d/%m/%Y").strftime("%Y-%m-%d")
            where_clause += " OR p.data_nascimento = %s"
            params = params + (date_term,)
        except ValueError:
            pass
    else:
        where_clause = ""
        params = ()
        
    patients = query(f"""
        SELECT p.id, p.nome, p.cpf,
               triage.senha_triagem,
               triage.especialidade_nome,
               triage.municipio_codigo,
               COALESCE(triage.triage_count, 0) as triage_count,
               COALESCE((SELECT suspeita_neoplasia FROM estomatologia WHERE patient_id = p.id ORDER BY id DESC LIMIT 1), FALSE) as suspeita_neoplasia
        FROM patients p
        LEFT JOIN LATERAL (
            SELECT
                STRING_AGG(s.codigo, ', ' ORDER BY COALESCE(s.vinculada_em, s.criado_em) DESC, s.id DESC) as senha_triagem,
                STRING_AGG(e.nome, ', ' ORDER BY COALESCE(s.vinculada_em, s.criado_em) DESC, s.id DESC) as especialidade_nome,
                STRING_AGG(m.codigo, ', ' ORDER BY COALESCE(s.vinculada_em, s.criado_em) DESC, s.id DESC) as municipio_codigo,
                COUNT(*) as triage_count
            FROM triagem_senhas s
            JOIN especialidades e ON s.especialidade_id = e.id
            JOIN municipios m ON s.municipio_id = m.id
            WHERE s.patient_id = p.id
        ) triage ON TRUE
        {where_clause}
        ORDER BY p.id DESC
        LIMIT %s OFFSET %s
    """, (*params, per_page, offset))
    
    total_count = query(f"""
        SELECT COUNT(*) as count
        FROM patients p
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
            return render_template('patients/edit.html', patient=patient, **_template_address_context(patient))
            
        data = _build_patient_form_data()
        data['id'] = id
        validation_error = _validate_patient_required_data(data)
        if validation_error:
            flash(validation_error, 'danger')
            patient = dict(patient)
            patient.update(data)
            return render_template('patients/edit.html', patient=patient, **_template_address_context(patient))
        
        try:
            execute('''
                UPDATE patients SET 
                    cns=%s, nome=%s, rg=%s, cpf=%s, profissao=%s, endereco_residencial=%s,
                    cep_residencial=%s, endereco_logradouro=%s, endereco_numero=%s,
                    endereco_bairro=%s, endereco_cidade=%s, endereco_estado=%s, endereco_ibge_codigo=%s,
                    endereco_comercial=%s, cd_anterior=%s, endereco_comercial_adicional=%s,
                    email=%s, genero=%s, data_nascimento=%s, nacionalidade=%s, celular=%s,
                    estado_civil=%s, atendido_em=%s, nome_responsavel=%s, rg_responsavel=%s,
                    telefone_expedidor_responsavel=%s, email_responsavel=%s
                WHERE id=%s
            ''', _patient_field_values(data) + [id])
            flash('Dados do paciente atualizados!', 'success')
            return redirect(url_for('patients.list_patients'))
        except Exception as e:
            flash(f'Erro ao atualizar: {str(e)}', 'danger')
            
    return render_template('patients/edit.html', patient=patient, **_template_address_context(patient))

from services.patient_service import PatientService
from services.sigtap_service import (
    build_sigtap_options,
    build_sigtap_specialty_groups,
    get_sigtap_procedure,
    is_sigtap_code_allowed_for_specialty,
    normalize_sigtap_code,
)
from services.visual_media_service import (
    build_estomatologia_photo_metadata,
    update_endodontia_image_metadata,
    update_estomatologia_photo_metadata,
    update_exam_image_metadata,
)
from services.inventory_service import (
    mark_post_op_completed,
    register_patient_material_usage,
)

@patients_bp.route('/view/<int:id>')
@login_required
def view_patient(id):
    data = PatientService.get_patient_basic_info(id)
    if not data or not data.get('patient'):
        flash('Paciente não encontrado.', 'danger')
        return redirect(url_for('patients.list_patients'))
    data['sigtap_procedures'] = build_sigtap_options()
    data['sigtap_specialty_groups'] = build_sigtap_specialty_groups()
    return render_template('patients/view.html', **data)

from extensions import cache

@cache.cached(timeout=600, key_prefix='students_list')
def get_students_cached():
    roles = tuple(sorted(CLINICAL_EXECUTOR_ROLES))
    placeholders = ', '.join(['%s'] * len(roles))
    return query(
        f"SELECT id, username, full_name FROM users WHERE role IN ({placeholders}) ORDER BY full_name ASC",
        roles,
    )

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
        },
        'tab-estomatologia': {
            'service': PatientService.get_patient_estomatologia,
            'template': 'patients/includes/_tab_estomatologia.html',
            'is_dict': True
        },
        'tab-visual': {
            'service': PatientService.get_patient_visual_media,
            'template': 'patients/includes/_tab_visual.html',
            'is_dict': True
        },
        'tab-materiais': {
            'service': PatientService.get_patient_inventory,
            'template': 'patients/includes/_tab_materiais.html',
            'is_dict': True
        },
        'tab-linha-tempo': {
            'service': PatientService.get_patient_timeline,
            'template': 'patients/includes/_tab_linha_tempo.html',
            'is_dict': True
        }
    }

    if tab_name not in tab_mapping:
        return "Aba não encontrada.", 404
    if tab_name == 'tab-materiais' and not current_user.can('inventory:view'):
        return "Acesso negado.", 403

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
        
    # Adicionar profissionais clínicos quando a aba precisa de responsáveis/validadores.
    if tab_name in ['tab-atendimento', 'tab-tratamento', 'tab-endodontia', 'tab-protese', 'tab-materiais']:
        clinical_users = get_students_cached()
        context['clinical_users'] = clinical_users
        context['students'] = clinical_users  # Alias legado para templates ainda não migrados.

    if tab_name == 'tab-endodontia':
        context['linked_anamnesis'] = PatientService.get_patient_anamnesis(id)

    if tab_name == 'tab-tratamento':
        context['sigtap_procedures'] = data.get('sigtap_procedures', build_sigtap_options())
        context['sigtap_specialty_groups'] = data.get(
            'sigtap_specialty_groups',
            build_sigtap_specialty_groups(),
        )

    context['now'] = datetime.now()

    if tab_name == 'tab-visual':
        audit_log(
            action='visual_media_tab_opened',
            module='visual_media',
            entity_type='patient',
            entity_id=id,
            patient_id=id,
            details={
                'total_items': len(context.get('visual_items', [])),
                'comparison_groups': len(context.get('visual_comparisons', [])),
            },
        )

    return render_template(config['template'], **context)


@patients_bp.route('/<int:id>/materials/use', methods=['POST'])
@login_required
def add_material_usage(id):
    if not current_user.can('inventory:write'):
        flash('Sem permissão para registrar uso de materiais.', 'danger')
        return redirect(url_for('patients.view_patient', id=id) + '#tab-materiais')
    try:
        result = register_patient_material_usage(id, request.form, actor_id=current_user.id)
        audit_log(
            action='inventory_usage_registered',
            module='inventory',
            entity_type='inventory_usage',
            entity_id=result['usage_id'],
            patient_id=id,
            details={
                'item_id': result['item_id'],
                'item_name': result['item_name'],
                'lot_id': result['lot_id'],
                'lot_number': result['lot_number'],
                'quantity': str(result['quantity']),
                'usage_type': result['usage_type'],
                'post_op_required': result['post_op_required'],
                'post_op_due_date': result['post_op_due_date'],
            },
        )
        flash('Material registrado no prontuário e estoque atualizado.', 'success')
    except Exception as exc:
        audit_log(
            action='inventory_usage_register_failed',
            module='inventory',
            entity_type='inventory_usage',
            patient_id=id,
            status='failed',
            details={'error': str(exc), 'lot_id': request.form.get('lot_id')},
        )
        flash(f'Erro ao registrar material: {str(exc)}', 'danger')
    return redirect(url_for('patients.view_patient', id=id) + '#tab-materiais')


@patients_bp.route('/<int:id>/materials/usage/<int:usage_id>/post-op', methods=['POST'])
@login_required
def complete_material_post_op(id, usage_id):
    if not current_user.can('inventory:write'):
        flash('Sem permissão para concluir pós-operatório.', 'danger')
        return redirect(url_for('patients.view_patient', id=id) + '#tab-materiais')
    try:
        usage = mark_post_op_completed(id, usage_id)
        audit_log(
            action='inventory_post_op_completed',
            module='inventory',
            entity_type='inventory_usage',
            entity_id=usage_id,
            patient_id=id,
            details={
                'item_name': usage.get('item_name'),
                'lot_number': usage.get('lot_number'),
            },
        )
        flash('Pós-operatório registrado.', 'success')
    except Exception as exc:
        audit_log(
            action='inventory_post_op_complete_failed',
            module='inventory',
            entity_type='inventory_usage',
            entity_id=usage_id,
            patient_id=id,
            status='failed',
            details={'error': str(exc)},
        )
        flash(f'Erro ao registrar pós-operatório: {str(exc)}', 'danger')
    return redirect(url_for('patients.view_patient', id=id) + '#tab-materiais')


@patients_bp.route('/<int:id>/visual/estomatologia-photo/<int:photo_id>')
@login_required
@permission_required('patients:view')
def serve_estomatologia_photo(id, photo_id):
    photo = query(
        '''
        SELECT f.id, f.file_path, f.filename, f.legenda
        FROM estomatologia_fotos f
        JOIN estomatologia e ON e.id = f.estomatologia_id
        WHERE f.id = %s
          AND e.patient_id = %s
          AND COALESCE(f.active, TRUE) = TRUE
        ''',
        (photo_id, id),
        one=True,
    )
    if not photo or not os.path.exists(photo['file_path']):
        return "Arquivo não encontrado", 404

    audit_log(
        action='visual_media_file_viewed',
        module='visual_media',
        entity_type='estomatologia_fotos',
        entity_id=photo_id,
        patient_id=id,
        details={'filename': photo.get('filename'), 'caption': photo.get('legenda')},
    )
    return sensitive_file_response(photo['file_path'])


@patients_bp.route('/<int:id>/visual/exam-image/<int:arquivo_id>/metadata', methods=['POST'])
@login_required
def update_exam_visual_metadata(id, arquivo_id):
    try:
        record = update_exam_image_metadata(arquivo_id, id, request.form)
        if not record:
            flash('Imagem não encontrada ou sem vínculo com este paciente.', 'danger')
            return redirect(url_for('patients.view_patient', id=id) + '#tab-visual')
        audit_log(
            action='visual_media_metadata_updated',
            module='visual_media',
            entity_type='exam_imagem_arquivos',
            entity_id=arquivo_id,
            patient_id=id,
            details={
                'source': 'exam_image',
                'visual_category': request.form.get('visual_category'),
                'comparison_label': request.form.get('comparison_label'),
                'comparison_group': request.form.get('comparison_group'),
            },
        )
        flash('Metadados da imagem atualizados.', 'success')
    except ValueError as exc:
        flash(str(exc), 'danger')
    except Exception as exc:
        flash(f'Erro ao atualizar imagem: {str(exc)}', 'danger')
    return redirect(url_for('patients.view_patient', id=id) + '#tab-visual')


@patients_bp.route('/<int:id>/visual/estomatologia-photo/<int:photo_id>/metadata', methods=['POST'])
@login_required
def update_estomatologia_visual_metadata(id, photo_id):
    try:
        record = update_estomatologia_photo_metadata(photo_id, id, request.form)
        if not record:
            flash('Foto não encontrada ou sem vínculo com este paciente.', 'danger')
            return redirect(url_for('patients.view_patient', id=id) + '#tab-visual')
        audit_log(
            action='visual_media_metadata_updated',
            module='visual_media',
            entity_type='estomatologia_fotos',
            entity_id=photo_id,
            patient_id=id,
            details={
                'source': 'estomatologia_photo',
                'visual_category': request.form.get('visual_category'),
                'comparison_label': request.form.get('comparison_label'),
                'comparison_group': request.form.get('comparison_group'),
            },
        )
        flash('Metadados da foto atualizados.', 'success')
    except ValueError as exc:
        flash(str(exc), 'danger')
    except Exception as exc:
        flash(f'Erro ao atualizar foto: {str(exc)}', 'danger')
    return redirect(url_for('patients.view_patient', id=id) + '#tab-visual')


@patients_bp.route('/<int:id>/visual/endodontia-image/<int:image_id>/metadata', methods=['POST'])
@login_required
def update_endodontia_visual_metadata(id, image_id):
    try:
        record = update_endodontia_image_metadata(image_id, id, request.form)
        if not record:
            flash('Imagem endodôntica não encontrada ou sem vínculo com este paciente.', 'danger')
            return redirect(url_for('patients.view_patient', id=id) + '#tab-visual')
        audit_log(
            action='visual_media_metadata_updated',
            module='visual_media',
            entity_type='endodontia_imagens',
            entity_id=image_id,
            patient_id=id,
            details={
                'source': 'endodontia_image',
                'visual_category': request.form.get('visual_category'),
                'comparison_label': request.form.get('comparison_label'),
                'comparison_group': request.form.get('comparison_group'),
                'canal': request.form.get('canal'),
            },
        )
        flash('Metadados da imagem endodôntica atualizados.', 'success')
    except ValueError as exc:
        flash(str(exc), 'danger')
    except Exception as exc:
        flash(f'Erro ao atualizar imagem endodôntica: {str(exc)}', 'danger')
    return redirect(url_for('patients.view_patient', id=id) + '#tab-visual')

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
        signature_mode = SIGNATURE_MODE_A_ROGO if wants_a_rogo(request.form) else SIGNATURE_MODE_CANVAS
        signer = current_user
        witnesses = []
        declaration_text = None
        auth_method = 'patient_canvas_session'

        if signature_mode == SIGNATURE_MODE_A_ROGO:
            try:
                signer = validate_a_rogo_signer(
                    request.form.get('rogo_prof_username'),
                    request.form.get('rogo_prof_password'),
                )
                witnesses = collect_a_rogo_witnesses(request.form)
                declaration_text = A_ROGO_DECLARATION
                assinatura = SIGNATURE_MARKER_A_ROGO
                auth_method = 'login_senha_cd_a_rogo'
            except ValueError as exc:
                flash(str(exc), 'danger')
                return render_template('patients/tcle.html', patient=patient)
        elif not assinatura:
            flash('A assinatura do paciente é obrigatória.', 'danger')
            return render_template('patients/tcle.html', patient=patient)

        try:
            signer_id = signer['id'] if isinstance(signer, dict) else signer.id
            tcle_id = execute('''
                INSERT INTO patient_tcle (
                    patient_id, aluno_id, assinatura_base64, assinatura_modo,
                    assinatura_a_rogo_por, assinatura_a_rogo_declaracao,
                    assinatura_a_rogo_testemunhas, assinatura_auth_method
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                RETURNING id
            ''', (
                id,
                signer_id,
                assinatura,
                signature_mode,
                signer_id if signature_mode == SIGNATURE_MODE_A_ROGO else None,
                declaration_text,
                json_dumps(witnesses),
                auth_method,
            ))
            payload = build_tcle_payload(
                patient,
                signature_mode,
                signature_capture=assinatura if signature_mode == SIGNATURE_MODE_CANVAS else None,
                witnesses=witnesses,
                signer=signer,
            )
            evidence = register_signature_event(
                document_type='patient_tcle',
                document_id=tcle_id,
                patient=patient,
                signature_mode=signature_mode,
                payload=payload,
                signed_by_user=signer,
                auth_method=auth_method,
                declaration_text=declaration_text,
                witnesses=witnesses,
                metadata={'tcle_version': 'tcle-odontologico-v1'},
            )
            execute('''
                UPDATE patient_tcle
                SET assinatura_event_id = %s,
                    assinatura_document_hash = %s,
                    assinatura_source_ip = %s,
                    assinatura_user_agent = %s
                WHERE id = %s
            ''', (
                evidence['event_id'],
                evidence['document_hash'],
                evidence['source_ip'],
                evidence['user_agent'],
                tcle_id,
            ))
            flash('Termo de Consentimento assinado com sucesso!', 'success')
            return redirect(url_for('patients.view_patient', id=id))
        except Exception as e:
            flash(f'Erro ao salvar termo: {str(e)}', 'danger')

    return render_template('patients/tcle.html', patient=patient)

@patients_bp.route('/<int:id>/treatment/add', methods=['POST'])
@login_required
def add_treatment(id):
    dente = request.form.get('dente')
    especialidade_sigtap = request.form.get('especialidade_sigtap') or None
    descricao = request.form.get('descricao')
    sigtap_code = normalize_sigtap_code(request.form.get('sigtap_code'))
    sigtap_competence = request.form.get('sigtap_competence') or None
    sigtap = get_sigtap_procedure(sigtap_code, sigtap_competence) if sigtap_code else None
    
    if not descricao:
        flash('Por favor, preencha o procedimento.', 'danger')
        return redirect(url_for('patients.view_patient', id=id) + '#tab-tratamento')
    if request.form.get('sigtap_code') and not sigtap:
        flash('Código SIGTAP não encontrado na competência carregada.', 'danger')
        return redirect(url_for('patients.view_patient', id=id) + '#tab-tratamento')
    if not is_sigtap_code_allowed_for_specialty(especialidade_sigtap, sigtap_code):
        flash('Código SIGTAP não pertence à especialidade selecionada.', 'danger')
        return redirect(url_for('patients.view_patient', id=id) + '#tab-tratamento')
        
    try:
        execute('''
            INSERT INTO tratamento_procedimentos (
                patient_id, dente, descricao, especialidade_sigtap,
                sigtap_code, sigtap_competence, sigtap_name
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            id,
            dente,
            descricao,
            especialidade_sigtap,
            sigtap['code'] if sigtap else None,
            sigtap['competence'] if sigtap else None,
            sigtap['name'] if sigtap else None,
        ))
        flash('Procedimento adicionado ao plano de tratamento.', 'success')
    except Exception as e:
        flash(f'Erro ao adicionar procedimento: {str(e)}', 'danger')
        
    return redirect(url_for('patients.view_patient', id=id) + '#tab-tratamento')

@patients_bp.route('/<int:id>/treatment/<int:proc_id>/edit', methods=['POST'])
@login_required
def edit_treatment(id, proc_id):
    dente = request.form.get('dente')
    especialidade_sigtap = request.form.get('especialidade_sigtap') or None
    descricao = request.form.get('descricao')
    sigtap_code = normalize_sigtap_code(request.form.get('sigtap_code'))
    sigtap_competence = request.form.get('sigtap_competence') or None
    sigtap = get_sigtap_procedure(sigtap_code, sigtap_competence) if sigtap_code else None
    
    if not descricao:
        flash('Por favor, preencha o procedimento.', 'danger')
        return redirect(url_for('patients.view_patient', id=id) + '#tab-tratamento')
    if request.form.get('sigtap_code') and not sigtap:
        flash('Código SIGTAP não encontrado na competência carregada.', 'danger')
        return redirect(url_for('patients.view_patient', id=id) + '#tab-tratamento')
    if not is_sigtap_code_allowed_for_specialty(especialidade_sigtap, sigtap_code):
        flash('Código SIGTAP não pertence à especialidade selecionada.', 'danger')
        return redirect(url_for('patients.view_patient', id=id) + '#tab-tratamento')
        
    try:
        execute('''
            UPDATE tratamento_procedimentos 
            SET dente = %s,
                descricao = %s,
                especialidade_sigtap = %s,
                sigtap_code = %s,
                sigtap_competence = %s,
                sigtap_name = %s,
                esus_export_status = CASE
                    WHEN status = 'Concluído' THEN 'pending'
                    ELSE esus_export_status
                END
            WHERE id = %s AND patient_id = %s
        ''', (
            dente,
            descricao,
            especialidade_sigtap,
            sigtap['code'] if sigtap else None,
            sigtap['competence'] if sigtap else None,
            sigtap['name'] if sigtap else None,
            proc_id,
            id,
        ))
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
            SET professor_id = %s,
                status = 'Concluído',
                esus_export_status = CASE
                    WHEN sigtap_code IS NULL THEN 'missing_sigtap'
                    ELSE 'pending'
                END
            WHERE id = %s AND patient_id = %s
        ''', (prof['id'], proc_id, id))
        
        # Busca o procedimento para pegar os detalhes
        proc = query(
            "SELECT dente, descricao, sigtap_code, sigtap_name FROM tratamento_procedimentos WHERE id = %s",
            (proc_id,),
            one=True,
        )
        obs = f"Dente {proc['dente']}: {proc['descricao']}" if proc['dente'] else proc['descricao']
        if proc.get('sigtap_code'):
            obs = f"{obs}\nSIGTAP {proc['sigtap_code']} - {proc.get('sigtap_name') or ''}".strip()
        
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
    signature_mode = SIGNATURE_MODE_A_ROGO if wants_a_rogo(request.form) else SIGNATURE_MODE_CANVAS
    patient = query("SELECT * FROM patients WHERE id = %s", (id,), one=True)
    appt = query("SELECT * FROM atendimentos WHERE id = %s AND patient_id = %s", (appt_id, id), one=True)

    if not patient or not appt:
        flash('Atendimento não encontrado para assinatura.', 'danger')
        return redirect(url_for('patients.view_patient', id=id) + '#tab-atendimento')

    signer = current_user
    witnesses = []
    declaration_text = None
    auth_method = 'patient_canvas_session'

    if signature_mode == SIGNATURE_MODE_A_ROGO:
        try:
            signer = validate_a_rogo_signer(
                request.form.get('rogo_prof_username'),
                request.form.get('rogo_prof_password'),
            )
            witnesses = collect_a_rogo_witnesses(request.form)
            declaration_text = A_ROGO_DECLARATION
            assinatura_base64 = SIGNATURE_MARKER_A_ROGO
            auth_method = 'login_senha_cd_a_rogo'
        except ValueError as exc:
            flash(str(exc), 'danger')
            return redirect(url_for('patients.view_patient', id=id) + '#tab-atendimento')
    elif not assinatura_base64:
        flash('Nenhuma assinatura fornecida.', 'danger')
        return redirect(url_for('patients.view_patient', id=id) + '#tab-atendimento')
        
    try:
        signer_id = signer['id'] if isinstance(signer, dict) else getattr(signer, 'id', None)
        payload = build_atendimento_payload(
            patient,
            appt,
            signature_mode,
            signature_capture=assinatura_base64 if signature_mode == SIGNATURE_MODE_CANVAS else None,
            witnesses=witnesses,
            signer=signer,
        )
        evidence = register_signature_event(
            document_type='atendimento_patient_confirmation',
            document_id=appt_id,
            patient=patient,
            signature_mode=signature_mode,
            payload=payload,
            signed_by_user=signer,
            auth_method=auth_method,
            declaration_text=declaration_text,
            witnesses=witnesses,
            metadata={'atendimento_id': appt_id},
        )
        execute('''
            UPDATE atendimentos 
            SET assinatura_paciente_base64 = %s,
                assinatura_modo = %s,
                assinatura_event_id = %s,
                assinatura_document_hash = %s,
                assinatura_a_rogo_por = %s,
                assinatura_a_rogo_declaracao = %s,
                assinatura_a_rogo_testemunhas = %s::jsonb,
                assinatura_auth_method = %s,
                assinatura_source_ip = %s,
                assinatura_user_agent = %s
            WHERE id = %s AND patient_id = %s
        ''', (
            assinatura_base64,
            signature_mode,
            evidence['event_id'],
            evidence['document_hash'],
            signer_id if signature_mode == SIGNATURE_MODE_A_ROGO else None,
            declaration_text,
            json_dumps(witnesses),
            auth_method,
            evidence['source_ip'],
            evidence['user_agent'],
            appt_id,
            id,
        ))
        
        # Verifica se já tem assinatura do professor e do aluno executor para gerar a data
        appt = query("SELECT data, professor_id, aluno_executor_id FROM atendimentos WHERE id = %s", (appt_id,), one=True)
        if appt['professor_id'] and appt['aluno_executor_id'] and (not appt['data'] or appt['data'] == ''):
            execute("UPDATE atendimentos SET data = %s WHERE id = %s", (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), appt_id))
            
        if signature_mode == SIGNATURE_MODE_A_ROGO:
            flash('Assinatura a rogo registrada com evidência de leitura, consentimento e testemunhas.', 'success')
        else:
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
    if not prof or not check_password_hash(prof['password'], password) or not can_sign_clinical_document(prof['role']):
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

# ── Rotas do Módulo de Estomatologia (Fase 0) ────────────────────────────────

@patients_bp.route('/<int:id>/estomatologia/save', methods=['POST'])
@login_required
def save_estomatologia(id):
    localizacao = request.form.get('localizacao_lesao')
    tamanho = request.form.get('tamanho_lesao')
    caracteristicas = request.form.get('caracteristicas_lesao')
    habitos = request.form.get('habitos_paciente')
    tempo_evolucao = request.form.get('tempo_evolucao')
    hipotese = request.form.get('hipotese_diagnostica')
    suspeita = True if request.form.get('suspeita_neoplasia') == 'on' else False
    conduta = request.form.get('conduta_clinica')
    encaminhado = True if request.form.get('encaminhado_para_biopsia') == 'on' else False

    if not all([localizacao, tamanho, caracteristicas, tempo_evolucao]):
        flash('Por favor, preencha todos os campos obrigatórios da lesão.', 'danger')
        return redirect(url_for('patients.view_patient', id=id) + '#tab-estomatologia')

    try:
        # Verifica se já existe um registro para o paciente
        est = query("SELECT id FROM estomatologia WHERE patient_id = %s LIMIT 1", (id,), one=True)

        if est:
            execute('''
                UPDATE estomatologia SET
                    dentista_id = %s,
                    localizacao_lesao = %s,
                    tamanho_lesao = %s,
                    caracteristicas_lesao = %s,
                    habitos_paciente = %s,
                    tempo_evolucao = %s,
                    hipotese_diagnostica = %s,
                    suspeita_neoplasia = %s,
                    conduta_clinica = %s,
                    encaminhado_para_biopsia = %s,
                    data_registro = CURRENT_TIMESTAMP
                WHERE patient_id = %s
            ''', (current_user.id, localizacao, tamanho, caracteristicas, habitos, tempo_evolucao, hipotese, suspeita, conduta, encaminhado, id))
            flash('Ficha de Estomatologia atualizada com sucesso!', 'success')
        else:
            execute('''
                INSERT INTO estomatologia (
                    patient_id, dentista_id, localizacao_lesao, tamanho_lesao,
                    caracteristicas_lesao, habitos_paciente, tempo_evolucao,
                    hipotese_diagnostica, suspeita_neoplasia, conduta_clinica,
                    encaminhado_para_biopsia
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (id, current_user.id, localizacao, tamanho, caracteristicas, habitos, tempo_evolucao, hipotese, suspeita, conduta, encaminhado))
            flash('Ficha de Estomatologia registrada com sucesso!', 'success')

    except Exception as e:
        flash(f'Erro ao salvar ficha de estomatologia: {str(e)}', 'danger')

    return redirect(url_for('patients.view_patient', id=id) + '#tab-estomatologia')

@patients_bp.route('/<int:id>/estomatologia/photo/upload', methods=['POST'])
@login_required
def upload_estomatologia_photo(id):
    import uuid
    from werkzeug.utils import secure_filename

    file = request.files.get('foto')
    metadata = build_estomatologia_photo_metadata(request.form)

    if not file or file.filename == '':
        flash('Nenhuma foto enviada.', 'danger')
        return redirect(url_for('patients.view_patient', id=id) + '#tab-estomatologia')
    if not metadata['legenda']:
        flash('A legenda da foto é obrigatória para rastreamento visual.', 'danger')
        return redirect(url_for('patients.view_patient', id=id) + '#tab-estomatologia')

    # Validação simples de tipo de arquivo
    original_filename = secure_filename(file.filename)
    ext = os.path.splitext(original_filename)[1].lower()
    if ext not in ['.jpg', '.jpeg', '.png', '.webp']:
        flash('Formato de imagem inválido. Use JPG, PNG ou WEBP.', 'danger')
        return redirect(url_for('patients.view_patient', id=id) + '#tab-estomatologia')

    try:
        # Busca a estomatologia correspondente do paciente
        est = query("SELECT id FROM estomatologia WHERE patient_id = %s LIMIT 1", (id,), one=True)
        if not est:
            flash('Por favor, salve a Ficha de Estomatologia antes de enviar fotos da lesão.', 'warning')
            return redirect(url_for('patients.view_patient', id=id) + '#tab-estomatologia')

        upload_dir = os.path.join('uploads', 'estomatologia')
        os.makedirs(upload_dir, exist_ok=True)

        filename = f"{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(upload_dir, filename)

        file.save(filepath)

        # Salva registro no banco
        photo_id = execute('''
            INSERT INTO estomatologia_fotos (
                estomatologia_id, filename, file_path, legenda, visual_category,
                clinical_context, comparison_label, comparison_group, taken_at,
                uploaded_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NULLIF(%s, '')::timestamp, %s)
            RETURNING id
        ''', (
            est['id'],
            original_filename or filename,
            filepath,
            metadata['legenda'],
            metadata['visual_category'],
            metadata['clinical_context'],
            metadata['comparison_label'],
            metadata['comparison_group'],
            metadata['taken_at'] or '',
            current_user.id,
        ))

        audit_log(
            action='visual_media_uploaded',
            module='visual_media',
            entity_type='estomatologia_fotos',
            entity_id=photo_id,
            patient_id=id,
            details={
                'source': 'estomatologia',
                'filename': original_filename,
                'visual_category': metadata['visual_category'],
                'comparison_label': metadata['comparison_label'],
                'comparison_group': metadata['comparison_group'],
            },
        )

        flash('Foto da lesão enviada com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao fazer upload da foto: {str(e)}', 'danger')

    return redirect(url_for('patients.view_patient', id=id) + '#tab-estomatologia')

@patients_bp.route('/<int:id>/estomatologia/photo/<int:photo_id>/delete', methods=['POST'])
@login_required
def delete_estomatologia_photo(id, photo_id):
    try:
        # Busca a foto para obter o caminho
        photo = query('''
            SELECT f.id, f.file_path, f.filename, f.legenda, f.visual_category, f.comparison_group
            FROM estomatologia_fotos f
            JOIN estomatologia e ON f.estomatologia_id = e.id
            WHERE f.id = %s AND e.patient_id = %s
        ''', (photo_id, id), one=True)

        if not photo:
            flash('Foto não encontrada ou sem permissão para excluí-la.', 'danger')
            return redirect(url_for('patients.view_patient', id=id) + '#tab-estomatologia')

        # Remove do banco
        execute('DELETE FROM estomatologia_fotos WHERE id = %s', (photo_id,))

        audit_log(
            action='visual_media_deleted',
            module='visual_media',
            entity_type='estomatologia_fotos',
            entity_id=photo_id,
            patient_id=id,
            details={
                'filename': photo.get('filename'),
                'caption': photo.get('legenda'),
                'visual_category': photo.get('visual_category'),
                'comparison_group': photo.get('comparison_group'),
            },
        )

        # Tenta remover do disco
        if os.path.exists(photo['file_path']):
            os.remove(photo['file_path'])

        flash('Foto removida da evolução com sucesso.', 'success')
    except Exception as e:
        flash(f'Erro ao excluir foto: {str(e)}', 'danger')

    return redirect(url_for('patients.view_patient', id=id) + '#tab-estomatologia')

@patients_bp.route('/red-alerts')
@login_required
def red_alert_list():
    patients = query('''
        SELECT p.id, p.nome, p.cpf, e.localizacao_lesao, e.tamanho_lesao,
               e.tempo_evolucao, e.data_registro,
               triage.senha_triagem,
               triage.municipio_nome
        FROM patients p
        JOIN estomatologia e ON e.patient_id = p.id
        LEFT JOIN LATERAL (
            SELECT
                STRING_AGG(s.codigo, ', ' ORDER BY COALESCE(s.vinculada_em, s.criado_em) DESC, s.id DESC) as senha_triagem,
                STRING_AGG(m.nome, ', ' ORDER BY COALESCE(s.vinculada_em, s.criado_em) DESC, s.id DESC) as municipio_nome
            FROM triagem_senhas s
            JOIN municipios m ON s.municipio_id = m.id
            WHERE s.patient_id = p.id
        ) triage ON TRUE
        WHERE e.suspeita_neoplasia = TRUE
        ORDER BY e.data_registro DESC
    ''')

    return render_template('patients/red_alerts.html', patients=patients)
