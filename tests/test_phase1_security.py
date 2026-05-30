from types import SimpleNamespace

from flask import Flask

import services.security_service as security_service
from constants import (
    MODULE_PERMISSIONS,
    Role,
    get_role_choices,
    get_role_label,
    role_has_permission,
)
from utils import User


def test_role_choices_exclude_legacy_atendimento():
    choices = dict(get_role_choices())

    assert Role.ATENDIMENTO_LEGACY not in choices
    assert choices[Role.ADMIN] == 'Administrador'
    assert choices[Role.AUDITORIA] == 'Auditoria'


def test_role_permissions_cover_admin_and_limit_auditoria():
    for permission in MODULE_PERMISSIONS:
        assert role_has_permission(Role.ADMIN, permission)

    assert role_has_permission(Role.AUDITORIA, 'audit:view')
    assert not role_has_permission(Role.AUDITORIA, 'users:write')
    assert not role_has_permission('perfil_inexistente', 'dashboard:view')


def test_role_label_falls_back_to_original_value():
    assert get_role_label(Role.ESTOMATOLOGIA) == 'Estomatologia'
    assert get_role_label('perfil_customizado') == 'perfil_customizado'
    assert get_role_label(None) == 'Usuário'


def test_user_active_state_and_permission_helper():
    active_user = User(id=1, username='admin', role=Role.ADMIN, active=True)
    inactive_user = User(id=2, username='bloqueado', role=Role.RECEPCAO, active=False)

    assert active_user.is_active
    assert not inactive_user.is_active
    assert active_user.can('audit:view')
    assert not inactive_user.can('audit:view')


def test_audit_log_records_request_context_and_actor(monkeypatch):
    calls = []
    app = Flask(__name__)

    actor = SimpleNamespace(
        is_authenticated=True,
        id=7,
        username='auditor',
        role=Role.AUDITORIA,
    )

    monkeypatch.setattr(security_service, 'current_user', actor)
    monkeypatch.setattr(security_service, 'execute', lambda sql, params: calls.append((sql, params)))

    with app.test_request_context(
        '/admin/audit?module=auth',
        method='POST',
        headers={
            'X-Forwarded-For': '203.0.113.10, 10.0.0.1',
            'User-Agent': 'pytest-agent',
        },
    ):
        security_service.audit_log(
            action='user_updated',
            module='admin',
            entity_type='user',
            entity_id=12,
            patient_id=34,
            details={'campo': 'role', 'novo': Role.AUDITORIA},
        )

    assert len(calls) == 1
    _, params = calls[0]
    assert params[0] == 7
    assert params[1] == 'auditor'
    assert params[2] == Role.AUDITORIA
    assert params[3] == 'user_updated'
    assert params[4] == 'admin'
    assert params[6] == '12'
    assert params[7] == 34
    assert params[8] == '203.0.113.10'
    assert params[9] == 'pytest-agent'
    assert params[10] == 'POST'
    assert params[11] == '/admin/audit'
    assert params[12] == 'success'
    assert '"novo": "auditoria"' in params[13]


def test_list_audit_logs_builds_filtered_query(monkeypatch):
    captured = {}

    def fake_query(sql, params=(), one=False):
        captured['sql'] = sql
        captured['params'] = params
        captured['one'] = one
        return [{'id': 1}]

    monkeypatch.setattr(security_service, 'query', fake_query)

    result = security_service.list_audit_logs(
        filters={
            'user_id': '7',
            'module': 'auth',
            'action': 'login',
            'patient_id': '34',
            'status': 'failed',
        },
        limit=25,
    )

    assert result == [{'id': 1}]
    assert 'user_id = %s' in captured['sql']
    assert 'module = %s' in captured['sql']
    assert 'action ILIKE %s' in captured['sql']
    assert 'patient_id = %s' in captured['sql']
    assert 'status = %s' in captured['sql']
    assert captured['params'] == ('7', 'auth', '%login%', '34', 'failed', 25)
    assert captured['one'] is False
