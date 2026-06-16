import hashlib
import json

from flask import has_request_context, request
from flask_login import current_user
from werkzeug.security import check_password_hash

from constants import can_sign_clinical_document
from database import execute, query
from services.security_service import audit_log, get_client_ip


SIGNATURE_MODE_CANVAS = 'patient_canvas'
SIGNATURE_MODE_A_ROGO = 'a_rogo'
SIGNATURE_MARKER_A_ROGO = 'ASSINATURA_A_ROGO_REGISTRADA'
TCLE_VERSION = 'tcle-odontologico-v1'

A_ROGO_DECLARATION = (
    'Declaro, sob minha responsabilidade profissional, que li em voz alta e '
    'expliquei este documento ao paciente não alfabetizado em linguagem '
    'acessível, esclareci suas dúvidas e registrei que ele manifestou '
    'consentimento livre e informado para este ato.'
)


def wants_a_rogo(form_data):
    return form_data.get('patient_not_literate') in {'1', 'true', 'on', 'yes'}


def json_dumps(value):
    return json.dumps(value, ensure_ascii=False, default=str)


def hash_text(value):
    return hashlib.sha256((value or '').encode('utf-8')).hexdigest()


def calculate_document_hash(payload):
    canonical_payload = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(',', ':'),
    )
    return hash_text(canonical_payload)


def collect_a_rogo_witnesses(form_data):
    witnesses = []
    for index in (1, 2):
        name = (form_data.get(f'rogo_witness{index}_name') or '').strip()
        document = (form_data.get(f'rogo_witness{index}_document') or '').strip()
        if not name or not document:
            raise ValueError('Informe nome e documento das duas testemunhas para assinatura a rogo.')
        witnesses.append({
            'order': index,
            'name': name,
            'document': document,
        })
    return witnesses


def validate_a_rogo_signer(username, password):
    username = (username or '').strip()
    if not username or not password:
        raise ValueError('Informe usuário e senha do CD responsável pela assinatura a rogo.')

    signer = query(
        """
        SELECT id, username, password, role, full_name, cro, cro_uf
        FROM users
        WHERE username = %s AND COALESCE(active, TRUE) = TRUE
        """,
        (username,),
        one=True,
    )
    if not signer or not check_password_hash(signer['password'], password):
        raise ValueError('Credenciais do CD inválidas.')
    if not can_sign_clinical_document(signer['role']):
        raise ValueError('Usuário sem permissão clínica para assinatura a rogo.')
    return signer


def current_actor_data():
    if getattr(current_user, 'is_authenticated', False):
        return {
            'id': current_user.id,
            'username': current_user.username,
            'role': current_user.role,
            'full_name': getattr(current_user, 'full_name', None),
            'cro': getattr(current_user, 'cro', None),
            'cro_uf': getattr(current_user, 'cro_uf', None),
        }
    return None


def user_public_data(user):
    if not user:
        return None
    if isinstance(user, dict):
        return {
            'id': user.get('id'),
            'username': user.get('username'),
            'role': user.get('role'),
            'full_name': user.get('full_name'),
            'cro': user.get('cro'),
            'cro_uf': user.get('cro_uf'),
        }
    return {
        'id': getattr(user, 'id', None),
        'username': getattr(user, 'username', None),
        'role': getattr(user, 'role', None),
        'full_name': getattr(user, 'full_name', None),
        'cro': getattr(user, 'cro', None),
        'cro_uf': getattr(user, 'cro_uf', None),
    }


def request_evidence_context():
    if not has_request_context():
        return {'source_ip': None, 'user_agent': None, 'method': None, 'path': None}
    return {
        'source_ip': get_client_ip(),
        'user_agent': request.headers.get('User-Agent'),
        'method': request.method,
        'path': request.path,
    }


def build_tcle_payload(patient, signature_mode, signature_capture=None, witnesses=None, signer=None):
    payload = {
        'document_type': 'patient_tcle',
        'version': TCLE_VERSION,
        'patient': {
            'id': patient.get('id'),
            'nome': patient.get('nome'),
            'cpf': patient.get('cpf'),
            'rg': patient.get('rg'),
        },
        'signature_mode': signature_mode,
        'declaration': A_ROGO_DECLARATION if signature_mode == SIGNATURE_MODE_A_ROGO else None,
        'witnesses': witnesses or [],
        'signer': user_public_data(signer),
        'content_summary': (
            'TCLE odontologico: identificacao das partes, esclarecimento e consentimento, '
            'natureza da atividade odontologica, deveres do paciente, alteracoes no plano, '
            'LGPD e disposicoes finais.'
        ),
    }
    if signature_capture:
        payload['signature_capture_sha256'] = hash_text(signature_capture)
    return payload


