import re
from pathlib import Path

from flask import Flask, jsonify, render_template_string, session
from flask_wtf.csrf import CSRFProtect
from werkzeug.exceptions import TooManyRequests

from services.web_security_service import (
    regenerate_session_after_authentication,
    register_web_security,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _security_app():
    app = Flask(
        __name__,
        template_folder=str(PROJECT_ROOT / 'templates'),
    )
    app.config.update(
        SECRET_KEY='test-secret',
        TESTING=False,
    )
    register_web_security(app)
    return app


def test_session_cookie_and_https_headers_are_hardened():
    app = _security_app()

    @app.get('/session')
    def create_session():
        session['user_id'] = 7
        return jsonify({'ok': True})

    response = app.test_client().get(
        '/session',
        base_url='https://sorrisodagentealagoas.com',
    )

    cookie = response.headers['Set-Cookie']
    assert 'Secure' in cookie
    assert 'HttpOnly' in cookie
    assert 'SameSite=Lax' in cookie
    assert response.headers['Strict-Transport-Security'] == (
        'max-age=31536000; includeSubDomains'
    )
    assert response.headers['X-Frame-Options'] == 'DENY'
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert response.headers['Referrer-Policy'] == 'strict-origin-when-cross-origin'
    assert response.headers['Permissions-Policy'] == (
        'camera=(), microphone=(), geolocation=(), payment=(), usb=()'
    )
    assert response.headers['Cross-Origin-Opener-Policy'] == 'same-origin'
    assert response.headers['Cross-Origin-Resource-Policy'] == 'same-origin'
    assert re.fullmatch(r'[0-9A-F]{16}', response.headers['X-Request-ID'])

    csp = response.headers['Content-Security-Policy']
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    assert "form-action 'self'" in csp
    assert 'https://cdn.jsdelivr.net' in csp
    assert 'https://fonts.googleapis.com' in csp


def test_local_training_can_disable_secure_cookie(monkeypatch):
    monkeypatch.setenv('SESSION_COOKIE_SECURE', 'false')
    app = _security_app()

    @app.get('/session')
    def create_training_session():
        session['user_id'] = 7
        return jsonify({'ok': True})

    response = app.test_client().get(
        '/session',
        base_url='http://127.0.0.1:5103',
    )

    cookie = response.headers['Set-Cookie']
    assert 'Secure' not in cookie
    assert 'HttpOnly' in cookie
    assert app.config['PREFERRED_URL_SCHEME'] == 'http'


def test_internal_error_response_hides_sensitive_details():
    app = _security_app()

    @app.get('/explode')
    def explode():
        raise RuntimeError(
            'postgresql://usuario:segredo@db/clinica /srv/gestaosaudeoral/private'
        )

    response = app.test_client().get(
        '/explode',
        base_url='https://sorrisodagentealagoas.com',
        headers={'Accept': 'application/json'},
    )

    assert response.status_code == 500
    payload = response.get_json()
    serialized = response.get_data(as_text=True)
    assert 'segredo' not in serialized
    assert '/srv/gestaosaudeoral/private' not in serialized
    assert 'postgresql://' not in serialized
    assert payload['error'].startswith('Não foi possível concluir a operação.')
    assert re.fullmatch(r'[0-9A-F]{16}', payload['reference'])
    assert response.headers['X-Request-ID'] == payload['reference']


def test_csrf_failure_uses_safe_response_and_reference():
    app = _security_app()
    CSRFProtect(app)

    @app.post('/mutate')
    def mutate():
        return jsonify({'ok': True})

    response = app.test_client().post(
        '/mutate',
        base_url='https://sorrisodagentealagoas.com',
        headers={'Accept': 'application/json'},
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert 'expirou' in payload['error']
    assert re.fullmatch(r'[0-9A-F]{16}', payload['reference'])


def test_valid_csrf_with_https_referer_is_accepted():
    app = _security_app()
    CSRFProtect(app)

    @app.get('/form')
    def form():
        return render_template_string(
            '<form method="post"><input name="csrf_token" value="{{ csrf_token() }}"></form>'
        )

    @app.post('/mutate')
    def mutate():
        return jsonify({'ok': True})

    client = app.test_client()
    form_response = client.get(
        '/form',
        base_url='https://sorrisodagentealagoas.com',
    )
    match = re.search(
        r'name="csrf_token" value="([^"]+)"',
        form_response.get_data(as_text=True),
    )
    assert match

    response = client.post(
        '/mutate',
        base_url='https://sorrisodagentealagoas.com',
        headers={'Referer': 'https://sorrisodagentealagoas.com/form'},
        data={'csrf_token': match.group(1)},
    )

    assert response.status_code == 200
    assert response.get_json() == {'ok': True}


def test_session_regeneration_clears_old_state_and_keeps_session_permanent():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-secret'

    class RecordingInterface:
        called = False
        session_was_nonempty = False

        def regenerate(self, current_session):
            self.called = True
            self.session_was_nonempty = bool(current_session)

    with app.test_request_context('/login', method='POST'):
        session['csrf_token'] = 'old-token'
        session['temporary_state'] = 'old-value'
        recorder = RecordingInterface()
        app.session_interface = recorder

        regenerate_session_after_authentication()

        assert 'csrf_token' not in session
        assert 'temporary_state' not in session
        assert '_session_regeneration_pending' not in session
        assert session.permanent is True
        assert recorder.called is True
        assert recorder.session_was_nonempty is True


def test_logout_route_accepts_post_only():
    auth_source = (PROJECT_ROOT / 'blueprints' / 'auth.py').read_text(
        encoding='utf-8'
    )
    base_template = (PROJECT_ROOT / 'templates' / 'base.html').read_text(
        encoding='utf-8'
    )

    assert "@auth_bp.route('/logout', methods=['POST'])" in auth_source
    assert "<form action=\"{{ url_for('auth.logout') }}\" method=\"POST\"" in base_template
    assert 'name="csrf_token"' in base_template
    assert "<a href=\"{{ url_for('auth.logout') }}\"" not in base_template


def test_auth_rate_limits_apply_only_to_submissions():
    auth_source = (PROJECT_ROOT / 'blueprints' / 'auth.py').read_text(
        encoding='utf-8'
    )

    assert (
        '@limiter.limit("5 per minute; 20 per hour", methods=[\'POST\'])'
        in auth_source
    )
    assert '@limiter.limit("10 per hour", methods=[\'POST\'])' in auth_source


def test_rate_limit_uses_safe_error_response():
    app = _security_app()

    @app.get('/limited')
    def limited():
        return 'ok'

    with app.test_request_context(
        '/limited',
        base_url='https://sorrisodagentealagoas.com',
        headers={'Accept': 'application/json'},
    ):
        response = app.handle_user_exception(
            TooManyRequests()
        )

    assert response[1] == 429
    assert 'bloqueou temporariamente' in response[0].get_json()['error']
