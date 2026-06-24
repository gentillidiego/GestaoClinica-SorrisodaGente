from pathlib import Path

from flask import Flask
import pytest
from werkzeug.security import generate_password_hash

import blueprints.anamnesis as anamnesis_module
import services.signature_evidence_service as signature_service
from constants import Role


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_a_rogo_payload_does_not_require_witnesses():
    patient = {'id': 42, 'nome': 'Paciente Teste', 'cpf': '123.456.789-00', 'rg': '123'}
    signer = {'id': 7, 'username': 'dra.cibely', 'role': Role.CLINICOS}

    payload = signature_service.build_tcle_payload(
        patient,
        signature_service.SIGNATURE_MODE_A_ROGO,
        signer=signer,
    )

    assert payload['signature_mode'] == signature_service.SIGNATURE_MODE_A_ROGO
    assert payload['witnesses'] == []


def test_a_rogo_forms_require_only_clinical_user_credentials():
    atendimento_modal = (
        PROJECT_ROOT / 'templates/patients/includes/_modals.html'
    ).read_text(encoding='utf-8')
    tcle_form = (PROJECT_ROOT / 'templates/patients/tcle.html').read_text(encoding='utf-8')

    for template in (atendimento_modal, tcle_form):
        assert 'name="rogo_validator_username"' in template
        assert 'name="rogo_validator_password"' in template
        assert 'rogo_witness' not in template


def test_anamnesis_forms_always_require_clinician_credentials():
    anamnesis_form = (
        PROJECT_ROOT / 'templates/anamnesis/form.html'
    ).read_text(encoding='utf-8')
    anamnesis_edit = (
        PROJECT_ROOT / 'templates/anamnesis/edit_anamnesis.html'
    ).read_text(encoding='utf-8')

    for template in (anamnesis_form, anamnesis_edit):
        assert 'name="clinico_username"' in template
        assert 'name="clinico_password"' in template
        assert 'signature-pad' not in template
        assert 'patient_not_literate' not in template


def test_validate_a_rogo_signer_accepts_active_clinical_user(monkeypatch):
    monkeypatch.setattr(
        signature_service,
        'query',
        lambda sql, params=(), one=False: {
            'id': 7,
            'username': 'dra.cibely',
            'password': generate_password_hash('segura'),
            'role': Role.CLINICOS,
            'full_name': 'Dra. Cibely',
            'cro': '1234',
            'cro_uf': 'AL',
        },
    )

    signer = signature_service.validate_a_rogo_signer('dra.cibely', 'segura')

    assert signer['id'] == 7
    assert signer['role'] == Role.CLINICOS


def test_register_signature_event_stores_hash_and_request_context(monkeypatch):
    app = Flask(__name__)
    calls = []
    audit_calls = []

    def fake_execute(sql, params=()):
        calls.append((sql, params))
        if 'INSERT INTO signature_events' in sql:
            return 101
        return None

    monkeypatch.setattr(signature_service, 'execute', fake_execute)
    monkeypatch.setattr(signature_service, 'audit_log', lambda **kwargs: audit_calls.append(kwargs))

    patient = {'id': 42, 'nome': 'Paciente Teste', 'cpf': '123.456.789-00', 'rg': '123'}
    signer = {
        'id': 7,
        'username': 'dra.cibely',
        'role': Role.CLINICOS,
        'full_name': 'Dra. Cibely',
        'cro': '1234',
        'cro_uf': 'AL',
    }
    witnesses = []
    payload = signature_service.build_tcle_payload(
        patient,
        signature_service.SIGNATURE_MODE_A_ROGO,
        witnesses=witnesses,
        signer=signer,
    )

    with app.test_request_context(
        '/patients/tcle/42',
        method='POST',
        headers={'X-Forwarded-For': '203.0.113.10, 10.0.0.1', 'User-Agent': 'pytest-agent'},
    ):
        evidence = signature_service.register_signature_event(
            document_type='patient_tcle',
            document_id=55,
            patient=patient,
            signature_mode=signature_service.SIGNATURE_MODE_A_ROGO,
            payload=payload,
            signed_by_user=signer,
            auth_method='login_senha_cd_a_rogo',
            declaration_text=signature_service.A_ROGO_DECLARATION,
            witnesses=witnesses,
        )

    assert evidence['event_id'] == 101
    assert len(evidence['document_hash']) == 64
    assert evidence['source_ip'] == '203.0.113.10'
    assert 'INSERT INTO signature_events' in calls[0][0]
    assert calls[0][1][5] == signature_service.SIGNATURE_MODE_A_ROGO
    assert calls[0][1][10] == 'login_senha_cd_a_rogo'
    assert calls[0][1][11] == '203.0.113.10'
    assert calls[1][1][6] == 'assinatura-a-rogo-login-senha'
    assert audit_calls[0]['details']['signature_mode'] == signature_service.SIGNATURE_MODE_A_ROGO


