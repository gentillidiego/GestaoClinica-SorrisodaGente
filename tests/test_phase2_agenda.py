from flask import Flask

import blueprints.agenda as agenda
from constants import Role


class FakeAgendaUser:
    def __init__(self, user_id=7, role=Role.CLINICOS, permissions=None):
        self.id = user_id
        self.role = role
        self.username = f'user{user_id}'
        self.full_name = f'User {user_id}'
        self._permissions = permissions or {'agenda:view', 'agenda:write'}

    def can(self, permission):
        return permission in self._permissions


def test_full_scope_roles_do_not_filter_agenda_by_dentist(monkeypatch):
    for role in (Role.ADMIN, Role.COORDENACAO, Role.RECEPCAO, Role.CLINICOS):
        monkeypatch.setattr(agenda, 'current_user', FakeAgendaUser(user_id=3, role=role))

        clause, params = agenda._consulta_scope_clause('c.dentista_id')

        assert clause == ''
        assert params == []


def test_only_specific_admin_exception_is_agenda_professional(monkeypatch):
    captured = {}

    def fake_query(sql, params=None, one=False):
        captured['sql'] = sql
        captured['params'] = params
        captured['one'] = one
        return {'id': params[0]} if params and params[0] == 12 else None

    monkeypatch.setattr(agenda, 'query', fake_query)

    assert agenda._is_agenda_professional(99) is False
    assert agenda._is_agenda_professional(12) is True
    assert Role.ADMIN not in captured['params']
    assert Role.CLINICOS in captured['params']
    assert 12 in captured['params']
    assert captured['one'] is True


def test_specific_admin_exception_is_listed_with_clinical_users(monkeypatch):
    captured = {}

    def fake_query(sql, params=None):
        captured['sql'] = sql
        captured['params'] = params
        return []

    monkeypatch.setattr(agenda, 'query', fake_query)

    agenda._list_clinical_users()

    assert 'role IN' in captured['sql']
    assert 'id IN' in captured['sql']
    assert Role.CLINICOS in captured['params']
    assert Role.ADMIN not in captured['params']
    assert 12 in captured['params']


def test_role_outside_full_scope_is_blocked_from_agenda(monkeypatch):
    monkeypatch.setattr(agenda, 'current_user', FakeAgendaUser(user_id=7, role=Role.CME))

    clause, params = agenda._consulta_scope_clause('c.dentista_id')

    assert clause == ' AND 1 = 0'
    assert params == []


def test_get_scoped_consulta_blocks_role_outside_full_scope(monkeypatch):
    captured = {}

    def fake_query(sql, params=None, one=False):
        captured['sql'] = sql
        captured['params'] = params
        captured['one'] = one
        return None

    monkeypatch.setattr(agenda, 'current_user', FakeAgendaUser(user_id=7, role=Role.CME))
    monkeypatch.setattr(agenda, 'query', fake_query)

    agenda._get_scoped_consulta(55)

    assert 'AND 1 = 0' in captured['sql']
    assert captured['params'] == (55,)
    assert captured['one'] is True


def test_clinical_user_creates_appointment_for_any_clinical_user(monkeypatch):
    app = Flask(__name__)
    app.config['LOGIN_DISABLED'] = True
    app.secret_key = 'test'
    app.register_blueprint(agenda.agenda_bp)

    captured = {}

    def fake_execute(sql, params=None):
        captured['sql'] = sql
        captured['params'] = params
        return 123

    monkeypatch.setattr(agenda, 'current_user', FakeAgendaUser(user_id=7, role=Role.CLINICOS))
    monkeypatch.setattr(agenda, '_is_agenda_professional', lambda user_id: user_id == 99)
    monkeypatch.setattr(agenda, 'execute', fake_execute)
    monkeypatch.setattr(agenda, 'audit_log', lambda *args, **kwargs: None)

    with app.test_request_context(
        '/agenda/nova',
        method='POST',
        data={
            'patient_id': '10',
            'dentista_id': '99',
            'data_consulta': '2026-06-15T10:00',
            'duracao_minutos': '30',
            'execution_unit': 'unidade_principal',
            'observacoes': 'Teste',
        },
    ):
        response = agenda.nova_consulta.__wrapped__()

    assert response.status_code == 302
    assert 'INSERT INTO consultas' in captured['sql']
    assert captured['params'][1] == 99


