import datetime as dt

import services.esus_export_service as esus_export_service
import services.sigtap_service as sigtap_service
from constants import Role, role_has_permission
from services.esus_export_service import (
    build_esus_payload,
    classify_esus_missing_fields,
    get_esus_dashboard,
    month_period,
    update_treatment_sigtap,
)
from services.sigtap_service import (
    normalize_sigtap_code,
    parse_tb_procedimento_line,
    split_sigtap_code,
    upsert_sigtap_procedure,
)


def test_sigtap_code_normalization_and_split():
    assert normalize_sigtap_code('03.070.300-40') == '0307030040'
    assert normalize_sigtap_code('123') == ''

    parts = split_sigtap_code('0307030040')

    assert parts['group_code'] == '03'
    assert parts['subgroup_code'] == '07'
    assert parts['form_code'] == '03'


def test_parse_tb_procedimento_fixed_width_line():
    name = 'PROFILAXIA / REMOÇÃO DA PLACA BACTERIANA'
    line = '0307030040' + name.ljust(250) + 'M'

    assert parse_tb_procedimento_line(line) == ('0307030040', name)


def test_upsert_sigtap_procedure_persists_group_fields(monkeypatch):
    captured = {}

    def fake_execute(sql, params=()):
        captured['sql'] = sql
        captured['params'] = params

    monkeypatch.setattr(sigtap_service, 'execute', fake_execute)

    code = upsert_sigtap_procedure('0307030040', 'Profilaxia', competence='202605')

    assert code == '0307030040'
    assert 'INSERT INTO sigtap_procedures' in captured['sql']
    assert captured['params'][0] == '0307030040'
    assert captured['params'][1] == '202605'
    assert captured['params'][3] == '03'
    assert captured['params'][4] == '07'
    assert captured['params'][5] == '03'


def test_esus_month_period():
    start, end = month_period('2026-05')

    assert start == dt.date(2026, 5, 1)
    assert end == dt.date(2026, 5, 31)


def test_build_esus_payload_uses_only_sigtap_ready_records(monkeypatch):
    rows = [
        {
            'id': 1,
            'patient_id': 10,
            'dente': '46',
            'descricao': 'Profilaxia',
            'sigtap_code': '0307030040',
            'sigtap_competence': '202605',
            'sigtap_name': 'PROFILAXIA / REMOÇÃO DA PLACA BACTERIANA',
            'criado_em': dt.datetime(2026, 5, 10, 9, 30),
            'professor_id': 7,
            'cns': '123',
            'cpf': '000',
            'patient_name': 'Paciente Teste',
            'cro': '1234',
            'cro_uf': 'AL',
            'professional_name': 'Dra. Teste',
        },
        {
            'id': 2,
            'patient_id': 11,
            'dente': '11',
            'descricao': 'Procedimento sem código',
            'sigtap_code': None,
            'sigtap_competence': None,
            'sigtap_name': None,
            'criado_em': dt.datetime(2026, 5, 11, 9, 30),
            'professor_id': 7,
            'cns': '456',
            'cpf': '111',
            'patient_name': 'Paciente Sem Código',
            'cro': '1234',
            'cro_uf': 'AL',
            'professional_name': 'Dra. Teste',
        },
    ]

    monkeypatch.setattr(esus_export_service, 'list_completed_procedures_for_esus', lambda month_value=None: rows)
    monkeypatch.setattr(
        esus_export_service,
        'get_esus_settings',
        lambda: {'cnes': '1234567', 'ine': '0000000000'},
    )

    payload, payload_hash = build_esus_payload('2026-05')

    assert len(payload['records']) == 1
    assert payload['records'][0]['procedure']['sigtap_code'] == '0307030040'
    assert payload['summary']['total'] == 2
    assert payload['summary']['ready'] == 1
    assert payload['summary']['missing_sigtap'] == 1
    assert len(payload_hash) == 64


def test_integrations_permissions_are_restricted():
    assert role_has_permission(Role.ADMIN, 'integrations:view')
    assert role_has_permission(Role.ADMIN, 'integrations:write')
    assert role_has_permission(Role.AUDITORIA, 'integrations:view')
    assert role_has_permission(Role.AUDITORIA, 'integrations:write') is False
    assert role_has_permission(Role.BI, 'integrations:view')
    assert role_has_permission(Role.SSA, 'integrations:view') is False


def test_classify_esus_missing_fields_flags_city_and_patient_data():
    row = {
        'sigtap_code': '0307030040',
        'sigtap_competence': '202605',
        'cns': None,
        'cpf': None,
        'professor_id': None,
        'cro': None,
    }

    missing = classify_esus_missing_fields(row, settings={'cnes': '', 'ine': ''})

    assert 'CNS/CPF' in missing
    assert 'profissional' in missing
    assert 'CRO' in missing
    assert 'CNES' in missing
    assert 'INE/equipe' in missing


def test_update_treatment_sigtap_uses_loaded_catalog(monkeypatch):
    captured = {}
    sigtap = {
        'code': '0307030040',
        'competence': '202605',
        'name': 'PROFILAXIA / REMOÇÃO DA PLACA BACTERIANA',
    }

    monkeypatch.setattr(esus_export_service, 'get_sigtap_procedure', lambda code, competence=None: sigtap)

    def fake_execute(sql, params=()):
        captured['sql'] = sql
        captured['params'] = params

    monkeypatch.setattr(esus_export_service, 'execute', fake_execute)

    result = update_treatment_sigtap(88, '0307030040', '202605')

    assert result == sigtap
    assert 'UPDATE tratamento_procedimentos' in captured['sql']
    assert captured['params'] == ('0307030040', '202605', 'PROFILAXIA / REMOÇÃO DA PLACA BACTERIANA', 88)


def test_get_esus_dashboard_composes_operational_context(monkeypatch):
    monkeypatch.setattr(
        esus_export_service,
        'build_esus_readiness',
        lambda month_value=None: {'total': 1, 'ready': 1, 'missing_sigtap': 0, 'incomplete': 0},
    )
    monkeypatch.setattr(esus_export_service, 'get_esus_settings', lambda: {'environment': 'homologacao'})
    monkeypatch.setattr(esus_export_service, 'list_procedures_missing_sigtap', lambda limit=80: [])
    monkeypatch.setattr(esus_export_service, 'list_esus_batches', lambda limit=12: [{'id': 1}])

    dashboard = get_esus_dashboard('2026-05')

    assert dashboard['month'] == '2026-05'
    assert dashboard['readiness']['ready'] == 1
    assert dashboard['settings']['environment'] == 'homologacao'
    assert dashboard['batches'][0]['id'] == 1
