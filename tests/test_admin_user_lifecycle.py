from datetime import datetime
import sys
import types

from flask import Flask


class FakeCeleryConfig(dict):
    def __getattr__(self, name):
        return self.get(name)

    def __setattr__(self, name, value):
        self[name] = value


class FakeCelery:
    class Task:
        pass

    def __init__(self, *args, **kwargs):
        self.conf = FakeCeleryConfig()

    def task(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator


celery_module = types.ModuleType('celery')
celery_module.Celery = FakeCelery
celery_schedules_module = types.ModuleType('celery.schedules')
celery_schedules_module.crontab = lambda *args, **kwargs: ('crontab', args, kwargs)
sys.modules.setdefault('celery', celery_module)
sys.modules.setdefault('celery.schedules', celery_schedules_module)

import blueprints.admin as admin
from constants import Role


class FakeAdminUser:
    id = 8
    username = 'admin'
    role = Role.ADMIN
    is_authenticated = True

    def can(self, permission):
        return permission in {'users:view', 'users:write'}


def _app():
    app = Flask(__name__)
    app.config['LOGIN_DISABLED'] = True
    app.secret_key = 'test'
    app.register_blueprint(admin.admin_bp)
    return app


def test_user_without_access_or_references_can_be_deleted(monkeypatch):
    def fake_query(sql, params=(), one=False):
        if 'FROM users' in sql:
            return {
                'id': 13,
                'username': 'demo.dentista',
                'role': Role.CLINICOS,
                'last_login_at': None,
                'first_access_completed_at': None,
                'email_confirmed_at': None,
                'password_changed_at': None,
                'password_reset_used_at': None,
                'password_reset_token_hash': None,
            }
        if 'information_schema.table_constraints' in sql:
            return []
        raise AssertionError(sql)

    monkeypatch.setattr(admin, 'query', fake_query)

    summary = admin._get_user_link_summary(13)

    assert summary == {'has_links': False, 'link_count': 0, 'reasons': []}


def test_user_with_login_or_references_must_be_deactivated(monkeypatch):
    def fake_query(sql, params=(), one=False):
        if 'information_schema.table_constraints' in sql:
            return [
                {'table_schema': 'public', 'table_name': 'audit_logs', 'column_name': 'user_id'},
            ]
        if 'COUNT(*) AS total' in sql:
            return {'total': 2}
        raise AssertionError(sql)

    monkeypatch.setattr(admin, 'query', fake_query)

    summary = admin._get_user_link_summary(
        10,
        {
            'id': 10,
            'last_login_at': datetime(2026, 6, 17, 10, 30),
            'first_access_completed_at': None,
            'email_confirmed_at': None,
            'password_changed_at': None,
            'password_reset_used_at': None,
            'password_reset_token_hash': None,
        },
    )

    assert summary['has_links'] is True
    assert summary['link_count'] == 3
    assert 'login/acesso ao sistema' in summary['reasons']
    assert 'auditoria: 2' in summary['reasons']


def test_delete_user_blocks_when_history_exists(monkeypatch):
    app = _app()
    executed = []
    audits = []

    def fake_query(sql, params=(), one=False):
        if 'FROM users' in sql:
            return {
                'id': 10,
                'username': 'erika',
                'role': Role.CLINICOS,
                'active': True,
                'last_login_at': None,
                'first_access_completed_at': None,
                'email_confirmed_at': None,
                'password_changed_at': None,
                'password_reset_used_at': None,
                'password_reset_token_hash': None,
            }
        if 'information_schema.table_constraints' in sql:
            return [
                {'table_schema': 'public', 'table_name': 'atendimentos', 'column_name': 'validator_id'},
            ]
        if 'COUNT(*) AS total' in sql:
            return {'total': 1}
        raise AssertionError(sql)

    monkeypatch.setattr(admin, 'current_user', FakeAdminUser())
    monkeypatch.setattr(admin, 'query', fake_query)
    monkeypatch.setattr(admin, 'execute', lambda *args, **kwargs: executed.append((args, kwargs)))
    monkeypatch.setattr(admin, 'audit_log', lambda **kwargs: audits.append(kwargs))

    with app.test_request_context('/admin/users/delete/10', method='POST'):
        response = admin.delete_user(10)

    assert response.status_code == 302
    assert executed == []
    assert audits[0]['action'] == 'user_delete_blocked'
    assert audits[0]['status'] == 'denied'


def test_deactivate_user_marks_access_inactive(monkeypatch):
    app = _app()
    executed = []
    audits = []

    monkeypatch.setattr(admin, 'current_user', FakeAdminUser())
    monkeypatch.setattr(
        admin,
        'query',
        lambda *args, **kwargs: {
            'id': 10,
            'username': 'erika',
            'role': Role.CLINICOS,
            'active': True,
        },
    )
    monkeypatch.setattr(admin, 'execute', lambda sql, params=(): executed.append((sql, params)))
    monkeypatch.setattr(admin, 'audit_log', lambda **kwargs: audits.append(kwargs))

    with app.test_request_context('/admin/users/deactivate/10', method='POST'):
        response = admin.deactivate_user(10)

    assert response.status_code == 302
    assert executed == [('UPDATE users SET active = FALSE WHERE id = %s', (10,))]
    assert audits[0]['action'] == 'user_deactivated'