def build_atendimento_payload(patient, atendimento, signature_mode, signature_capture=None, witnesses=None, signer=None):
    payload = {
        'document_type': 'atendimento_patient_confirmation',
        'patient': {
            'id': patient.get('id'),
            'nome': patient.get('nome'),
            'cpf': patient.get('cpf'),
            'rg': patient.get('rg'),
        },
        'atendimento': {
            'id': atendimento.get('id'),
            'data': atendimento.get('data'),
            'observacoes': atendimento.get('observacoes'),
            'status': atendimento.get('status'),
            'professor_id': atendimento.get('professor_id'),
            'aluno_executor_id': atendimento.get('aluno_executor_id'),
        },
        'signature_mode': signature_mode,
        'declaration': A_ROGO_DECLARATION if signature_mode == SIGNATURE_MODE_A_ROGO else None,
        'witnesses': witnesses or [],
        'signer': user_public_data(signer),
    }
    if signature_capture:
        payload['signature_capture_sha256'] = hash_text(signature_capture)
    return payload


def build_generic_signature_payload(
    document_type,
    patient,
    signature_mode,
    document_data=None,
    signature_capture=None,
    witnesses=None,
    signer=None,
):
    payload = {
        'document_type': document_type,
        'patient': {
            'id': patient.get('id'),
            'nome': patient.get('nome'),
            'cpf': patient.get('cpf'),
            'rg': patient.get('rg'),
        },
        'document_data': document_data or {},
        'signature_mode': signature_mode,
        'declaration': A_ROGO_DECLARATION if signature_mode == SIGNATURE_MODE_A_ROGO else None,
        'witnesses': witnesses or [],
        'signer': user_public_data(signer),
    }
    if signature_capture:
        payload['signature_capture_sha256'] = hash_text(signature_capture)
    return payload


def register_signature_event(
    document_type,
    document_id,
    patient,
    signature_mode,
    payload,
    signed_by_user=None,
    auth_method='session',
    declaration_text=None,
    witnesses=None,
    metadata=None,
):
    request_context = request_evidence_context()
    signer = user_public_data(signed_by_user) or current_actor_data()
    document_hash = calculate_document_hash(payload)
    witnesses = witnesses or []
    metadata = metadata or {}
    metadata = {
        **metadata,
        'payload': payload,
        'request': request_context,
    }

    event_id = execute(
        """
        INSERT INTO signature_events (
            document_type, document_id, patient_id, patient_name, patient_cpf,
            signature_mode, document_hash, signed_by, signer_username,
            signer_role, auth_method, source_ip, user_agent, declaration_text,
            witnesses, metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
        RETURNING id
        """,
        (
            document_type,
            str(document_id) if document_id is not None else None,
            patient.get('id'),
            patient.get('nome'),
            patient.get('cpf'),
            signature_mode,
            document_hash,
            signer.get('id') if signer else None,
            signer.get('username') if signer else None,
            signer.get('role') if signer else None,
            auth_method,
            request_context['source_ip'],
            request_context['user_agent'],
            declaration_text,
            json_dumps(witnesses),
            json_dumps(metadata),
        ),
    )

    execute(
        """
        INSERT INTO digital_signatures (
            document_type, document_id, patient_id, signed_by, signer_name,
            signer_role, signature_provider, signature_hash, ip_address, metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        """,
        (
            document_type,
            str(document_id) if document_id is not None else None,
            patient.get('id'),
            signer.get('id') if signer else None,
            (signer.get('full_name') or signer.get('username')) if signer else None,
            signer.get('role') if signer else None,
            'assinatura-a-rogo-login-senha' if signature_mode == SIGNATURE_MODE_A_ROGO else 'patient-canvas-internal',
            document_hash,
            request_context['source_ip'],
            json_dumps({'signature_event_id': event_id, 'auth_method': auth_method}),
        ),
    )

    if has_request_context():
        audit_log(
            action='signature_event_recorded',
            module='documents',
            entity_type=document_type,
            entity_id=document_id,
            patient_id=patient.get('id'),
            details={
                'signature_event_id': event_id,
                'signature_mode': signature_mode,
                'document_hash': document_hash,
                'auth_method': auth_method,
                'signed_by': signer.get('username') if signer else None,
            },
        )

    return {
        'event_id': event_id,
        'document_hash': document_hash,
        'source_ip': request_context['source_ip'],
        'user_agent': request_context['user_agent'],
        'witnesses': witnesses,
        'declaration_text': declaration_text,
        'auth_method': auth_method,
        'signer': signer,
    }