def test_reception_creates_appointment_for_any_clinical_user(monkeypatch):
    app = Flask(__name__)
    app.config['LOGIN_DISABLED'] = True
    app.secret_key = 'test'
    app.register_blueprint(agenda.agenda_bp)

    captured = {}

    def fake_execute(sql, params=None):
        captured['sql'] = sql
        captured['params'] = params
        return 321

    monkeypatch.setattr(
        agenda,
        'current_user',
        FakeAgendaUser(user_id=3, role=Role.RECEPCAO),
    )
    monkeypatch.setattr(agenda, '_is_agenda_professional', lambda user_id: user_id == 99)
    monkeypatch.setattr(agenda, 'execute', fake_execute)
    monkeypatch.setattr(agenda, 'audit_log', lambda *args, **kwargs: None)

    with app.test_request_context(
        '/agenda/nova',
        method='POST',
        data={
            'patient_id': '10',
            'dentista_id': '99',
            'data_consulta': '2026-06-15T10:00',
            'duracao_minutos': '45',
            'execution_unit': 'unidade_apoio',
            'observacoes': 'Agendada pela recepção',
        },
    ):
        response = agenda.nova_consulta.__wrapped__()

    assert response.status_code == 302
    assert 'INSERT INTO consultas' in captured['sql']
    assert captured['params'][0] == 10
    assert captured['params'][1] == 99
    assert captured['params'][3] == 45
    assert captured['params'][4] == 'unidade_apoio'
    assert captured['params'][6] == 3


def test_clinical_user_edits_appointment_from_another_clinical_user(monkeypatch):
    app = Flask(__name__)
    app.config['LOGIN_DISABLED'] = True
    app.secret_key = 'test'
    app.register_blueprint(agenda.agenda_bp)

    captured = {}
    existing = {
        'id': 55,
        'patient_id': 10,
        'patient_nome': 'Paciente',
        'dentista_id': 88,
        'dentista_username': 'clinico88',
        'status': 'Pendente',
        'data_consulta': agenda.datetime(2026, 6, 15, 9, 0),
    }

    def fake_execute(sql, params=None):
        captured['sql'] = sql
        captured['params'] = params

    monkeypatch.setattr(
        agenda,
        'current_user',
        FakeAgendaUser(user_id=7, role=Role.CLINICOS),
    )
    monkeypatch.setattr(agenda, '_get_scoped_consulta', lambda *args, **kwargs: existing)
    monkeypatch.setattr(agenda, '_is_agenda_professional', lambda user_id: user_id == 99)
    monkeypatch.setattr(agenda, 'execute', fake_execute)
    monkeypatch.setattr(agenda, 'audit_log', lambda *args, **kwargs: None)

    with app.test_request_context(
        '/agenda/55/editar',
        method='POST',
        data={
            'patient_id': '10',
            'dentista_id': '99',
            'data_consulta': '2026-06-16T14:30',
            'duracao_minutos': '60',
            'status': 'Confirmado',
            'execution_unit': 'unidade_principal',
            'observacoes': 'Remanejada por outro clínico',
        },
    ):
        response = agenda.editar_consulta.__wrapped__(55)

    assert response.status_code == 302
    assert 'UPDATE consultas' in captured['sql']
    assert captured['params'][1] == 99
    assert captured['params'][3] == 60
    assert captured['params'][4] == 'Confirmado'
    assert captured['params'][-1] == 55


def test_clinical_user_cancels_appointment_from_another_clinical_user(monkeypatch):
    app = Flask(__name__)
    app.config['LOGIN_DISABLED'] = True
    app.secret_key = 'test'
    app.register_blueprint(agenda.agenda_bp)

    captured = {}
    existing = {
        'id': 55,
        'patient_id': 10,
        'dentista_id': 88,
        'status': 'Confirmado',
        'data_consulta': agenda.datetime(2026, 6, 15, 9, 0),
    }

    def fake_query(sql, params=None, one=False):
        captured['query_sql'] = sql
        captured['query_params'] = params
        captured['query_one'] = one
        return existing

    def fake_execute(sql, params=None):
        captured['execute_sql'] = sql
        captured['execute_params'] = params

    monkeypatch.setattr(
        agenda,
        'current_user',
        FakeAgendaUser(user_id=7, role=Role.CLINICOS),
    )
    monkeypatch.setattr(agenda, 'query', fake_query)
    monkeypatch.setattr(agenda, 'execute', fake_execute)
    monkeypatch.setattr(agenda, 'audit_log', lambda *args, **kwargs: None)

    with app.test_request_context('/agenda/55/cancelar', method='POST'):
        response = agenda.cancelar_consulta.__wrapped__(55)

    assert response.status_code == 302
    assert 'c.dentista_id = %s' not in captured['query_sql']
    assert captured['query_params'] == (55,)
    assert captured['query_one'] is True
    assert captured['execute_sql'] == "UPDATE consultas SET status = 'Cancelado' WHERE id = %s"
    assert captured['execute_params'] == (55,)


