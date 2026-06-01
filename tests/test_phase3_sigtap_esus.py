import datetime as dt

import services.esus_export_service as esus_export_service
import services.sigtap_service as sigtap_service
from services.esus_export_service import build_esus_payload, month_period
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

    payload, payload_hash = build_esus_payload('2026-05')

    assert len(payload['records']) == 1
    assert payload['records'][0]['procedure']['sigtap_code'] == '0307030040'
    assert payload['summary']['total'] == 2
    assert payload['summary']['ready'] == 1
    assert payload['summary']['missing_sigtap'] == 1
    assert len(payload_hash) == 64
