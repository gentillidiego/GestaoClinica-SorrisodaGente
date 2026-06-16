from datetime import date, datetime

from flask import Blueprint, Flask

import services.auth_flow_service as auth_flow_service
import services.professional_registration_service as professional_registration_service


def test_parse_birthdate_input_accepts_multiple_formats():
    assert auth_flow_service.parse_birthdate_input('1990-05-17') == date(1990, 5, 17)
    assert auth_flow_service.parse_birthdate_input('17/05/1990') == date(1990, 5, 17)
    assert auth_flow_service.parse_birthdate_input('17051990') == date(1990, 5, 17)
    assert auth_flow_service.parse_birthdate_input('') is None


def test_verify_first_access_user_requires_matching_birthdate(monkeypatch):
    monkeypatch.setattr(
        auth_flow_service,
        'get_user_for_login',
        lambda username: {
            'id': 8,
            'username': username,
            'active': True,
            'is_first_access': True,
            'data_nascimento': date(1984, 3, 25),
        },
    )

    assert auth_flow_service.verify_first_access_user('maria', '25/03/1984')['id'] == 8
    assert auth_flow_service.verify_first_access_user('maria', '24/03/1984') is None


def test_validate_password_strength_requires_letter_and_number():
    assert auth_flow_service.validate_password_strength('abc') == 'A senha definitiva deve ter pelo menos 8 caracteres.'
    assert auth_flow_service.validate_password_strength('abcdefgh') == 'A senha definitiva deve conter pelo menos um numero.'
    assert auth_flow_service.validate_password_strength('12345678') == 'A senha definitiva deve conter pelo menos uma letra.'
    assert auth_flow_service.validate_password_strength('Senha123') is None


def test_build_reset_url_prefers_external_request_url(monkeypatch):
    app = Flask(__name__)
    app.secret_key = 'test'
    auth_bp = Blueprint('auth', __name__)

    @auth_bp.route('/redefinir-senha')
    def reset_password():
        return 'ok'

    app.register_blueprint(auth_bp)

    monkeypatch.delenv('APP_BASE_URL', raising=False)

    with app.test_request_context('/esqueci-senha', base_url='https://sorrisodagentealagoas.com'):
        url = auth_flow_service.build_reset_url('abc123')

    assert url == 'https://sorrisodagentealagoas.com/redefinir-senha?token=abc123'


def test_password_reset_email_uses_brand_template(monkeypatch):
    app = Flask(__name__)
    app.secret_key = 'test'
    auth_bp = Blueprint('auth', __name__)

    @auth_bp.route('/redefinir-senha')
    def reset_password():
        return 'ok'

    app.register_blueprint(auth_bp)
    monkeypatch.setenv('APP_BASE_URL', 'https://sorrisodagentealagoas.com')

    with app.test_request_context('/esqueci-senha'):
        text_body, html_body = auth_flow_service.build_password_reset_email(
            {'full_name': 'Dra. Maria', 'username': 'maria', 'email': 'maria@example.com'},
            'abc123',
        )

    assert 'https://sorrisodagentealagoas.com/redefinir-senha?token=abc123' in text_body
    assert 'logo_sorriso_horizontal.png' in html_body
    assert 'Redefinir senha' in html_body
    assert 'Programa Sorriso da Gente' in html_body


def test_create_password_reset_token_stores_only_hash(monkeypatch):
    calls = []
    monkeypatch.setattr(auth_flow_service, 'execute', lambda sql, params=(): calls.append((sql, params)))

    raw_token, expires_at = auth_flow_service.create_password_reset_token(12)

    assert raw_token
    assert isinstance(expires_at, datetime)
    assert len(calls) == 1
    _, params = calls[0]
    assert params[0] != raw_token
    assert params[2] == 12


