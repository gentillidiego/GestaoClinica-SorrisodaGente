import csv
import io
import re
from decimal import Decimal, InvalidOperation

from database import execute, query
from services.sigtap_service import normalize_sigtap_code


METHODOLOGY_STATUS_OPTIONS = [
    ('draft', 'Rascunho / demonstrativo'),
    ('pending_public_validation', 'Aguardando homologação pública'),
    ('validated', 'Validada pela gestão pública'),
]

SOURCE_OPTIONS = [
    ('demo_reference_internal', 'Referência demonstrativa interna'),
    ('manual', 'Cadastro manual'),
    ('csv_import', 'Importação CSV'),
    ('official_public_table', 'Tabela oficial homologada'),
    ('pending_seed', 'Placeholder automático — sem custo cadastrado'),
]

STATUS_ALIASES = {
    'draft': 'draft',
    'rascunho': 'draft',
    'demonstrativo': 'draft',
    'demo': 'draft',
    'pending_public_validation': 'pending_public_validation',
    'pendente': 'pending_public_validation',
    'aguardando': 'pending_public_validation',
    'aguardando homologacao': 'pending_public_validation',
    'aguardando homologação': 'pending_public_validation',
    'aguardando_homologacao': 'pending_public_validation',
    'aguardando_homologação': 'pending_public_validation',
    'validated': 'validated',
    'validado': 'validated',
    'validada': 'validated',
    'homologado': 'validated',
    'homologada': 'validated',
}

SOURCE_ALIASES = {
    'demo_reference_internal': 'demo_reference_internal',
    'demo': 'demo_reference_internal',
    'manual': 'manual',
    'csv': 'csv_import',
    'csv_import': 'csv_import',
    'importacao_csv': 'csv_import',
    'importação_csv': 'csv_import',
    'official_public_table': 'official_public_table',
    'oficial': 'official_public_table',
    'tabela_oficial': 'official_public_table',
    'pending_seed': 'pending_seed',
    'placeholder': 'pending_seed',
}

CSV_ALIASES = {
    'sigtap_code': ('sigtap_code', 'codigo', 'codigo_sigtap', 'codigo_sus', 'procedimento_codigo'),
    'sigtap_name': ('sigtap_name', 'nome', 'nome_sigtap', 'procedimento', 'descricao'),
    'public_cost': ('public_cost', 'custo_publico', 'valor_publico', 'custo_sus', 'valor_sus'),
    'private_reference': ('private_reference', 'referencia_privada', 'valor_privado', 'custo_privado', 'referencia'),
    'reference_label': ('reference_label', 'rotulo_referencia', 'referencia_label', 'fonte_rotulo'),
    'source': ('source', 'fonte', 'origem'),
    'methodology_status': ('methodology_status', 'status_metodologia', 'status', 'homologacao'),
    'notes': ('notes', 'observacoes', 'observação', 'observacao', 'notas'),
    'active': ('active', 'ativo', 'status_ativo'),
    'validation_notes': ('validation_notes', 'notas_validacao', 'observacao_validacao'),
}


def seed_missing_cost_reference_placeholders():
    """Garante que todo código do catálogo SIGTAP apareça na tela de Custos.

    Não inventa valor de custo: cria a linha com R$ 0,00 e
    methodology_status='draft'/source='pending_seed', deixando explícito que
    falta cadastrar o custo real. Nunca sobrescreve linhas já existentes.
    """
    from services.sigtap_service import SIGTAP_PROCEDURE_INDEX

    for code, item in SIGTAP_PROCEDURE_INDEX.items():
        execute(
            """
            INSERT INTO procedure_cost_references (
                sigtap_code, sigtap_name, public_cost, private_reference,
                reference_label, source, methodology_status, notes, active
            )
            VALUES (%s, %s, 0, 0, %s, 'pending_seed', 'draft', %s, TRUE)
            ON CONFLICT (sigtap_code) DO NOTHING
            """,
            (
                code,
                item['name'],
                'Sem referência cadastrada',
                'Placeholder gerado automaticamente — custo público e referência privada ainda não informados.',
            ),
        )


