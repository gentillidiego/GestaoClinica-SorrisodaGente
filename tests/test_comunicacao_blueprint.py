from types import SimpleNamespace

from flask import Flask
from flask_login import LoginManager

import blueprints.comunicacao as comunicacao_module
from blueprints.comunicacao import comunicacao_bp
from constants import Role, role_has_permission


def make_app():
    app = Flask(__name__)
    app.config.update(SECRET_KEY='test-secret', TESTING=True, WTF_CSRF_ENABLED=False)
    app.register_blueprint(comunicacao_bp)

    @app.route('/login-stub', endpoint='auth.login')
    def login():
        return 'login'

    @app.route('/dashboard-stub', endpoint='main.dashboard')
    def dashboard():
        return 'dashboard'

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)
    return app


def test_role_permissions_grant_comunicacao_only_to_intended_roles():
    assert role_has_permission(Role.COMUNICACAO, 'comunicacao:view')
    assert role_has_permission(Role.COMUNICACAO, 'comunicacao:write')
    assert role_has_permission(Role.ADMIN, 'comunicacao:write')
    assert role_has_permission(Role.COORDENACAO, 'comunicacao:view')

    # Acesso restrito: o perfil Comunicação não deve herdar acesso a
    # prontuário clínico/agenda só por ganhar o módulo de campanhas.
    assert not role_has_permission(Role.COMUNICACAO, 'patients:view')
    assert not role_has_permission(Role.COMUNICACAO, 'agenda:view')

    # Outros perfis sem o módulo não devem ganhar acesso por acidente.
    assert not role_has_permission(Role.RADIOLOGIA, 'comunicacao:view')
    assert not role_has_permission(Role.CLINICOS, 'comunicacao:view')


def test_require_comunicacao_access_blocks_user_without_view_permission(monkeypatch):
    monkeypatch.setattr(
        comunicacao_module, 'current_user',
        SimpleNamespace(is_authenticated=True, can=lambda perm: False),
    )
    app = make_app()
    with app.test_request_context('/comunicacao/'):
        result = comunicacao_module.require_comunicacao_access()
    assert result is not None  # redirect response, antes de chegar à view


def test_require_comunicacao_access_allows_user_with_view_permission(monkeypatch):
    monkeypatch.setattr(
        comunicacao_module, 'current_user',
        SimpleNamespace(is_authenticated=True, can=lambda perm: perm == 'comunicacao:view'),
    )
    app = make_app()
    with app.test_request_context('/comunicacao/'):
        result = comunicacao_module.require_comunicacao_access()
    assert result is None  # nada bloqueia, segue para a view


def test_require_comunicacao_access_redirects_unauthenticated_user(monkeypatch):
    monkeypatch.setattr(
        comunicacao_module, 'current_user', SimpleNamespace(is_authenticated=False),
    )
    app = make_app()
    with app.test_request_context('/comunicacao/'):
        result = comunicacao_module.require_comunicacao_access()
    assert result is not None
    assert result.status_code in (301, 302, 308)


def test_require_comunicacao_access_skips_whatsapp_webhook(monkeypatch):
    monkeypatch.setattr(
        comunicacao_module, 'current_user', SimpleNamespace(is_authenticated=False),
    )
    app = make_app()
    with app.test_request_context('/comunicacao/webhook/whatsapp'):
        result = comunicacao_module.require_comunicacao_access()
    assert result is None


def test_require_write_blocks_without_write_permission(monkeypatch):
    monkeypatch.setattr(
        comunicacao_module, 'current_user',
        SimpleNamespace(is_authenticated=True, can=lambda perm: perm == 'comunicacao:view'),
    )
    app = make_app()
    with app.test_request_context('/comunicacao/campanhas/nova', method='POST'):
        assert comunicacao_module._require_write() is False


def test_require_write_allows_with_write_permission(monkeypatch):
    monkeypatch.setattr(
        comunicacao_module, 'current_user',
        SimpleNamespace(is_authenticated=True, can=lambda perm: True),
    )
    app = make_app()
    with app.test_request_context('/comunicacao/campanhas/nova', method='POST'):
        assert comunicacao_module._require_write() is True


def test_webhook_get_validates_token(monkeypatch):
    monkeypatch.setenv('WHATSAPP_WEBHOOK_VERIFY_TOKEN', 'segredo123')
    app = make_app()
    client = app.test_client()

    ok_response = client.get(
        '/comunicacao/webhook/whatsapp',
        query_string={
            'hub.mode': 'subscribe',
            'hub.verify_token': 'segredo123',
            'hub.challenge': 'desafio-abc',
        },
    )
    assert ok_response.status_code == 200
    assert ok_response.data.decode() == 'desafio-abc'

    bad_response = client.get(
        '/comunicacao/webhook/whatsapp',
        query_string={
            'hub.mode': 'subscribe',
            'hub.verify_token': 'errado',
            'hub.challenge': 'desafio-abc',
        },
    )
    assert bad_response.status_code == 403


def test_webhook_post_triggers_opt_out_on_stop_keyword(monkeypatch):
    opted_out = []
    monkeypatch.setattr(
        comunicacao_module, 'opt_out_whatsapp_by_phone',
        lambda phone: opted_out.append(phone),
    )
    app = make_app()
    client = app.test_client()

    payload = {
        'entry': [{
            'changes': [{
                'value': {
                    'messages': [{'from': '5582999999999', 'text': {'body': 'PARAR'}}],
                },
            }],
        }],
    }
    response = client.post('/comunicacao/webhook/whatsapp', json=payload)

    assert response.status_code == 200
    assert opted_out == ['5582999999999']