def test_professional_registration_validation_matches_new_rule():
    payload = {
        'full_name': 'Maria da Silva',
        'cpf': '529.982.247-25',
        'data_nascimento': '1990-05-17',
        'email': 'maria@example.com',
        'celular': '(82) 99999-0000',
        'desired_username': 'maria.silva',
        'requested_role': 'clinicos',
        'cns': '123.4567.8901.2345',
        'cbo': '223208',
        'cro': '1234',
        'cro_uf': 'AL',
        'notes': '',
        'truth_accepted': True,
        'lgpd_accepted': True,
    }
    errors = professional_registration_service.validate_registration_payload(payload)
    assert errors == []


def test_professional_registration_does_not_require_cnes_or_ine():
    payload = {
        'full_name': 'Carlos Lima',
        'cpf': '529.982.247-25',
        'data_nascimento': '1992-02-10',
        'email': 'carlos@example.com',
        'celular': '(82) 99999-1111',
        'desired_username': 'carlos.lima',
        'requested_role': 'radiologia',
        'cns': '123.4567.8901.2345',
        'cbo': '322205',
        'cro': '',
        'cro_uf': '',
        'notes': '',
        'truth_accepted': True,
        'lgpd_accepted': True,
    }
    errors = professional_registration_service.validate_registration_payload(payload)
    assert errors == []


def test_approve_registration_request_creates_first_access_user(monkeypatch):
    calls = {'execute': []}
    registration = {
        'id': 4,
        'status': 'pending',
        'full_name': 'Maria da Silva',
        'cpf': '529.982.247-25',
        'data_nascimento': '1990-05-17',
        'email': 'maria@example.com',
        'celular': '(82) 99999-0000',
        'desired_username': 'maria.silva',
        'requested_role': 'clinicos',
        'cns': '123.4567.8901.2345',
        'cbo': '223208',
        'cro': '1234',
        'cro_uf': 'AL',
    }

    def fake_query(sql, params=(), one=False):
        if 'FROM professional_registration_requests' in sql:
            return dict(registration)
        if 'FROM users WHERE username' in sql:
            return None
        return None

    def fake_execute_returning(sql, params=()):
        calls['insert_sql'] = sql
        calls['insert_params'] = params
        return 77

    def fake_execute(sql, params=()):
        calls['execute'].append((sql, params))

    monkeypatch.setattr(professional_registration_service, 'query', fake_query)
    monkeypatch.setattr(professional_registration_service, 'execute_returning', fake_execute_returning)
    monkeypatch.setattr(professional_registration_service, 'execute', fake_execute)

    approved = professional_registration_service.approve_registration_request(4, reviewer_id=9)

    assert approved['created_user_id'] == 77
    assert approved['status'] == 'approved'
    assert 'is_first_access' in calls['insert_sql']
    assert calls['insert_params'][0] == 'maria.silva'
    assert calls['insert_params'][2] == 'clinicos'
    assert calls['execute'][0][1] == (9, 77, 4)


def test_professional_registration_approved_email_has_first_access_link(monkeypatch):
    monkeypatch.setenv('APP_BASE_URL', 'https://sorrisodagentealagoas.com')
    text_body, html_body = professional_registration_service.build_registration_approved_email({
        'full_name': 'Maria da Silva',
        'desired_username': 'maria.silva',
        'requested_role': 'clinicos',
    })

    assert 'maria.silva' in text_body
    assert 'https://sorrisodagentealagoas.com/primeiro-acesso' in text_body
    assert 'Fazer primeiro acesso' in html_body
    assert 'logo_sorriso_horizontal.png' in html_body


def test_professional_registration_rejected_email_includes_review_notes():
    text_body, html_body = professional_registration_service.build_registration_rejected_email({
        'full_name': 'Carlos Lima',
        'review_notes': 'CPF divergente. Reenvie os dados corrigidos.',
    })

    assert 'CPF divergente' in text_body
    assert 'CPF divergente' in html_body
    assert 'Pre-cadastro recusado' in html_body
