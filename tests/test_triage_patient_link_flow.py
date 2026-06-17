from flask import Flask

import blueprints.triage as triage


def _app():
    app = Flask(__name__)
    app.config['LOGIN_DISABLED'] = True
    app.secret_key = 'test'
    app.register_blueprint(triage.triage_bp)
    return app


def test_generate_ticket_requires_registered_patient(monkeypatch):
    app = _app()
    execute_called = False

    def fake_query(sql, params=(), one=False):
        if 'FROM triagem_acoes' in sql:
            return {'id': 10, 'municipio_id': 2, 'municipio_codigo': 'ARA'}
        return None

    def fake_execute(*args, **kwargs):
        nonlocal execute_called
        execute_called = True

    monkeypatch.setattr(triage, 'query', fake_query)
    monkeypatch.setattr(triage, 'execute', fake_execute)

    with app.test_request_context('/triagem/acoes/10/gerar', method='POST', data={'especialidade_id': '3'}):
        response = triage.generate_tickets(10)

    assert response.status_code == 302
    assert execute_called is False


def test_generate_ticket_links_existing_patient_on_insert(monkeypatch):
    app = _app()
    captured = {}

    def fake_query(sql, params=(), one=False):
        if 'FROM triagem_acoes' in sql:
            return {'id': 10, 'municipio_id': 2, 'municipio_codigo': 'ARA'}
        if 'FROM patients' in sql:
            return {'id': 42, 'nome': 'Maria Souza'}
        if 'FROM especialidades' in sql:
            return {'id': 3, 'codigo': 'P'}
        if 'COALESCE(MAX(numero)' in sql:
            return {'ultimo': 4}
        return None

    def fake_execute(sql, params=()):
        captured['sql'] = sql
        captured['params'] = params

    monkeypatch.setattr(triage, 'query', fake_query)
    monkeypatch.setattr(triage, 'execute', fake_execute)

    with app.test_request_context(
        '/triagem/acoes/10/gerar',
        method='POST',
        data={'patient_id': '42', 'especialidade_id': '3'},
    ):
        response = triage.generate_tickets(10)

    assert response.status_code == 302
    assert 'status, patient_id, vinculada_em' in captured['sql']
    assert "'Vinculada'" in captured['sql']
    assert captured['params'] == (10, 2, 3, 5, 'ARA-P-005', 42)
