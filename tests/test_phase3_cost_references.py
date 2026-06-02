import datetime as dt
from decimal import Decimal

import services.cost_reference_service as cost_reference_service
from constants import Role, role_has_permission
from services.cost_reference_service import (
    import_cost_references_csv,
    parse_money,
    update_cost_reference,
)


def test_financial_cost_reference_permissions_are_restricted():
    assert role_has_permission(Role.ADMIN, 'financeiro:view')
    assert role_has_permission(Role.ADMIN, 'financeiro:write')
    assert role_has_permission(Role.FINANCEIRO, 'financeiro:view')
    assert role_has_permission(Role.FINANCEIRO, 'financeiro:write')
    assert role_has_permission(Role.BI, 'financeiro:view') is False
    assert role_has_permission(Role.AUDITORIA, 'financeiro:write') is False


def test_parse_money_accepts_brazilian_and_decimal_formats():
    assert parse_money('R$ 1.234,56') == Decimal('1234.56')
    assert parse_money('80.00') == Decimal('80.00')
    assert parse_money('1.234') == Decimal('1234.00')
    assert parse_money('') == Decimal('0.00')


def test_update_cost_reference_sets_validation_metadata(monkeypatch):
    old_row = {
        'id': 8,
        'sigtap_code': '0307030040',
        'sigtap_name': 'Profilaxia',
        'public_cost': Decimal('35.00'),
        'private_reference': Decimal('180.00'),
        'reference_label': 'Referência demo',
        'source': 'demo_reference_internal',
        'methodology_status': 'draft',
        'notes': 'demo',
        'active': True,
        'validated_by': None,
        'validated_at': None,
        'validation_notes': None,
    }
    new_row = {
        **old_row,
        'public_cost': Decimal('40.00'),
        'private_reference': Decimal('200.00'),
        'source': 'official_public_table',
        'methodology_status': 'validated',
        'validated_by': 7,
        'validated_at': dt.datetime(2026, 6, 2, 8, 30),
        'validation_notes': 'Tabela aprovada pela gestão.',
    }
    responses = [old_row, new_row]
    captured = {}

    def fake_query(sql, params=(), one=False):
        return responses.pop(0)

    def fake_execute(sql, params=()):
        captured['sql'] = sql
        captured['params'] = params

    monkeypatch.setattr(cost_reference_service, 'query', fake_query)
    monkeypatch.setattr(cost_reference_service, 'execute', fake_execute)

    result = update_cost_reference(
        8,
        {
            'sigtap_code': '0307030040',
            'sigtap_name': 'Profilaxia',
            'public_cost': '40,00',
            'private_reference': '200,00',
            'reference_label': 'Referência demo',
            'source': 'official_public_table',
            'methodology_status': 'validated',
            'notes': 'demo',
            'active': '1',
            'validation_notes': 'Tabela aprovada pela gestão.',
        },
        actor_id=7,
    )

    assert 'validated_at = NOW()' in captured['sql']
    assert captured['params'][8] == 7
    assert result['changed_fields']['methodology_status']['new'] == 'validated'
    assert result['changed_fields']['public_cost']['new'] == Decimal('40.00')


def test_import_cost_references_csv_rejects_invalid_file_before_writing(monkeypatch):
    called = {'execute': False}

    def fake_execute(sql, params=()):
        called['execute'] = True

    monkeypatch.setattr(cost_reference_service, 'execute', fake_execute)

    result = import_cost_references_csv(
        'codigo;valor_publico;referencia_privada\n123;10,00;20,00\n',
        actor_id=7,
    )

    assert result['imported'] == 0
    assert result['errors']
    assert called['execute'] is False


def test_import_cost_references_csv_upserts_valid_rows(monkeypatch):
    old_row = {
        'id': 9,
        'sigtap_code': '0307030040',
        'sigtap_name': 'Profilaxia',
        'public_cost': Decimal('35.00'),
        'private_reference': Decimal('180.00'),
        'reference_label': 'Referência demo',
        'source': 'demo_reference_internal',
        'methodology_status': 'draft',
        'notes': '',
        'active': True,
        'validated_by': None,
        'validated_at': None,
        'validation_notes': None,
    }
    new_row = {
        **old_row,
        'public_cost': Decimal('45.50'),
        'private_reference': Decimal('250.00'),
        'source': 'csv_import',
        'methodology_status': 'pending_public_validation',
        'notes': 'Planilha SSA',
    }
    responses = [old_row, new_row]
    captured = {}

    def fake_query(sql, params=(), one=False):
        return responses.pop(0)

    def fake_execute(sql, params=()):
        captured['sql'] = sql
        captured['params'] = params
        return 9

    monkeypatch.setattr(cost_reference_service, 'query', fake_query)
    monkeypatch.setattr(cost_reference_service, 'execute', fake_execute)

    result = import_cost_references_csv(
        (
            'codigo_sigtap;nome_sigtap;valor_publico;referencia_privada;'
            'status_metodologia;fonte;ativo;observacoes\n'
            '0307030040;Profilaxia;45,50;250,00;aguardando homologacao;csv;sim;Planilha SSA\n'
        ),
        actor_id=7,
    )

    assert result['imported'] == 1
    assert result['updated'] == 1
    assert result['changes'][0]['changed_fields']['private_reference']['new'] == Decimal('250.00')
    assert captured['params'][0] == '0307030040'
    assert captured['params'][2] == Decimal('45.50')
    assert captured['params'][6] == 'pending_public_validation'