def get_methodology_status_options():
    return METHODOLOGY_STATUS_OPTIONS


def get_source_options():
    return SOURCE_OPTIONS


def normalize_methodology_status(value):
    normalized = _slug(value)
    return STATUS_ALIASES.get(normalized, 'draft')


def normalize_source(value, default='manual'):
    normalized = _slug(value)
    return SOURCE_ALIASES.get(normalized, default)


def parse_money(value, field_label='valor'):
    if value is None:
        return Decimal('0.00')

    raw = str(value).strip()
    if not raw:
        return Decimal('0.00')

    cleaned = re.sub(r'[^\d,.\-]', '', raw)
    if cleaned in {'', '-', '.', ',', '-.', '-,'}:
        raise ValueError(f'{field_label} inválido.')

    if ',' in cleaned and '.' in cleaned:
        if cleaned.rfind(',') > cleaned.rfind('.'):
            normalized = cleaned.replace('.', '').replace(',', '.')
        else:
            normalized = cleaned.replace(',', '')
    elif ',' in cleaned:
        normalized = cleaned.replace('.', '').replace(',', '.')
    elif '.' in cleaned:
        parts = cleaned.split('.')
        if len(parts) > 2 or (len(parts[-1]) == 3 and all(len(part) == 3 for part in parts[1:])):
            normalized = ''.join(parts)
        else:
            normalized = cleaned
    else:
        normalized = cleaned

    try:
        amount = Decimal(normalized).quantize(Decimal('0.01'))
    except InvalidOperation as exc:
        raise ValueError(f'{field_label} inválido.') from exc

    if amount < 0:
        raise ValueError(f'{field_label} não pode ser negativo.')
    return amount


def list_cost_references(filters=None, limit=120):
    filters = normalize_filters(filters)
    clauses = []
    params = []

    if filters['q']:
        normalized_code = normalize_sigtap_code(filters['q'])
        if normalized_code:
            clauses.append('cr.sigtap_code = %s')
            params.append(normalized_code)
        else:
            clauses.append('(cr.sigtap_name ILIKE %s OR cr.sigtap_code ILIKE %s)')
            params.extend([f"%{filters['q']}%", f"%{filters['q']}%"])

    if filters['methodology_status']:
        clauses.append('cr.methodology_status = %s')
        params.append(filters['methodology_status'])

    if filters['source']:
        clauses.append('cr.source = %s')
        params.append(filters['source'])

    if filters['active'] == 'active':
        clauses.append('cr.active = TRUE')
    elif filters['active'] == 'inactive':
        clauses.append('cr.active = FALSE')

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ''
    params.append(limit)

    return query(
        f"""
        SELECT cr.*,
               u.full_name as validated_by_name,
               u.username as validated_by_username,
               GREATEST(COALESCE(cr.private_reference, 0) - COALESCE(cr.public_cost, 0), 0) as unit_savings
        FROM procedure_cost_references cr
        LEFT JOIN users u ON u.id = cr.validated_by
        {where_sql}
        ORDER BY cr.active DESC, cr.methodology_status ASC, cr.sigtap_code ASC
        LIMIT %s
        """,
        tuple(params),
    )


def get_cost_reference_stats():
    row = query(
        """
        SELECT COUNT(*) as total,
               COUNT(*) FILTER (WHERE active = TRUE) as active,
               COUNT(*) FILTER (WHERE active = FALSE) as inactive,
               COUNT(*) FILTER (WHERE methodology_status = 'validated') as validated,
               COUNT(*) FILTER (WHERE methodology_status <> 'validated' OR methodology_status IS NULL) as pending_validation,
               COUNT(*) FILTER (WHERE source = 'demo_reference_internal') as demo_references,
               COUNT(*) FILTER (WHERE active = TRUE AND private_reference > 0 AND public_cost >= 0) as priced
        FROM procedure_cost_references
        """,
        one=True,
    ) or {}
    total = _as_int(row.get('total'))
    validated = _as_int(row.get('validated'))
    return {
        'total': total,
        'active': _as_int(row.get('active')),
        'inactive': _as_int(row.get('inactive')),
        'validated': validated,
        'pending_validation': _as_int(row.get('pending_validation')),
        'demo_references': _as_int(row.get('demo_references')),
        'priced': _as_int(row.get('priced')),
        'validation_rate': round((validated / total) * 100, 1) if total else 0,
    }


