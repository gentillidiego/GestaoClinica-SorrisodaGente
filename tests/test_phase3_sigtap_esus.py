import datetime as dt

import services.esus_export_service as esus_export_service
import services.sigtap_service as sigtap_service
from constants import (
    Role,
    role_has_permission,
    role_requires_dental_license,
    role_requires_professional_data,
)
from services.esus_export_service import (
    build_esus_payload,
    build_batch_transmission_readiness,
    build_esus_meeting_checklist,
    build_homologation_status,
    classify_esus_missing_fields,
    get_esus_batch_detail,
    get_esus_dashboard,
    get_esus_homologation_report,
    month_period,
    procedure_locked_by_validated_batch,
    register_esus_export_batch,
    simulate_esus_transmission_preflight,
    update_treatment_sigtap,
    validate_esus_export_batch,
)
from services.sigtap_service import (
    build_sigtap_specialty_groups,
    is_sigtap_code_allowed_for_specialty,
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


def test_sigtap_specialty_groups_filter_treatment_codes(monkeypatch):
    monkeypatch.setattr(sigtap_service, 'get_latest_sigtap_competence', lambda: '202606')
    monkeypatch.setattr(sigtap_service, 'get_sigtap_procedure', lambda code, competence=None: None)

    groups = build_sigtap_specialty_groups()
    endodontia = next(group for group in groups if group['value'] == 'endodontia')

    assert any(item['code'] == '0307020061' for item in endodontia['procedures'])
    assert is_sigtap_code_allowed_for_specialty('endodontia', '0307020061')
    assert not is_sigtap_code_allowed_for_specialty('endodontia', '0414020138')


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
            'cns': '123456789012345',
            'cpf': '12345678901',
            'patient_name': 'Paciente Teste',
            'professional_cns': '700000000000000',
            'professional_cbo': '223208',
            'professional_cnes': '1234567',
            'professional_ine': '0000000000',
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
            'cns': '456789012345678',
            'cpf': '98765432100',
            'patient_name': 'Paciente Sem Código',
            'professional_cns': '700000000000000',
            'professional_cbo': '223208',
            'professional_cnes': '1234567',
            'professional_ine': '0000000000',
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
    assert role_has_permission(Role.COORDENACAO, 'integrations:view')
    assert role_has_permission(Role.COORDENACAO, 'integrations:write')
    assert role_has_permission(Role.AUDITORIA, 'integrations:view')
    assert role_has_permission(Role.AUDITORIA, 'integrations:write') is False
    assert role_has_permission(Role.BI, 'integrations:view')
    assert role_has_permission(Role.SSA, 'integrations:view') is False


def test_professional_roles_require_esus_identification_fields():
    assert role_requires_professional_data(Role.CLINICOS)
    assert role_requires_professional_data(Role.CME)
    assert role_requires_professional_data(Role.RADIOLOGIA)
    assert role_requires_professional_data(Role.DENTISTA)
    assert role_requires_professional_data(Role.TRIAGEM) is False
    assert role_requires_dental_license(Role.CLINICOS)
    assert role_requires_dental_license(Role.DENTISTA)
    assert role_requires_dental_license(Role.TRIAGEM) is False
    assert role_requires_professional_data(Role.RECEPCAO) is False


def test_classify_esus_missing_fields_flags_city_and_patient_data():
    row = {
        'sigtap_code': '0307030040',
        'sigtap_competence': '202605',
        'cns': None,
        'cpf': None,
        'professor_id': None,
        'professional_cns': None,
        'professional_cbo': None,
        'professional_cnes': None,
        'professional_ine': None,
        'cro': None,
    }

    missing = classify_esus_missing_fields(row, settings={'cnes': '', 'ine': ''})

    assert 'CNS/CPF' in missing
    assert 'profissional' in missing
    assert 'CNS profissional' in missing
    assert 'CBO' in missing
    assert 'CRO' in missing
    assert 'CNES' in missing
    assert 'INE/equipe' in missing


def test_classify_esus_missing_fields_flags_invalid_formats():
    row = {
        'sigtap_code': '0307030040',
        'sigtap_competence': '202605',
        'cns': '123',
        'cpf': '',
        'professor_id': 9,
        'professional_cns': '700',
        'professional_cbo': '223',
        'professional_cnes': '123',
        'professional_ine': '000',
        'cro': '1234',
        'cro_uf': 'A1',
    }

    missing = classify_esus_missing_fields(row, settings={'cnes': '123', 'ine': '000'})

    assert 'CNS/CPF inválido' in missing
    assert 'CNS profissional inválido' in missing
    assert 'CBO inválido' in missing
    assert 'CNES inválido' in missing
    assert 'INE/equipe inválido' in missing
    assert 'CRO-UF inválido' in missing


def test_update_treatment_sigtap_uses_loaded_catalog(monkeypatch):
    captured = {}
    sigtap = {
        'code': '0307030040',
        'competence': '202605',
        'name': 'PROFILAXIA / REMOÇÃO DA PLACA BACTERIANA',
    }

    monkeypatch.setattr(esus_export_service, 'get_sigtap_procedure', lambda code, competence=None: sigtap)
    monkeypatch.setattr(esus_export_service, 'procedure_locked_by_validated_batch', lambda procedure_id: None)

    def fake_execute(sql, params=()):
        captured['sql'] = sql
        captured['params'] = params

    monkeypatch.setattr(esus_export_service, 'execute', fake_execute)

    result = update_treatment_sigtap(88, '0307030040', '202605')

    assert result == sigtap
    assert 'UPDATE tratamento_procedimentos' in captured['sql']
    assert captured['params'] == ('0307030040', '202605', 'PROFILAXIA / REMOÇÃO DA PLACA BACTERIANA', 88)


def test_update_treatment_sigtap_blocks_validated_batch_record(monkeypatch):
    monkeypatch.setattr(esus_export_service, 'procedure_locked_by_validated_batch', lambda procedure_id: 5)

    try:
        update_treatment_sigtap(88, '0307030040', '202605')
    except ValueError as exc:
        assert 'lote e-SUS validado internamente #5' in str(exc)
    else:
        raise AssertionError('Expected validated batch lock error')


def test_register_esus_export_batch_stores_payload_snapshot(monkeypatch):
    payload = {
        'reference_month': '2026-05',
        'records': [{'local_procedure_id': 1}],
        'summary': {'total': 2, 'ready': 1, 'missing_sigtap': 1, 'incomplete': 0},
    }
    captured = {}

    monkeypatch.setattr(esus_export_service, 'build_esus_payload', lambda month_value=None: (payload, 'abc123'))

    def fake_execute(sql, params=()):
        captured['sql'] = sql
        captured['params'] = params
        return 42

    monkeypatch.setattr(esus_export_service, 'execute', fake_execute)

    batch_id, result_payload = register_esus_export_batch('2026-05', generated_by=7)

    assert batch_id == 42
    assert result_payload == payload
    assert 'payload_json' in captured['sql']
    assert captured['params'][0] == '2026-05'
    assert captured['params'][2] == 'abc123'
    assert '"local_procedure_id": 1' in captured['params'][3]
    assert captured['params'][7] == 0
    assert captured['params'][8] == 7


def test_get_esus_batch_detail_uses_stored_payload_and_pending_records(monkeypatch):
    payload = {
        'reference_month': '2026-05',
        'records': [{'local_procedure_id': 1}],
        'summary': {'total': 1, 'ready': 1, 'missing_sigtap': 0, 'incomplete': 0},
    }
    monkeypatch.setattr(
        esus_export_service,
        'get_esus_batch',
        lambda batch_id: {
            'id': batch_id,
            'reference_month': '2026-05',
            'payload_json': payload,
            'payload_hash': None,
            'status': 'draft',
        },
    )
    monkeypatch.setattr(
        esus_export_service,
        'build_esus_readiness',
        lambda month_value=None: {
            'missing_sigtap_records': [{'id': 2}],
            'incomplete_records': [{'id': 3}],
        },
    )
    monkeypatch.setattr(esus_export_service, 'list_esus_transmission_attempts', lambda batch_id: [{'id': 4}])
    monkeypatch.setattr(
        esus_export_service,
        'build_batch_transmission_readiness',
        lambda batch, payload, computed_hash=None: {'ready': False, 'blockers': ['bloqueio']},
    )

    detail = get_esus_batch_detail(9)

    assert detail['batch']['id'] == 9
    assert detail['records'] == payload['records']
    assert detail['pending_records'] == [{'id': 2}, {'id': 3}]
    assert detail['attempts'] == [{'id': 4}]
    assert detail['legacy_payload'] is False


def test_validate_esus_export_batch_marks_internal_validation(monkeypatch):
    payload = {
        'summary': {'total': 4, 'ready': 3, 'missing_sigtap': 1, 'incomplete': 0},
        'records': [{'local_procedure_id': 1}],
    }
    calls = []
    batches = [
        {'id': 12, 'status': 'draft', 'reference_month': '2026-05', 'payload_json': payload, 'payload_hash': 'hash-1'},
        {'id': 12, 'status': 'validated_internally', 'reference_month': '2026-05', 'payload_hash': 'hash-1'},
    ]

    monkeypatch.setattr(esus_export_service, 'get_esus_batch', lambda batch_id: batches.pop(0))
    monkeypatch.setattr(esus_export_service, 'execute', lambda sql, params=(): calls.append((sql, params)))

    validated = validate_esus_export_batch(12, validated_by=7, notes='Conferido')

    assert validated['status'] == 'validated_internally'
    assert 'validated_by' in calls[0][0]
    assert calls[0][1][0] == 'hash-1'
    assert calls[0][1][1:5] == (4, 3, 1, 0)
    assert calls[0][1][5] == 7
    assert calls[0][1][6] == 'Conferido'


def test_procedure_locked_by_validated_batch_detects_record(monkeypatch):
    monkeypatch.setattr(
        esus_export_service,
        'query',
        lambda *args, **kwargs: [{
            'id': 3,
            'payload_json': {'records': [{'local_procedure_id': 88}]},
        }],
    )

    assert procedure_locked_by_validated_batch(88) == 3
    assert procedure_locked_by_validated_batch(99) is None


def test_batch_transmission_readiness_requires_validated_payload_and_settings():
    result = build_batch_transmission_readiness(
        batch={'status': 'draft', 'payload_hash': 'hash'},
        payload={'records': []},
        computed_hash='different',
        settings={
            'environment': 'aguardando_prefeitura',
            'base_url': '',
            'credential_status': 'pending',
            'cnes': '',
            'ine': '',
            'active': False,
        },
    )

    assert result['ready'] is False
    assert 'lote ainda não validado internamente' in result['blockers']
    assert 'hash do payload divergente' in result['blockers']
    assert 'payload sem registros prontos' in result['blockers']
    assert 'URL PEC/e-SUS não informada' in result['blockers']


def test_batch_transmission_readiness_accepts_ready_configuration():
    result = build_batch_transmission_readiness(
        batch={'status': 'validated_internally', 'payload_hash': 'hash'},
        payload={'records': [{'local_procedure_id': 1}]},
        computed_hash='hash',
        settings={
            'environment': 'homologacao',
            'base_url': 'https://esus.local',
            'credential_status': 'received',
            'cnes': '1234567',
            'ine': '0000000000',
            'active': True,
        },
    )

    assert result['ready'] is True
    assert result['blockers'] == []
    assert result['endpoint_url'] == 'https://esus.local'


def test_simulate_esus_transmission_preflight_blocks_when_not_ready(monkeypatch):
    calls = []
    detail = {
        'batch': {'id': 7, 'status': 'validated_internally'},
        'transmission_readiness': {
            'ready': False,
            'blockers': ['URL PEC/e-SUS não informada'],
            'records_count': 10,
            'payload_hash': 'hash-7',
            'endpoint_url': '',
        },
    }

    monkeypatch.setattr(esus_export_service, 'get_esus_batch_detail', lambda batch_id: detail)
    monkeypatch.setattr(esus_export_service, 'register_esus_transmission_attempt', lambda **kwargs: calls.append(kwargs) or 99)
    monkeypatch.setattr(esus_export_service, 'execute', lambda sql, params=(): calls.append({'sql': sql, 'params': params}))

    result = simulate_esus_transmission_preflight(7, attempted_by=3)

    assert result['status'] == 'blocked'
    assert result['ready_to_send'] is False
    assert calls[0]['status'] == 'blocked'
    assert calls[0]['http_status'] == 428
    assert 'simulation_blocked' in calls[1]['sql']


def test_simulate_esus_transmission_preflight_marks_ready_to_send(monkeypatch):
    calls = []
    detail = {
        'batch': {'id': 8, 'status': 'validated_internally'},
        'transmission_readiness': {
            'ready': True,
            'blockers': [],
            'records_count': 12,
            'payload_hash': 'hash-8',
            'endpoint_url': 'https://esus.local',
        },
    }

    monkeypatch.setattr(esus_export_service, 'get_esus_batch_detail', lambda batch_id: detail)
    monkeypatch.setattr(esus_export_service, 'register_esus_transmission_attempt', lambda **kwargs: calls.append(kwargs) or 100)
    monkeypatch.setattr(esus_export_service, 'execute', lambda sql, params=(): calls.append({'sql': sql, 'params': params}))

    result = simulate_esus_transmission_preflight(8, attempted_by=3)

    assert result['status'] == 'success'
    assert result['ready_to_send'] is True
    assert calls[0]['status'] == 'success'
    assert calls[0]['http_status'] == 200
    assert "status = 'ready_to_send'" in calls[1]['sql']
    assert calls[1]['params'][0] == 'https://esus.local'


def test_build_esus_meeting_checklist_groups_prefecture_items():
    checklist = build_esus_meeting_checklist(
        settings={
            'environment': 'homologacao',
            'base_url': 'https://esus.local',
            'pec_version': '5.4.36',
            'ledi_version': '7.4.1',
            'credential_status': 'received',
            'cnes': '1234567',
            'ine': '0000000000',
            'active': True,
        },
        homologation={'ready': True, 'blocking_count': 0},
        batch_detail={
            'batch': {
                'status': 'ready_to_send',
                'payload_hash': 'hash-1',
                'response_status': 'simulation_success',
            },
            'transmission_readiness': {'ready': True, 'blockers': []},
        },
    )

    assert checklist['pending'] == []
    assert 'Dados da prefeitura' in checklist['groups']
    assert any(item['label'] == 'Endpoint PEC/e-SUS informado' for item in checklist['items'])


def test_esus_homologation_report_composes_batch_manual_and_pending(monkeypatch):
    dashboard = {
        'settings': {
            'environment': 'aguardando_prefeitura',
            'base_url': '',
            'pec_version': '',
            'ledi_version': '',
            'credential_status': 'pending',
            'cnes': '',
            'ine': '',
            'active': False,
        },
        'homologation': {'ready': False, 'blocking_count': 2, 'items': []},
        'readiness': {'total': 1, 'ready': 1},
        'patient_gaps': {'missing_cns_or_cpf': 0},
        'missing_professionals': [],
    }
    batch = {'id': 4, 'reference_month': '2026-06'}
    batch_detail = {
        'batch': {
            'id': 4,
            'status': 'validated_internally',
            'payload_hash': 'hash-4',
            'response_status': 'simulation_blocked',
        },
        'attempts': [{'id': 1}],
        'transmission_readiness': {
            'ready': False,
            'blockers': ['URL PEC/e-SUS não informada'],
        },
    }

    monkeypatch.setattr(esus_export_service, 'get_esus_dashboard', lambda month_value=None: dashboard)
    monkeypatch.setattr(esus_export_service, 'get_esus_batch', lambda batch_id: batch)
    monkeypatch.setattr(esus_export_service, 'get_esus_batch_detail', lambda batch_id: batch_detail)
    monkeypatch.setattr(esus_export_service, 'get_latest_esus_batch', lambda month_value=None: batch)
    monkeypatch.setattr(esus_export_service, 'get_sigtap_summary', lambda: {'latest': {'total': 10}})

    report = get_esus_homologation_report(month_value='2026-06', batch_id=4)

    assert report['month'] == '2026-06'
    assert report['batch_detail']['batch']['id'] == 4
    assert 'URL PEC/e-SUS não informada' in report['pending_items']
    assert len(report['manual_steps']) >= 8
    assert 'endpoint' in report['external_dependency_note']


def test_get_esus_dashboard_composes_operational_context(monkeypatch):
    monkeypatch.setattr(
        esus_export_service,
        'build_esus_readiness',
        lambda month_value=None: {'total': 1, 'ready': 1, 'missing_sigtap': 0, 'incomplete': 0},
    )
    monkeypatch.setattr(
        esus_export_service,
        'get_esus_settings',
        lambda: {
            'environment': 'homologacao',
            'base_url': 'https://esus.local',
            'pec_version': '5.4.36',
            'ledi_version': '7.4.1',
            'credential_status': 'received',
            'cnes': '1234567',
            'ine': '0000000000',
        },
    )
    monkeypatch.setattr(
        esus_export_service,
        'get_sigtap_summary',
        lambda: {'latest': {'total': 10, 'competence': '202605'}},
    )
    monkeypatch.setattr(esus_export_service, 'get_patient_identifier_gaps', lambda: {'total': 2, 'missing_cns_or_cpf': 0, 'invalid_cns_or_cpf': 0})
    monkeypatch.setattr(esus_export_service, 'list_professionals_missing_required_data', lambda limit=80: [])
    monkeypatch.setattr(esus_export_service, 'list_procedures_missing_sigtap', lambda limit=80: [])
    monkeypatch.setattr(esus_export_service, 'list_esus_batches', lambda limit=12: [{'id': 1}])

    dashboard = get_esus_dashboard('2026-05')

    assert dashboard['month'] == '2026-05'
    assert dashboard['readiness']['ready'] == 1
    assert dashboard['settings']['environment'] == 'homologacao'
    assert dashboard['homologation']['ready']
    assert dashboard['batches'][0]['id'] == 1


def test_homologation_status_reports_blockers():
    status = build_homologation_status(
        settings={
            'environment': 'aguardando_prefeitura',
            'base_url': '',
            'pec_version': '',
            'ledi_version': '',
            'credential_status': 'pending',
            'cnes': '',
            'ine': '',
        },
        readiness={'missing_sigtap': 1, 'incomplete': 2},
        sigtap_summary={'latest': {'total': 0}},
        patient_gaps={'missing_cns_or_cpf': 3},
        missing_professionals=[{'id': 1}],
    )

    assert status['ready'] is False
    assert status['blocking_count'] == len(status['items'])


def test_homologation_status_blocks_invalid_identifier_formats():
    status = build_homologation_status(
        settings={
            'environment': 'homologacao',
            'base_url': 'https://esus.local',
            'pec_version': '5.4.36',
            'ledi_version': '7.4.1',
            'credential_status': 'received',
            'cnes': '123',
            'ine': '000',
        },
        readiness={'missing_sigtap': 0, 'incomplete': 0},
        sigtap_summary={'latest': {'total': 1}},
        patient_gaps={'missing_cns_or_cpf': 0, 'invalid_cns_or_cpf': 2},
        missing_professionals=[],
    )

    labels = {item['label']: item for item in status['items']}
    assert labels['CNES configurado']['ok'] is False
    assert labels['INE/equipe configurado']['ok'] is False
    assert labels['Pacientes com CNS/CPF válido']['ok'] is False
