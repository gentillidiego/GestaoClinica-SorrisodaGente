import pytest

import services.execution_unit_service as execution_unit_service
from services.execution_unit_service import (
    ExecutionUnitError,
    create_execution_unit,
    get_execution_unit_choices,
    get_default_execution_unit,
    normalize_execution_unit,
    update_execution_unit,
)


class FakeExecutionUnitStore:
    def __init__(self, units=None, consultas=None):
        self.units = [dict(unit) for unit in units or []]
        self.consultas = consultas or {}
        self.next_id = max([unit['id'] for unit in self.units] or [0]) + 1

    def query(self, sql, params=(), one=False):
        if 'FROM execution_units eu' in sql:
            rows = [dict(unit) for unit in self.units]
            if 'WHERE eu.active = TRUE' in sql:
                rows = [unit for unit in rows if unit.get('active')]
            for unit in rows:
                unit['consultas_count'] = self.consultas.get(unit['code'], 0)
            rows.sort(key=lambda unit: (
                not unit.get('is_default'),
                not unit.get('active'),
                unit['name'],
            ))
            return rows[0] if one and rows else rows

        if 'FROM execution_units' in sql and 'WHERE id = %s' in sql:
            row = next((unit for unit in self.units if unit['id'] == params[0]), None)
            return dict(row) if row else None

        if 'FROM execution_units' in sql and 'WHERE code = %s' in sql:
            row = next((unit for unit in self.units if unit['code'] == params[0]), None)
            return {'id': row['id']} if row else None

        if 'COUNT(*) as count FROM execution_units' in sql:
            exclude_id = params[0] if params else None
            return {
                'count': sum(
                    1
                    for unit in self.units
                    if unit.get('active') and unit['id'] != exclude_id
                )
            }

        if 'FROM consultas WHERE execution_unit = %s' in sql:
            return {'count': self.consultas.get(params[0], 0)}

        return None if one else []

    def execute_returning(self, sql, params=()):
        code, name, cnes, address, notes, active, is_default = params
        if any(unit['code'] == code for unit in self.units):
            raise AssertionError('duplicate code should be validated before insert')
        unit_id = self.next_id
        self.next_id += 1
        self.units.append({
            'id': unit_id,
            'code': code,
            'name': name,
            'cnes': cnes,
            'address': address,
            'notes': notes,
            'active': active,
            'is_default': is_default,
        })
        return unit_id

    def execute(self, sql, params=()):
        if 'UPDATE execution_units SET is_default = FALSE' in sql:
            for unit in self.units:
                unit['is_default'] = False
            return None

        if 'UPDATE execution_units SET is_default = TRUE' in sql:
            unit_id = params[0]
            for unit in self.units:
                if unit['id'] == unit_id:
                    unit['is_default'] = True
            return None

        if 'SET name = %s' in sql:
            name, cnes, address, notes, active, unit_id = params
            for unit in self.units:
                if unit['id'] == unit_id:
                    unit.update({
                        'name': name,
                        'cnes': cnes,
                        'address': address,
                        'notes': notes,
                        'active': active,
                    })
            return None

        return None


@pytest.fixture
def fake_units(monkeypatch):
    store = FakeExecutionUnitStore([
        {
            'id': 1,
            'code': 'unidade_principal',
            'name': 'Unidade Principal',
            'cnes': None,
            'address': None,
            'notes': None,
            'active': True,
            'is_default': True,
        },
        {
            'id': 2,
            'code': 'unidade_apoio',
            'name': 'Unidade de Apoio',
            'cnes': None,
            'address': None,
            'notes': None,
            'active': False,
            'is_default': False,
        },
    ])
    monkeypatch.setattr(execution_unit_service, 'query', store.query)
    monkeypatch.setattr(execution_unit_service, 'execute', store.execute)
    monkeypatch.setattr(execution_unit_service, 'execute_returning', store.execute_returning)
    return store


def test_execution_unit_choices_only_show_active_units_by_default(fake_units):
    assert get_execution_unit_choices() == [('unidade_principal', 'Unidade Principal')]
    assert get_execution_unit_choices(include_inactive=True) == [
        ('unidade_principal', 'Unidade Principal'),
        ('unidade_apoio', 'Unidade de Apoio'),
    ]
    assert normalize_execution_unit('unidade_apoio') is None
    assert normalize_execution_unit('unidade_apoio', include_inactive=True) == 'unidade_apoio'
    assert get_default_execution_unit() == 'unidade_principal'


def test_create_execution_unit_enforces_max_two_active_units(fake_units):
    create_execution_unit({'name': 'Unidade Norte', 'active': True})

    with pytest.raises(ExecutionUnitError, match='máximo 2 unidades ativas'):
        create_execution_unit({'name': 'Unidade Sul', 'active': True})

    inactive = create_execution_unit({'name': 'Unidade Sul', 'active': False})
    assert inactive['code'] == 'unidade_sul'
    assert inactive['active'] is False


def test_create_execution_unit_requires_default_to_be_active(fake_units):
    before_count = len(fake_units.units)

    with pytest.raises(ExecutionUnitError, match='padrão precisa estar ativa'):
        create_execution_unit({
            'name': 'Unidade Temporária',
            'active': False,
            'is_default': True,
        })

    assert len(fake_units.units) == before_count


def test_create_execution_unit_rejects_duplicate_code(fake_units):
    with pytest.raises(ExecutionUnitError, match='Já existe uma unidade'):
        create_execution_unit({
            'name': 'Outro nome',
            'code': 'unidade_principal',
            'active': False,
        })


def test_update_execution_unit_blocks_default_and_used_unit_deactivation(fake_units):
    with pytest.raises(ExecutionUnitError, match='padrão não pode ser desativada'):
        update_execution_unit(1, {'name': 'Unidade Principal', 'active': False})

    with pytest.raises(ExecutionUnitError, match='padrão precisa estar ativa'):
        update_execution_unit(2, {
            'name': 'Unidade de Apoio',
            'active': False,
            'is_default': True,
        })

    fake_units.consultas['unidade_apoio'] = 2
    fake_units.units[1]['active'] = True

    with pytest.raises(ExecutionUnitError, match='Unidade com agenda'):
        update_execution_unit(2, {'name': 'Unidade de Apoio', 'active': False})


def test_update_execution_unit_can_set_new_default(fake_units):
    fake_units.units[1]['active'] = True

    updated = update_execution_unit(2, {
        'name': 'Unidade de Apoio',
        'active': True,
        'is_default': True,
    })

    assert updated['is_default'] is True
    assert fake_units.units[0]['is_default'] is False