def test_clinical_user_updates_status_from_another_clinical_user(monkeypatch):
    app = Flask(__name__)
    app.config['LOGIN_DISABLED'] = True
    app.secret_key = 'test'
    app.register_blueprint(agenda.agenda_bp)

    captured = {}
    existing = {
        'id': 55,
        'patient_id': 10,
        'dentista_id': 88,
        'status': 'Confirmado',
        'data_consulta': agenda.datetime(2026, 6, 15, 9, 0),
    }

    def fake_query(sql, params=None, one=False):
        captured['query_sql'] = sql
        captured['query_params'] = params
        captured['query_one'] = one
        return existing

    def fake_execute(sql, params=None):
        captured['execute_sql'] = sql
        captured['execute_params'] = params

    monkeypatch.setattr(
        agenda,
        'current_user',
        FakeAgendaUser(user_id=7, role=Role.CLINICOS),
    )
    monkeypatch.setattr(agenda, 'query', fake_query)
    monkeypatch.setattr(agenda, 'execute', fake_execute)
    monkeypatch.setattr(agenda, 'audit_log', lambda *args, **kwargs: None)

    with app.test_request_context('/agenda/55/status', method='POST', data={'status': 'Realizado'}):
        response = agenda.atualizar_status.__wrapped__(55)

    assert response.status_code == 302
    assert 'c.dentista_id = %s' not in captured['query_sql']
    assert captured['query_params'] == (55,)
    assert captured['query_one'] is True
    assert captured['execute_sql'] == 'UPDATE consultas SET status = %s WHERE id = %s'
    assert captured['execute_params'] == ('Realizado', 55)


def test_reception_edits_appointment_from_another_clinical_user(monkeypatch):
    app = Flask(__name__)
    app.config['LOGIN_DISABLED'] = True
    app.secret_key = 'test'
    app.register_blueprint(agenda.agenda_bp)

    captured = {}
    existing = {
        'id': 55,
        'patient_id': 10,
        'patient_nome': 'Paciente',
        'dentista_id': 88,
        'dentista_username': 'clinico88',
        'status': 'Pendente',
        'data_consulta': agenda.datetime(2026, 6, 15, 9, 0),
    }

    def fake_execute(sql, params=None):
        captured['sql'] = sql
        captured['params'] = params

    monkeypatch.setattr(
        agenda,
        'current_user',
        FakeAgendaUser(user_id=3, role=Role.RECEPCAO),
    )
    monkeypatch.setattr(agenda, '_get_scoped_consulta', lambda *args, **kwargs: existing)
    monkeypatch.setattr(agenda, '_is_agenda_professional', lambda user_id: user_id == 99)
    monkeypatch.setattr(agenda, 'execute', fake_execute)
    monkeypatch.setattr(agenda, 'audit_log', lambda *args, **kwargs: None)

    with app.test_request_context(
        '/agenda/55/editar',
        method='POST',
        data={
            'patient_id': '10',
            'dentista_id': '99',
            'data_consulta': '2026-06-16T14:30',
            'duracao_minutos': '60',
            'status': 'Confirmado',
            'execution_unit': 'unidade_principal',
            'observacoes': 'Remanejada pela recepção',
        },
    ):
        response = agenda.editar_consulta.__wrapped__(55)

    assert response.status_code == 302
    assert 'UPDATE consultas' in captured['sql']
    assert captured['params'][1] == 99
    assert captured['params'][3] == 60
    assert captured['params'][4] == 'Confirmado'
    assert captured['params'][-1] == 55


def test_atualizar_status_does_not_update_missing_consulta(monkeypatch):
    app = Flask(__name__)
    app.config['LOGIN_DISABLED'] = True
    app.secret_key = 'test'
    app.register_blueprint(agenda.agenda_bp)

    execute_called = False

    def fake_execute(*args, **kwargs):
        nonlocal execute_called
        execute_called = True

    monkeypatch.setattr(agenda, 'current_user', FakeAgendaUser(user_id=7, role=Role.CLINICOS))
    monkeypatch.setattr(agenda, '_can_manage', lambda: True)
    monkeypatch.setattr(agenda, 'query', lambda *args, **kwargs: None)
    monkeypatch.setattr(agenda, 'execute', fake_execute)
    monkeypatch.setattr(agenda, 'audit_log', lambda *args, **kwargs: None)

    with app.test_request_context('/agenda/999/status', method='POST', data={'status': 'Faltou'}):
        response = agenda.atualizar_status(999)

    assert response.status_code == 302
    assert execute_called is False