def get_cost_reference_dashboard(filters=None):
    filters = normalize_filters(filters)
    return {
        'filters': filters,
        'stats': get_cost_reference_stats(),
        'references': list_cost_references(filters),
        'methodology_status_options': get_methodology_status_options(),
        'source_options': get_source_options(),
    }


def get_cost_reference(reference_id):
    return query(
        """
        SELECT *
        FROM procedure_cost_references
        WHERE id = %s
        """,
        (reference_id,),
        one=True,
    )


def update_cost_reference(reference_id, data, actor_id=None):
    current = get_cost_reference(reference_id)
    if not current:
        raise ValueError('Referência de custo não encontrada.')

    prepared = prepare_cost_reference_payload(data, actor_id=actor_id, default_source='manual')
    _update_cost_reference_record(reference_id, prepared)
    updated = get_cost_reference(reference_id)

    return _build_change_result(current, updated, created=False)


def import_cost_references_csv(content, actor_id=None):
    prepared_rows, errors = parse_cost_reference_csv(content, actor_id=actor_id)
    if errors:
        return {
            'imported': 0,
            'created': 0,
            'updated': 0,
            'errors': errors,
            'changes': [],
        }

    changes = []
    created_count = 0
    updated_count = 0
    for item in prepared_rows:
        result = upsert_cost_reference(item, actor_id=actor_id, default_source='csv_import')
        changes.append(result)
        if result['created']:
            created_count += 1
        else:
            updated_count += 1

    return {
        'imported': len(prepared_rows),
        'created': created_count,
        'updated': updated_count,
        'errors': [],
        'changes': changes,
    }


def parse_cost_reference_csv(content, actor_id=None):
    text = (content or '').lstrip('\ufeff')
    if not text.strip():
        return [], ['Arquivo CSV vazio.']

    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=',;')
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ';'

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        return [], ['Cabeçalho CSV não identificado.']

    prepared = []
    errors = []
    seen_codes = set()
    for line_number, row in enumerate(reader, start=2):
        if not any((value or '').strip() for value in row.values()):
            continue

        normalized_row = _normalize_csv_row(row)
        raw_code = _pick_csv_value(normalized_row, CSV_ALIASES['sigtap_code'])
        code = normalize_sigtap_code(raw_code)
        if not code:
            errors.append(f'Linha {line_number}: código SIGTAP inválido ou ausente.')
            continue
        if code in seen_codes:
            errors.append(f'Linha {line_number}: código SIGTAP duplicado no arquivo ({code}).')
            continue
        seen_codes.add(code)

        try:
            public_cost = parse_money(
                _pick_csv_value(normalized_row, CSV_ALIASES['public_cost']),
                field_label=f'Linha {line_number}: custo público',
            )
            private_reference = parse_money(
                _pick_csv_value(normalized_row, CSV_ALIASES['private_reference']),
                field_label=f'Linha {line_number}: referência privada',
            )
        except ValueError as exc:
            errors.append(str(exc))
            continue

        prepared.append({
            'sigtap_code': code,
            'sigtap_name': _clean_text(_pick_csv_value(normalized_row, CSV_ALIASES['sigtap_name'])),
            'public_cost': public_cost,
            'private_reference': private_reference,
            'reference_label': _clean_text(_pick_csv_value(normalized_row, CSV_ALIASES['reference_label']))
            or 'Referência operacional importada',
            'source': normalize_source(_pick_csv_value(normalized_row, CSV_ALIASES['source']), default='csv_import'),
            'methodology_status': normalize_methodology_status(
                _pick_csv_value(normalized_row, CSV_ALIASES['methodology_status'])
            ),
            'notes': _clean_text(_pick_csv_value(normalized_row, CSV_ALIASES['notes'])),
            'active': _parse_bool(_pick_csv_value(normalized_row, CSV_ALIASES['active']), default=True),
            'validation_notes': _clean_text(_pick_csv_value(normalized_row, CSV_ALIASES['validation_notes'])),
            'actor_id': actor_id,
        })

    if not prepared and not errors:
        errors.append('Nenhuma linha válida encontrada no CSV.')
    return prepared, errors


