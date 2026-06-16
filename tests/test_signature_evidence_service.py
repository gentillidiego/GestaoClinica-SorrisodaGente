from flask import Flask
from werkzeug.security import generate_password_hash

import services.signature_evidence_service as signature_service
from constants import Role


def test_collect_a_rogo_witnesses_requires_two_witnesses():
    form = {
        'rogo_witness1_name': 'Maria Testemunha',
        'rogo_witness1_document': '111.111.111-11',
        'rogo_witness2_name': 'Jose Testemunha',
        'rogo_witness2_document': '222.222.222-22',
    }

    witnesses = signature_service.collect_a_rogo_witnesses(form)

    assert len(witnesses) == 2
    assert witnesses[0]['name'] == 'Maria Testemunha'
    assert witnesses[1]['document'] == '222.222.222-22'


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
    witnesses = [
        {'order': 1, 'name': 'Maria', 'document': '111'},
        {'order': 2, 'name': 'Jose', 'document': '222'},
    ]
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
