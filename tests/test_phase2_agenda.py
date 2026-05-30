from flask import Flask

import blueprints.agenda as agenda


def test_atualizar_status_does_not_update_missing_consulta(monkeypatch):
    app = Flask(__name__)
    app.config['LOGIN_DISABLED'] = True
    app.secret_key = 'test'
    app.register_blueprint(agenda.agenda_bp)

    execute_called = False

    def fake_execute(*args, **kwargs):
        nonlocal execute_called
        execute_called = True

    monkeypatch.setattr(agenda, '_can_manage', lambda: True)
    monkeypatch.setattr(agenda, 'query', lambda *args, **kwargs: None)
    monkeypatch.setattr(agenda, 'execute', fake_execute)
    monkeypatch.setattr(agenda, 'audit_log', lambda *args, **kwargs: None)

    with app.test_request_context('/agenda/999/status', method='POST', data={'status': 'Faltou'}):
        response = agenda.atualizar_status(999)

    assert response.status_code == 302
    assert execute_called is False