def upsert_cost_reference(data, actor_id=None, default_source='manual'):
    prepared = prepare_cost_reference_payload(data, actor_id=actor_id, default_source=default_source)
    code = prepared['sigtap_code']
    current = query(
        """
        SELECT *
        FROM procedure_cost_references
        WHERE sigtap_code = %s
        """,
        (code,),
        one=True,
    )

    reference_id = execute(
        """
        INSERT INTO procedure_cost_references (
            sigtap_code, sigtap_name, public_cost, private_reference,
            reference_label, source, methodology_status, notes, active,
            validated_by, validated_at, validation_notes, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CASE WHEN %s THEN NOW() ELSE NULL END, %s, NOW())
        ON CONFLICT (sigtap_code)
        DO UPDATE SET
            sigtap_name = COALESCE(NULLIF(EXCLUDED.sigtap_name, ''), procedure_cost_references.sigtap_name),
            public_cost = EXCLUDED.public_cost,
            private_reference = EXCLUDED.private_reference,
            reference_label = EXCLUDED.reference_label,
            source = EXCLUDED.source,
            methodology_status = EXCLUDED.methodology_status,
            notes = EXCLUDED.notes,
            active = EXCLUDED.active,
            validated_by = EXCLUDED.validated_by,
            validated_at = EXCLUDED.validated_at,
            validation_notes = EXCLUDED.validation_notes,
            updated_at = NOW()
        RETURNING id
        """,
        _payload_params(prepared),
    )
    updated = get_cost_reference(reference_id)
    return _build_change_result(current, updated, created=current is None)


def prepare_cost_reference_payload(data, actor_id=None, default_source='manual'):
    status = normalize_methodology_status(data.get('methodology_status'))
    sigtap_code = normalize_sigtap_code(data.get('sigtap_code'))
    if not sigtap_code:
        raise ValueError('Código SIGTAP inválido. Informe 10 dígitos.')

    active = _parse_bool(data.get('active'), default=False)
    validation_notes = _clean_text(data.get('validation_notes'))
    validated_by = actor_id if status == 'validated' else None
    validated_at_sql = 'NOW()' if status == 'validated' else None

    return {
        'sigtap_code': sigtap_code,
        'sigtap_name': _clean_text(data.get('sigtap_name')),
        'public_cost': parse_money(data.get('public_cost'), field_label='Custo público'),
        'private_reference': parse_money(data.get('private_reference'), field_label='Referência privada'),
        'reference_label': _clean_text(data.get('reference_label')) or 'Referência operacional interna',
        'source': normalize_source(data.get('source'), default=default_source),
        'methodology_status': status,
        'notes': _clean_text(data.get('notes')),
        'active': active,
        'validated_by': validated_by,
        'validated_at_sql': validated_at_sql,
        'validation_notes': validation_notes,
    }


def normalize_filters(filters=None):
    filters = filters or {}
    methodology_status = filters.get('methodology_status') or ''
    source = filters.get('source') or ''
    active = filters.get('active') or 'active'

    valid_statuses = {value for value, _ in METHODOLOGY_STATUS_OPTIONS}
    valid_sources = {value for value, _ in SOURCE_OPTIONS}
    if methodology_status not in valid_statuses:
        methodology_status = ''
    if source not in valid_sources:
        source = ''
    if active not in {'active', 'inactive', 'all'}:
        active = 'active'

    return {
        'q': _clean_text(filters.get('q')),
        'methodology_status': methodology_status,
        'source': source,
        'active': active,
    }