def test_build_generic_signature_payload_hashes_canvas_capture():
    patient = {'id': 42, 'nome': 'Paciente Teste', 'cpf': '123.456.789-00', 'rg': '123'}
    payload = signature_service.build_generic_signature_payload(
        'anamnesis',
        patient,
        signature_service.SIGNATURE_MODE_CANVAS,
        document_data={'anamnesis_id': 5, 'queixa_principal': 'Dor'},
        signature_capture='data:image/png;base64,assinatura',
    )

    assert payload['document_type'] == 'anamnesis'
    assert payload['patient']['cpf'] == '123.456.789-00'
    assert payload['document_data']['anamnesis_id'] == 5
    assert payload['signature_capture_sha256'] == signature_service.hash_text('data:image/png;base64,assinatura')


def test_prepare_anamnesis_uses_clinician_credentials(monkeypatch):
    signer = {
        'id': 7,
        'username': 'dra.cibely',
        'role': Role.CLINICOS,
        'full_name': 'Dra. Cibely',
        'cro': '1234',
        'cro_uf': 'AL',
    }
    monkeypatch.setattr(
        anamnesis_module,
        'validate_a_rogo_signer',
        lambda username, password: signer,
    )

    signature_data = anamnesis_module._prepare_anamnesis_signature({
        'clinico_username': 'dra.cibely',
        'clinico_password': 'segura',
    })

    assert signature_data['assinatura'] == signature_service.SIGNATURE_MARKER_A_ROGO
    assert signature_data['signature_mode'] == signature_service.SIGNATURE_MODE_A_ROGO
    assert signature_data['signer'] == signer
    assert signature_data['declaration_text'] == signature_service.ANAMNESIS_CLINICIAN_DECLARATION
    assert signature_data['auth_method'] == 'login_senha_clinico'
    assert signature_data['witnesses'] == []


def test_prepare_anamnesis_requires_valid_clinician_credentials(monkeypatch):
    def fake_validate(username, password):
        raise ValueError('Informe usuário e senha do CD responsável pela assinatura a rogo.')

    monkeypatch.setattr(anamnesis_module, 'validate_a_rogo_signer', fake_validate)

    with pytest.raises(ValueError, match='usuário e senha'):
        anamnesis_module._prepare_anamnesis_signature({})


def test_record_anamnesis_a_rogo_persists_evidence_fields(monkeypatch):
    calls = []
    signer = {
        'id': 7,
        'username': 'dra.cibely',
        'role': Role.CLINICOS,
        'full_name': 'Dra. Cibely',
        'cro': '1234',
        'cro_uf': 'AL',
    }
    signature_data = {
        'assinatura': signature_service.SIGNATURE_MARKER_A_ROGO,
        'signature_mode': signature_service.SIGNATURE_MODE_A_ROGO,
        'signer': signer,
        'declaration_text': signature_service.ANAMNESIS_CLINICIAN_DECLARATION,
        'auth_method': 'login_senha_clinico',
        'witnesses': [],
    }
    monkeypatch.setattr(
        anamnesis_module,
        'register_signature_event',
        lambda **kwargs: {
            'event_id': 101,
            'document_hash': 'a' * 64,
            'source_ip': '203.0.113.10',
            'user_agent': 'pytest-agent',
        },
    )
    monkeypatch.setattr(
        anamnesis_module,
        'execute',
        lambda sql, params=(): calls.append((sql, params)),
    )

    anamnesis_module._record_anamnesis_signature(
        55,
        {'id': 42, 'nome': 'Paciente Teste', 'cpf': '123.456.789-00', 'rg': '123'},
        {'queixa_principal': 'Dor', 'tem_alergia': 'Não'},
        signature_data,
    )

    sql, params = calls[0]
    assert 'assinatura_a_rogo_por = %s' in sql
    assert 'assinatura_a_rogo_declaracao = %s' in sql
    assert params[0] == signature_service.SIGNATURE_MARKER_A_ROGO
    assert params[1] == signature_service.SIGNATURE_MODE_A_ROGO
    assert params[4] == signer['id']
    assert params[5] == signature_service.ANAMNESIS_CLINICIAN_DECLARATION
    assert params[6] == '[]'
    assert params[7] == 'login_senha_clinico'
