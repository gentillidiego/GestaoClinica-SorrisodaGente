from types import SimpleNamespace

from flask import Flask

import blueprints.patients as patients


def make_app():
    app = Flask(__name__)
    app.config.update(SECRET_KEY='test-secret', TESTING=True)
    app.register_blueprint(patients.patients_bp)
    return app


def _sign_treatment(monkeypatch, *, existing_appt=None):
    """Chama sign_treatment() com credenciais válidas, capturando os execute()."""
    queries = {
        'FROM tratamento_procedimentos': {
            'id': 50, 'patient_id': 9, 'dente': '12',
            'descricao': 'Restauração', 'sigtap_code': '0307010031',
            'sigtap_name': 'Restauração de Dente Permanente Anterior',
        },
        'FROM users': {'id': 5, 'password': 'hash', 'role': 'clinicos'},
        'FROM atendimentos WHERE tratamento_procedimento_id': existing_appt,
    }

    def fake_query(sql, params=(), one=False):
        for marker, value in queries.items():
            if marker in sql:
                return value
        raise AssertionError(f'Query inesperada: {sql}')

    executed = []

    def fake_execute(sql, params=()):
        executed.append((sql, params))
        return 999

    monkeypatch.setattr(patients, 'query', fake_query)
    monkeypatch.setattr(patients, 'execute', fake_execute)
    monkeypatch.setattr(patients, 'check_password_hash', lambda pw_hash, pw: True)
    monkeypatch.setattr(patients, 'can_sign_clinical_document', lambda role: True)
    monkeypatch.setattr(patients, 'current_user', SimpleNamespace(id=5))

    app = make_app()
    with app.test_request_context(
        '/patients/9/treatment/50/sign',
        method='POST',
        data={'validator_username': 'dra.cibely', 'validator_password': 'segura'},
    ):
        patients.sign_treatment.__wrapped__(9, 50)

    return executed


def test_sign_treatment_marks_plan_as_planejado_not_concluido(monkeypatch):
    executed = _sign_treatment(monkeypatch, existing_appt=None)

    update_sql, update_params = executed[0]
    assert 'UPDATE tratamento_procedimentos' in update_sql
    assert "status = 'Planejado'" in update_sql
    assert 'Concluído' not in update_sql
    assert update_params == (5, 50, 9)


def test_sign_treatment_creates_linked_atendimento_without_executor(monkeypatch):
    executed = _sign_treatment(monkeypatch, existing_appt=None)

    insert_sql, insert_params = executed[1]
    assert 'INSERT INTO atendimentos' in insert_sql
    assert 'tratamento_procedimento_id' in insert_sql
    assert "'Pendente'" in insert_sql
    assert 'executor_id' not in insert_sql
    assert insert_params == (9, 'Dente 12: Restauração\nSIGTAP 0307010031 - Restauração de Dente Permanente Anterior', 5, 50)


def test_sign_treatment_does_not_duplicate_atendimento_when_already_linked(monkeypatch):
    executed = _sign_treatment(monkeypatch, existing_appt={'id': 777})

    assert len(executed) == 1
    assert 'UPDATE tratamento_procedimentos' in executed[0][0]


def _sign_executor(monkeypatch, *, tratamento_procedimento_id):
    queries = {
        'FROM atendimentos': {
            'id': 30, 'data': None,
            'tratamento_procedimento_id': tratamento_procedimento_id,
        },
        'FROM users': {'id': 6, 'password': 'hash', 'role': 'clinicos'},
    }

    def fake_query(sql, params=(), one=False):
        for marker, value in queries.items():
            if marker in sql:
                return value
        raise AssertionError(f'Query inesperada: {sql}')

    executed = []
    audited = []

    def fake_execute(sql, params=()):
        executed.append((sql, params))
        return None

    monkeypatch.setattr(patients, 'query', fake_query)
    monkeypatch.setattr(patients, 'execute', fake_execute)
    monkeypatch.setattr(patients, 'check_password_hash', lambda pw_hash, pw: True)
    monkeypatch.setattr(patients, 'can_sign_clinical_document', lambda role: True)
    monkeypatch.setattr(patients, 'audit_log', lambda **kwargs: audited.append(kwargs))

    app = make_app()
    with app.test_request_context(
        '/patients/9/atendimento/30/sign_executor',
        method='POST',
        data={'executor_username': 'dr.joao', 'executor_password': 'segura'},
    ):
        patients.sign_executor_atendimento.__wrapped__(9, 30)

    return executed, audited


def test_sign_executor_confirms_production_on_linked_procedure(monkeypatch):
    executed, audited = _sign_executor(monkeypatch, tratamento_procedimento_id=50)

    atendimento_sql, atendimento_params = executed[0]
    assert 'UPDATE atendimentos' in atendimento_sql
    assert 'executor_id = %s' in atendimento_sql
    assert "status = 'Concluído'" in atendimento_sql
    assert atendimento_params[0] == 6  # executor_id
    assert atendimento_params[1] == 6  # validator_id (mesmo signatário)

    proc_sql, proc_params = executed[1]
    assert 'UPDATE tratamento_procedimentos' in proc_sql
    assert "status = 'Concluído'" in proc_sql
    assert proc_params == (50,)

    assert audited[0]['action'] == 'treatment_production_confirmed'
    assert audited[0]['entity_id'] == 50
    assert audited[0]['details']['executor_id'] == 6


def test_sign_executor_without_linked_procedure_does_not_touch_treatment(monkeypatch):
    executed, audited = _sign_executor(monkeypatch, tratamento_procedimento_id=None)

    assert len(executed) == 1
    assert 'UPDATE atendimentos' in executed[0][0]
    assert audited == []
