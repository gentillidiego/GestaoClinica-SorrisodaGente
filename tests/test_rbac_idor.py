import sys
import types
from types import SimpleNamespace

import pytest
from flask import Flask


class _FakePdfTask:
    @staticmethod
    def delay(*_args, **_kwargs):
        return SimpleNamespace(id='test-task')


class _FakeCelery:
    def task(self, *args, **kwargs):
        def decorator(func):
            func.delay = lambda *call_args, **call_kwargs: SimpleNamespace(
                id='test-task',
            )
            return func

        return decorator


class _FakeCache:
    def cached(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator


fake_pdf_tasks = types.ModuleType('tasks.pdf_tasks')
fake_pdf_tasks.generate_pdf_task = _FakePdfTask()
fake_celery_result = types.ModuleType('celery.result')
fake_celery_result.AsyncResult = lambda *_args, **_kwargs: None
fake_celery_app = types.ModuleType('celery_app')
fake_celery_app.celery = _FakeCelery()
fake_extensions = types.ModuleType('extensions')
fake_extensions.cache = _FakeCache()
sys.modules.setdefault('tasks.pdf_tasks', fake_pdf_tasks)
sys.modules.setdefault('celery.result', fake_celery_result)
sys.modules.setdefault('celery_app', fake_celery_app)
sys.modules.setdefault('extensions', fake_extensions)

import blueprints.documents as documents_module
import blueprints.exams as exams_module
import services.security_service as security_module
from blueprints.anamnesis import anamnesis_bp
from blueprints.documents import documents_bp
from blueprints.endodontia import endodontia_bp
from blueprints.exams import exams_bp
from blueprints.patients import patients_bp
from blueprints.prosthesis import _patient_scope_matches, prosthesis_bp
from blueprints.radiologia import radiologia_bp
from blueprints.analises_clinicas import analises_clinicas_bp
from constants import ACTIVE_ROLE_LABELS, Role
from services.authorization_service import (
    TAB_ACCESS_RULES,
    get_access_rule,
    rule_allows,
)
from utils import User


ACTIVE_ROLES = tuple(ACTIVE_ROLE_LABELS)


def _user(role):
    return User(
        id=1,
        username=f'teste-{role}',
        role=role,
        active=True,
    )


def _allowed_roles(endpoint, method='GET'):
    access_rule = get_access_rule(endpoint=endpoint, method=method)
    assert access_rule is not None
    return {
        role
        for role in ACTIVE_ROLES
        if rule_allows(_user(role), access_rule)
    }


@pytest.mark.parametrize(
    ('endpoint', 'method', 'expected_roles'),
    (
        (
            'patients.list_patients',
            'GET',
            {
                Role.ADMIN,
                Role.COORDENACAO,
                Role.CLINICOS,
                Role.RECEPCAO,
                Role.CME,
                Role.RADIOLOGIA,
                Role.ANALISES_CLINICAS,
                Role.AUDITORIA,
            },
        ),
        (
            'patients.register',
            'GET',
            {Role.ADMIN, Role.CLINICOS, Role.RECEPCAO},
        ),
        ('patients.delete_patient', 'POST', {Role.ADMIN}),
        (
            'anamnesis.view_anamnesis',
            'GET',
            {Role.ADMIN, Role.COORDENACAO, Role.CLINICOS, Role.AUDITORIA},
        ),
        ('anamnesis.form', 'GET', {Role.ADMIN, Role.CLINICOS}),
        (
            'patients.pending_treatments',
            'GET',
            {Role.ADMIN, Role.COORDENACAO, Role.CLINICOS, Role.AUDITORIA},
        ),
        ('patients.add_treatment', 'POST', {Role.ADMIN, Role.CLINICOS}),
        ('patients.add_atendimento', 'POST', {Role.ADMIN, Role.CLINICOS}),
        (
            'exams.list_exams',
            'GET',
            {Role.ADMIN, Role.CLINICOS, Role.RADIOLOGIA},
        ),
        (
            'exams.clinico_laboratorial',
            'GET',
            {Role.ADMIN, Role.CLINICOS, Role.CME, Role.ANALISES_CLINICAS},
        ),
        ('exams.delete_exam', 'POST', {Role.ADMIN, Role.CLINICOS}),
        (
            'exams.solicitar_imagem',
            'GET',
            {Role.ADMIN, Role.CLINICOS, Role.RADIOLOGIA},
        ),
        (
            'exams.solicitar_clinico_laboratorial',
            'GET',
            {Role.ADMIN, Role.CLINICOS, Role.CME, Role.ANALISES_CLINICAS},
        ),
        (
            'radiologia.solicitacoes',
            'GET',
            {Role.ADMIN, Role.RADIOLOGIA},
        ),
        (
            'analises_clinicas.solicitacoes',
            'GET',
            {Role.ADMIN, Role.ANALISES_CLINICAS},
        ),
        (
            'documents.add_receituario',
            'POST',
            {Role.ADMIN, Role.CLINICOS, Role.RECEPCAO},
        ),
        (
            'documents.signature_receipt',
            'GET',
            {Role.ADMIN, Role.CLINICOS},
        ),
        (
            'endodontia.followup',
            'GET',
            {Role.ADMIN, Role.CLINICOS},
        ),
        (
            'endodontia.add_element',
            'POST',
            {Role.ADMIN, Role.CLINICOS},
        ),
        (
            'prosthesis.create_case',
            'POST',
            {Role.ADMIN, Role.CLINICOS},
        ),
    ),
)
def test_route_policy_matches_the_ten_active_profiles(
    endpoint,
    method,
    expected_roles,
):
    assert set(ACTIVE_ROLES) == {
        Role.ADMIN,
        Role.COORDENACAO,
        Role.CLINICOS,
        Role.RECEPCAO,
        Role.CME,
        Role.RADIOLOGIA,
        Role.ANALISES_CLINICAS,
        Role.COMUNICACAO,
        Role.SSA_SMS,
        Role.AUDITORIA,
    }
    assert _allowed_roles(endpoint, method) == expected_roles


def test_every_clinical_route_has_a_backend_access_policy():
    app = Flask(__name__)
    for blueprint in (
        patients_bp,
        anamnesis_bp,
        exams_bp,
        documents_bp,
        endodontia_bp,
        prosthesis_bp,
        radiologia_bp,
        analises_clinicas_bp,
    ):
        app.register_blueprint(blueprint)

    missing = []
    protected_blueprints = {
        'patients',
        'anamnesis',
        'exams',
        'documents',
        'endodontia',
        'prosthesis',
        'radiologia',
        'analises_clinicas',
    }
    for flask_rule in app.url_map.iter_rules():
        if flask_rule.endpoint.split('.', 1)[0] not in protected_blueprints:
            continue
        for method in sorted(flask_rule.methods - {'HEAD', 'OPTIONS'}):
            if get_access_rule(endpoint=flask_rule.endpoint, method=method) is None:
                missing.append(f'{method} {flask_rule.endpoint} {flask_rule.rule}')

    assert missing == []


def test_denied_json_access_returns_403_and_is_audited(monkeypatch):
    app = Flask(__name__)
    calls = []
    actor = SimpleNamespace(
        id=7,
        username='sem-permissao',
        role=Role.RECEPCAO,
        is_authenticated=True,
    )
    monkeypatch.setattr(security_module, 'current_user', actor)
    monkeypatch.setattr(
        security_module,
        'audit_log',
        lambda **kwargs: calls.append(kwargs),
    )

    with app.test_request_context(
        '/patients/delete/9',
        method='POST',
        headers={'Accept': 'application/json'},
    ):
        response, status = security_module.deny_access(
            permissions={
                'all_of': ['patients:delete'],
                'any_of': [],
            },
            patient_id=9,
        )

    assert status == 403
    assert response.get_json() == {'error': 'Acesso negado.'}
    assert calls == [{
        'action': 'access_denied',
        'module': 'security',
        'patient_id': 9,
        'status': 'denied',
        'details': {
            'reason': 'permission_denied',
            'endpoint': None,
            'permissions': {
                'all_of': ['patients:delete'],
                'any_of': [],
            },
        },
    }]


@pytest.mark.parametrize(
    ('tab_name', 'expected_roles'),
    (
        (
            'tab-anamnese',
            {Role.ADMIN, Role.COORDENACAO, Role.CLINICOS, Role.AUDITORIA},
        ),
        (
            'tab-exames',
            {Role.ADMIN, Role.CLINICOS, Role.RADIOLOGIA},
        ),
        (
            'tab-atendimento',
            {Role.ADMIN, Role.COORDENACAO, Role.CLINICOS, Role.AUDITORIA},
        ),
        (
            'tab-endodontia',
            {Role.ADMIN, Role.CLINICOS},
        ),
        (
            'tab-protese',
            {Role.ADMIN, Role.CLINICOS},
        ),
        (
            'tab-linha-tempo',
            {Role.ADMIN, Role.COORDENACAO, Role.CLINICOS, Role.AUDITORIA},
        ),
    ),
)
def test_patient_tabs_follow_the_profile_matrix(tab_name, expected_roles):
    access_rule = TAB_ACCESS_RULES[tab_name]
    allowed = {
        role
        for role in ACTIVE_ROLES
        if rule_allows(_user(role), access_rule)
    }
    assert allowed == expected_roles


def test_exam_scope_uses_exam_anamnesis_and_type_together(monkeypatch):
    captured = {}

    def fake_query(sql, params=(), one=False):
        captured['sql'] = sql
        captured['params'] = params
        captured['one'] = one
        return {'id': 77}

    monkeypatch.setattr(exams_module, 'query', fake_query)

    result = exams_module._get_scoped_exam(12, 77, 'imagem')

    assert result == {'id': 77}
    assert captured['params'] == (77, 12, 'imagem')
    assert 'id = %s' in captured['sql']
    assert 'anamnesis_id = %s' in captured['sql']
    assert 'tipo = %s' in captured['sql']
    assert captured['one'] is True


@pytest.mark.parametrize(
    ('filename', 'expected_params'),
    (
        ('receituario_31_9.pdf', (31, 9)),
        ('atestado_9_42.pdf', (9, 42)),
        ('declaracao_comparecimento_9_42.pdf', (9, 42)),
        ('encaminhamento_18_9.pdf', (18, 9)),
    ),
)
def test_clinical_pdf_filename_is_scoped_to_its_source_record(
    monkeypatch,
    filename,
    expected_params,
):
    captured = {}

    def fake_query(sql, params=(), one=False):
        captured['sql'] = sql
        captured['params'] = params
        captured['one'] = one
        return None

    monkeypatch.setattr(documents_module, 'query', fake_query)

    context = documents_module._clinical_pdf_context(filename)

    assert context['matched'] is True
    assert context['record'] is None
    assert captured['params'] == expected_params
    assert 'patient_id = %s' in captured['sql']
    assert captured['one'] is True


def test_clinical_pdf_is_denied_when_filename_ids_do_not_match_a_record(
    monkeypatch,
):
    user = SimpleNamespace(
        id=5,
        role=Role.CLINICOS,
        is_admin=False,
        can=lambda _permission: True,
    )
    monkeypatch.setattr(documents_module, 'current_user', user)
    monkeypatch.setattr(documents_module, 'query', lambda *args, **kwargs: None)

    assert documents_module._can_access_pdf('receituario_31_999.pdf') is False


def test_estomatologia_pdf_requires_source_specific_permission(monkeypatch):
    permissions = {'patients:view', 'documents:generate'}
    user = SimpleNamespace(
        id=5,
        role=Role.RECEPCAO,
        is_admin=False,
        can=lambda permission: permission in permissions,
    )
    monkeypatch.setattr(documents_module, 'current_user', user)
    monkeypatch.setattr(
        documents_module,
        'query',
        lambda *args, **kwargs: {'id': 18, 'patient_id': 9},
    )

    assert documents_module._can_access_pdf('encaminhamento_18_9.pdf') is False


@pytest.mark.parametrize(
    ('requested_patient_id', 'actual_patient_id', 'expected'),
    (
        ('9', 9, True),
        (9, 9, True),
        ('10', 9, False),
        ('inválido', 9, False),
    ),
)
def test_prosthesis_patient_scope_rejects_cross_patient_ids(
    requested_patient_id,
    actual_patient_id,
    expected,
):
    assert (
        _patient_scope_matches(requested_patient_id, actual_patient_id)
        is expected
    )