def _update_cost_reference_record(reference_id, prepared):
    validated_at_sql = prepared.pop('validated_at_sql')
    validated_at_fragment = 'NOW()' if validated_at_sql else 'NULL'
    execute(
        f"""
        UPDATE procedure_cost_references
        SET sigtap_name = %s,
            public_cost = %s,
            private_reference = %s,
            reference_label = %s,
            source = %s,
            methodology_status = %s,
            notes = %s,
            active = %s,
            validated_by = %s,
            validated_at = {validated_at_fragment},
            validation_notes = %s,
            updated_at = NOW()
        WHERE id = %s
        """,
        (
            prepared['sigtap_name'],
            prepared['public_cost'],
            prepared['private_reference'],
            prepared['reference_label'],
            prepared['source'],
            prepared['methodology_status'],
            prepared['notes'],
            prepared['active'],
            prepared['validated_by'],
            prepared['validation_notes'],
            reference_id,
        ),
    )


def _payload_params(prepared):
    return (
        prepared['sigtap_code'],
        prepared['sigtap_name'],
        prepared['public_cost'],
        prepared['private_reference'],
        prepared['reference_label'],
        prepared['source'],
        prepared['methodology_status'],
        prepared['notes'],
        prepared['active'],
        prepared['validated_by'],
        prepared.get('methodology_status') == 'validated',
        prepared['validation_notes'],
    )


def _build_change_result(old_row, new_row, created=False):
    old_snapshot = _snapshot(old_row) if old_row else None
    new_snapshot = _snapshot(new_row)
    changes = {}
    if old_snapshot:
        for key, new_value in new_snapshot.items():
            old_value = old_snapshot.get(key)
            if _compare_value(old_value) != _compare_value(new_value):
                changes[key] = {
                    'old': old_value,
                    'new': new_value,
                }
    else:
        changes = {key: {'old': None, 'new': value} for key, value in new_snapshot.items()}

    return {
        'reference': new_row,
        'old': old_snapshot,
        'new': new_snapshot,
        'created': created,
        'changed_fields': changes,
    }


def _snapshot(row):
    if not row:
        return {}
    keys = (
        'sigtap_code',
        'sigtap_name',
        'public_cost',
        'private_reference',
        'reference_label',
        'source',
        'methodology_status',
        'notes',
        'active',
        'validated_by',
        'validated_at',
        'validation_notes',
    )
    return {key: row.get(key) for key in keys}


def _compare_value(value):
    if isinstance(value, Decimal):
        return str(value.quantize(Decimal('0.01')))
    return '' if value is None else str(value)


def _parse_bool(value, default=False):
    if value is None or value == '':
        return default
    if isinstance(value, bool):
        return value
    normalized = _slug(value)
    return normalized in {'1', 'true', 'sim', 's', 'yes', 'y', 'ativo', 'active'}


def _clean_text(value):
    return (str(value).strip() if value is not None else '')


def _slug(value):
    text = _clean_text(value).lower()
    text = text.replace('-', '_').replace(' ', '_')
    text = text.replace('ã', 'a').replace('á', 'a').replace('à', 'a').replace('â', 'a')
    text = text.replace('é', 'e').replace('ê', 'e')
    text = text.replace('í', 'i')
    text = text.replace('ó', 'o').replace('ô', 'o').replace('õ', 'o')
    text = text.replace('ú', 'u').replace('ç', 'c')
    return text


def _normalize_csv_row(row):
    return {
        _slug(key): value
        for key, value in row.items()
        if key is not None
    }


def _pick_csv_value(row, aliases):
    for alias in aliases:
        value = row.get(_slug(alias))
        if value not in (None, ''):
            return value
    return ''


def _as_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
