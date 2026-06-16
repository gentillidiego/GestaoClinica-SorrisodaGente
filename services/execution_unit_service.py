import re
import unicodedata

from constants import DEFAULT_EXECUTION_UNIT, EXECUTION_UNITS
from database import execute, execute_returning, query


MAX_ACTIVE_EXECUTION_UNITS = 2


class ExecutionUnitError(ValueError):
    pass


def _clean(value):
    return str(value or '').strip()


def _as_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {'1', 'true', 'sim', 'yes', 'on'}


def _slugify(value):
    normalized = unicodedata.normalize('NFKD', _clean(value))
    ascii_value = normalized.encode('ascii', 'ignore').decode('ascii').lower()
    code = re.sub(r'[^a-z0-9]+', '_', ascii_value).strip('_')
    return code[:40] or ''


def _fallback_units(include_inactive=False):
    return [
        {
            'id': index + 1,
            'code': code,
            'name': label,
            'cnes': None,
            'address': None,
            'notes': None,
            'active': True,
            'is_default': code == DEFAULT_EXECUTION_UNIT,
            'consultas_count': 0,
        }
        for index, (code, label) in enumerate(EXECUTION_UNITS)
    ]


def list_execution_units(include_inactive=False, with_usage=False):
    try:
        where = '' if include_inactive else 'WHERE eu.active = TRUE'
        usage_select = ''
        usage_joins = ''
        if with_usage:
            usage_select = """,
                   COALESCE(c.consultas_count, 0) as consultas_count
            """
            usage_joins = """
            LEFT JOIN (
                SELECT execution_unit, COUNT(*) as consultas_count
                FROM consultas
                GROUP BY execution_unit
            ) c ON c.execution_unit = eu.code
            """

        return query(
            f"""
            SELECT eu.*
                   {usage_select}
            FROM execution_units eu
            {usage_joins}
            {where}
            ORDER BY eu.is_default DESC, eu.active DESC, eu.name ASC
            """
        ) or []
    except Exception:
        return _fallback_units(include_inactive=include_inactive)


def get_execution_unit_choices(include_inactive=False):
    return [
        (unit['code'], unit['name'])
        for unit in list_execution_units(include_inactive=include_inactive)
    ]


def get_execution_unit_label(code):
    normalized = code or DEFAULT_EXECUTION_UNIT
    for unit in list_execution_units(include_inactive=True):
        if unit['code'] == normalized:
            return unit['name']
    return dict(EXECUTION_UNITS).get(normalized, dict(EXECUTION_UNITS)[DEFAULT_EXECUTION_UNIT])


def normalize_execution_unit(code, include_inactive=False):
    normalized = _clean(code)
    if not normalized:
        return None
    valid_codes = {
        unit['code']
        for unit in list_execution_units(include_inactive=include_inactive)
    }
    return normalized if normalized in valid_codes else None


def get_default_execution_unit():
    for unit in list_execution_units():
        if unit.get('is_default'):
            return unit['code']
    return DEFAULT_EXECUTION_UNIT


def get_execution_unit(unit_id):
    return query(
        """
        SELECT *
        FROM execution_units
        WHERE id = %s
        """,
        (unit_id,),
        one=True,
    )


def _active_count(exclude_id=None):
    params = []
    where = ["active = TRUE"]
    if exclude_id:
        where.append("id != %s")
        params.append(exclude_id)
    row = query(
        f"SELECT COUNT(*) as count FROM execution_units WHERE {' AND '.join(where)}",
        tuple(params),
        one=True,
    ) or {}
    return int(row.get('count') or 0)


def _usage_count(code):
    consultas = query(
        "SELECT COUNT(*) as count FROM consultas WHERE execution_unit = %s",
        (code,),
        one=True,
    ) or {}
    return int(consultas.get('count') or 0)


def _validate_active_limit(active, exclude_id=None):
    if active and _active_count(exclude_id=exclude_id) >= MAX_ACTIVE_EXECUTION_UNITS:
        raise ExecutionUnitError('O sistema está configurado para no máximo 2 unidades ativas.')


def create_execution_unit(payload):
    name = _clean(payload.get('name'))
    if not name:
        raise ExecutionUnitError('Nome da unidade é obrigatório.')

    code = _slugify(payload.get('code') or name)
    if not code:
        raise ExecutionUnitError('Código da unidade é obrigatório.')

    active = _as_bool(payload.get('active'), default=True)
    is_default = _as_bool(payload.get('is_default'))
    if is_default and not active:
        raise ExecutionUnitError('A unidade padrão precisa estar ativa.')
    _validate_active_limit(active)

    existing = query(
        "SELECT id FROM execution_units WHERE code = %s",
        (code,),
        one=True,
    )
    if existing:
        raise ExecutionUnitError('Já existe uma unidade com este código.')

    unit_id = execute_returning(
        """
        INSERT INTO execution_units (
            code, name, cnes, address, notes, active, is_default
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            code,
            name,
            _clean(payload.get('cnes')) or None,
            _clean(payload.get('address')) or None,
            _clean(payload.get('notes')) or None,
            active,
            is_default,
        ),
    )
    if is_default:
        set_default_execution_unit(unit_id)
    return get_execution_unit(unit_id)


def update_execution_unit(unit_id, payload):
    unit = get_execution_unit(unit_id)
    if not unit:
        raise ExecutionUnitError('Unidade não encontrada.')

    name = _clean(payload.get('name'))
    if not name:
        raise ExecutionUnitError('Nome da unidade é obrigatório.')

    active = _as_bool(payload.get('active'))
    set_as_default = _as_bool(payload.get('is_default'))
    if set_as_default and not active:
        raise ExecutionUnitError('A unidade padrão precisa estar ativa.')

    if not active:
        if unit.get('is_default'):
            raise ExecutionUnitError('A unidade padrão não pode ser desativada.')
        if _usage_count(unit['code']) > 0:
            raise ExecutionUnitError('Unidade com agenda vinculada não pode ser desativada.')
    elif not unit.get('active'):
        _validate_active_limit(active=True, exclude_id=unit_id)

    execute(
        """
        UPDATE execution_units
        SET name = %s,
            cnes = %s,
            address = %s,
            notes = %s,
            active = %s,
            updated_at = NOW()
        WHERE id = %s
        """,
        (
            name,
            _clean(payload.get('cnes')) or None,
            _clean(payload.get('address')) or None,
            _clean(payload.get('notes')) or None,
            active,
            unit_id,
        ),
    )
    if set_as_default:
        set_default_execution_unit(unit_id)
    return get_execution_unit(unit_id)


def set_default_execution_unit(unit_id):
    unit = get_execution_unit(unit_id)
    if not unit:
        raise ExecutionUnitError('Unidade não encontrada.')
    if not unit.get('active'):
        raise ExecutionUnitError('A unidade padrão precisa estar ativa.')

    execute("UPDATE execution_units SET is_default = FALSE")
    execute(
        "UPDATE execution_units SET is_default = TRUE, updated_at = NOW() WHERE id = %s",
        (unit_id,),
    )
    return get_execution_unit(unit_id)
