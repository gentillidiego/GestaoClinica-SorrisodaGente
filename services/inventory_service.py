import datetime as dt
from decimal import Decimal, InvalidOperation

from database import execute, get_db_connection, put_db_connection, query


ITEM_CATEGORIES = [
    ('material', 'Material clínico'),
    ('instrumental', 'Instrumental'),
    ('implante', 'Implante'),
    ('protese', 'Prótese'),
    ('medicamento', 'Medicamento'),
    ('radiologia', 'Radiologia'),
    ('laboratorio', 'Laboratório'),
]

USAGE_TYPES = [
    ('consumo', 'Consumo clínico'),
    ('instrumental', 'Instrumental utilizado'),
    ('implante', 'Implante instalado'),
    ('protese', 'Prótese / componente'),
    ('perda', 'Perda operacional'),
]

_CATEGORY_SLUGS = {value for value, _label in ITEM_CATEGORIES}
_USAGE_TYPE_SLUGS = {value for value, _label in USAGE_TYPES}


def _clean(value):
    text = str(value or '').strip()
    return text or None


def _parse_decimal(value, default='0'):
    if value is None or value == '':
        value = default
    if isinstance(value, Decimal):
        number = value
    else:
        text = str(value).strip().replace('R$', '').replace(' ', '')
        if ',' in text:
            text = text.replace('.', '').replace(',', '.')
        try:
            number = Decimal(text)
        except (InvalidOperation, ValueError):
            raise ValueError(f'Valor numérico inválido: {value}')
    if number < 0:
        raise ValueError('Valores numéricos não podem ser negativos.')
    return number


def _parse_date(value):
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = _clean(value)
    if not text:
        return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f'Data inválida: {value}')


def _parse_datetime(value):
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, dt.date):
        return dt.datetime.combine(value, dt.time.min)
    text = _clean(value)
    if not text:
        return dt.datetime.now()
    for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d/%m/%Y'):
        try:
            return dt.datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f'Data/hora inválida: {value}')


def _normalize_category(value):
    category = _clean(value) or 'material'
    return category if category in _CATEGORY_SLUGS else 'material'


def _normalize_usage_type(value):
    usage_type = _clean(value) or 'consumo'
    return usage_type if usage_type in _USAGE_TYPE_SLUGS else 'consumo'


def _format_money(value):
    return float(value or 0)


def get_item_category_options():
    return ITEM_CATEGORIES


def get_usage_type_options():
    return USAGE_TYPES


def create_inventory_item(form_data, actor_id=None):
    name = _clean(form_data.get('name'))
    if not name:
        raise ValueError('Nome do material é obrigatório.')

    item_id = execute(
        """
        INSERT INTO inventory_items (
            name, category, unit, min_quantity, center_cost, notes, active, created_by
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            name,
            _normalize_category(form_data.get('category')),
            _clean(form_data.get('unit')) or 'unidade',
            _parse_decimal(form_data.get('min_quantity')),
            _clean(form_data.get('center_cost')),
            _clean(form_data.get('notes')),
            form_data.get('active', '1') != '0',
            actor_id,
        ),
    )
    return item_id


def _get_or_create_supplier_id(name):
    supplier_name = _clean(name)
    if not supplier_name:
        return None
    existing = query(
        "SELECT id FROM inventory_suppliers WHERE LOWER(name) = LOWER(%s) LIMIT 1",
        (supplier_name,),
        one=True,
    )
    if existing:
        return existing['id']
    return execute(
        "INSERT INTO inventory_suppliers (name) VALUES (%s) RETURNING id",
        (supplier_name,),
    )


def create_inventory_lot(form_data, actor_id=None):
    item_id = form_data.get('item_id')
    item = query("SELECT id FROM inventory_items WHERE id = %s AND active = TRUE", (item_id,), one=True)
    if not item:
        raise ValueError('Material/insumo não encontrado ou inativo.')

    lot_number = _clean(form_data.get('lot_number'))
    if not lot_number:
        raise ValueError('Número do lote é obrigatório.')

    quantity = _parse_decimal(form_data.get('quantity_initial'))
    if quantity <= 0:
        raise ValueError('Quantidade inicial deve ser maior que zero.')

    lot_id = execute(
        """
        INSERT INTO inventory_lots (
            item_id, supplier_id, lot_number, expiration_date, quantity_initial,
            quantity_current, unit_cost, received_at, center_cost, notes, active,
            created_by
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, %s)
        RETURNING id
        """,
        (
            item_id,
            _get_or_create_supplier_id(form_data.get('supplier_name')),
            lot_number,
            _parse_date(form_data.get('expiration_date')),
            quantity,
            quantity,
            _parse_decimal(form_data.get('unit_cost')),
            _parse_date(form_data.get('received_at')) or dt.date.today(),
            _clean(form_data.get('center_cost')),
            _clean(form_data.get('notes')),
            actor_id,
        ),
    )
    return lot_id


def get_inventory_dashboard(filters=None):
    filters = filters or {}
    q = _clean(filters.get('q'))
    category = _clean(filters.get('category'))

    clauses = ["i.active = TRUE"]
    params = []
    if q:
        clauses.append("(i.name ILIKE %s OR l.lot_number ILIKE %s OR s.name ILIKE %s)")
        params.extend([f'%{q}%', f'%{q}%', f'%{q}%'])
    if category:
        clauses.append("i.category = %s")
        params.append(category)
    where_sql = " AND ".join(clauses)

    items = query(
        f"""
        SELECT i.*,
               COALESCE(SUM(l.quantity_current) FILTER (WHERE l.active = TRUE), 0) AS total_quantity,
               COUNT(l.id) FILTER (WHERE l.active = TRUE) AS lot_count
        FROM inventory_items i
        LEFT JOIN inventory_lots l ON l.item_id = i.id
        LEFT JOIN inventory_suppliers s ON s.id = l.supplier_id
        WHERE {where_sql}
        GROUP BY i.id
        ORDER BY i.name ASC
        """,
        tuple(params),
    )
    lots = query(
        f"""
        SELECT l.*, i.name AS item_name, i.category, i.unit, i.min_quantity,
               s.name AS supplier_name,
               (l.quantity_current * COALESCE(l.unit_cost, 0)) AS current_value
        FROM inventory_lots l
        JOIN inventory_items i ON i.id = l.item_id
        LEFT JOIN inventory_suppliers s ON s.id = l.supplier_id
        WHERE {where_sql.replace('i.active = TRUE', 'i.active = TRUE AND l.active = TRUE')}
        ORDER BY l.expiration_date ASC NULLS LAST, i.name ASC, l.lot_number ASC
        LIMIT 300
        """,
        tuple(params),
    )
    recent_usage = query(
        """
        SELECT u.*, p.nome AS patient_name, i.name AS item_name, i.unit,
               l.lot_number, prof.full_name AS professional_name, prof.username AS professional_username,
               (u.quantity * COALESCE(u.unit_cost_snapshot, 0)) AS total_cost
        FROM inventory_usage u
        JOIN patients p ON p.id = u.patient_id
        JOIN inventory_items i ON i.id = u.item_id
        JOIN inventory_lots l ON l.id = u.lot_id
        LEFT JOIN users prof ON prof.id = u.professional_id
        ORDER BY u.used_at DESC, u.id DESC
        LIMIT 30
        """
    )
    alerts = get_inventory_alerts(limit=30)
    stats = {
        'items': len(items or []),
        'lots': len(lots or []),
        'low_stock': sum(1 for alert in alerts if alert['type'] == 'low_stock'),
        'expired': sum(1 for alert in alerts if alert['type'] == 'expired_lot'),
        'expiring': sum(1 for alert in alerts if alert['type'] == 'expiring_lot'),
        'postop_pending': sum(1 for alert in alerts if alert['type'] == 'implant_postop_pending'),
        'current_value': sum(_format_money(row.get('current_value')) for row in lots or []),
    }
    return {
        'items': items,
        'lots': lots,
        'recent_usage': recent_usage,
        'alerts': alerts,
        'stats': stats,
        'filters': filters,
        'category_options': get_item_category_options(),
        'usage_type_options': get_usage_type_options(),
    }


def list_available_lots():
    return query(
        """
        SELECT l.id, l.item_id, l.lot_number, l.expiration_date, l.quantity_current,
               l.unit_cost, i.name AS item_name, i.category, i.unit,
               s.name AS supplier_name
        FROM inventory_lots l
        JOIN inventory_items i ON i.id = l.item_id
        LEFT JOIN inventory_suppliers s ON s.id = l.supplier_id
        WHERE l.active = TRUE
          AND i.active = TRUE
          AND l.quantity_current > 0
        ORDER BY i.name ASC, l.expiration_date ASC NULLS LAST, l.lot_number ASC
        """
    )


def list_patient_material_usage(patient_id):
    return query(
        """
        SELECT u.*, i.name AS item_name, i.category, i.unit,
               l.lot_number, l.expiration_date,
               s.name AS supplier_name,
               tp.descricao AS treatment_description, tp.dente,
               prof.full_name AS professional_name, prof.username AS professional_username,
               creator.username AS created_by_username,
               (u.quantity * COALESCE(u.unit_cost_snapshot, 0)) AS total_cost
        FROM inventory_usage u
        JOIN inventory_items i ON i.id = u.item_id
        JOIN inventory_lots l ON l.id = u.lot_id
        LEFT JOIN inventory_suppliers s ON s.id = l.supplier_id
        LEFT JOIN tratamento_procedimentos tp ON tp.id = u.treatment_procedure_id
        LEFT JOIN users prof ON prof.id = u.professional_id
        LEFT JOIN users creator ON creator.id = u.created_by
        WHERE u.patient_id = %s
        ORDER BY u.used_at DESC, u.id DESC
        """,
        (patient_id,),
    )


def get_patient_inventory_context(patient_id):
    treatments = query(
        """
        SELECT id, dente, descricao, status
        FROM tratamento_procedimentos
        WHERE patient_id = %s
        ORDER BY criado_em DESC, id DESC
        """,
        (patient_id,),
    )
    usage = list_patient_material_usage(patient_id)
    return {
        'inventory_usage': usage,
        'inventory_lots': list_available_lots(),
        'inventory_treatments': treatments,
        'inventory_usage_type_options': get_usage_type_options(),
        'inventory_total_cost': sum(_format_money(row.get('total_cost')) for row in usage or []),
    }


def register_patient_material_usage(patient_id, form_data, actor_id=None):
    patient = query("SELECT id FROM patients WHERE id = %s", (patient_id,), one=True)
    if not patient:
        raise ValueError('Paciente não encontrado.')

    treatment_id = form_data.get('treatment_procedure_id') or None
    if treatment_id:
        treatment = query(
            "SELECT id FROM tratamento_procedimentos WHERE id = %s AND patient_id = %s",
            (treatment_id, patient_id),
            one=True,
        )
        if not treatment:
            raise ValueError('Procedimento não pertence a este paciente.')

    quantity = _parse_decimal(form_data.get('quantity'), default='1')
    if quantity <= 0:
        raise ValueError('Quantidade utilizada deve ser maior que zero.')

    used_at = _parse_datetime(form_data.get('used_at'))
    professional_id = form_data.get('professional_id') or actor_id

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT l.id AS lot_id, l.item_id, l.quantity_current, l.unit_cost,
                   l.lot_number, i.category, i.name AS item_name
            FROM inventory_lots l
            JOIN inventory_items i ON i.id = l.item_id
            WHERE l.id = %s
              AND l.active = TRUE
              AND i.active = TRUE
            FOR UPDATE
            """,
            (form_data.get('lot_id'),),
        )
        lot = cur.fetchone()
        if not lot:
            raise ValueError('Lote não encontrado ou inativo.')
        if Decimal(lot['quantity_current']) < quantity:
            raise ValueError('Quantidade insuficiente no lote selecionado.')

        category = lot['category']
        usage_type = _normalize_usage_type(form_data.get('usage_type') or category)
        post_op_required = form_data.get('post_op_required') == 'on' or category == 'implante'
        post_op_due_date = _parse_date(form_data.get('post_op_due_date'))
        if post_op_required and not post_op_due_date:
            post_op_due_date = used_at.date() + dt.timedelta(days=7)

        cur.execute(
            """
            INSERT INTO inventory_usage (
                patient_id, treatment_procedure_id, item_id, lot_id, quantity,
                unit_cost_snapshot, usage_type, used_at, professional_id, notes,
                post_op_required, post_op_due_date, created_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                patient_id,
                treatment_id,
                lot['item_id'],
                lot['lot_id'],
                quantity,
                lot['unit_cost'] or Decimal('0'),
                usage_type,
                used_at,
                professional_id,
                _clean(form_data.get('notes')),
                post_op_required,
                post_op_due_date,
                actor_id,
            ),
        )
        usage_id = cur.fetchone()['id']
        cur.execute(
            "UPDATE inventory_lots SET quantity_current = quantity_current - %s WHERE id = %s",
            (quantity, lot['lot_id']),
        )
        conn.commit()
        return {
            'usage_id': usage_id,
            'lot_id': lot['lot_id'],
            'item_id': lot['item_id'],
            'item_name': lot['item_name'],
            'lot_number': lot['lot_number'],
            'quantity': quantity,
            'usage_type': usage_type,
            'post_op_required': post_op_required,
            'post_op_due_date': post_op_due_date,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        put_db_connection(conn)


def mark_post_op_completed(patient_id, usage_id):
    usage = query(
        """
        SELECT u.id, u.patient_id, i.name AS item_name, l.lot_number
        FROM inventory_usage u
        JOIN inventory_items i ON i.id = u.item_id
        JOIN inventory_lots l ON l.id = u.lot_id
        WHERE u.id = %s AND u.patient_id = %s
        """,
        (usage_id, patient_id),
        one=True,
    )
    if not usage:
        raise ValueError('Registro de material não encontrado para este paciente.')
    execute(
        "UPDATE inventory_usage SET post_op_completed_at = NOW() WHERE id = %s",
        (usage_id,),
    )
    return usage


def get_inventory_alerts(limit=50, today=None):
    today = today or dt.date.today()
    expiring_until = today + dt.timedelta(days=30)
    alerts = []

    low_stock = query(
        """
        WITH stock AS (
            SELECT i.id, i.name, i.unit, i.min_quantity,
                   COALESCE(SUM(l.quantity_current) FILTER (WHERE l.active = TRUE), 0) AS total_quantity
            FROM inventory_items i
            LEFT JOIN inventory_lots l ON l.item_id = i.id
            WHERE i.active = TRUE
            GROUP BY i.id
        )
        SELECT *
        FROM stock
        WHERE min_quantity > 0 AND total_quantity <= min_quantity
        ORDER BY total_quantity ASC, name ASC
        LIMIT %s
        """,
        (limit,),
    )
    for row in low_stock or []:
        alerts.append({
            'type': 'low_stock',
            'severity': 'warning',
            'title': 'Estoque baixo',
            'message': f"{row['name']} com {row['total_quantity']} {row['unit']} em estoque.",
            'endpoint': 'admin.inventory',
        })

    expired = query(
        """
        SELECT l.id, l.lot_number, l.expiration_date, l.quantity_current,
               i.name AS item_name, i.unit
        FROM inventory_lots l
        JOIN inventory_items i ON i.id = l.item_id
        WHERE l.active = TRUE
          AND i.active = TRUE
          AND l.quantity_current > 0
          AND l.expiration_date IS NOT NULL
          AND l.expiration_date < %s
        ORDER BY l.expiration_date ASC
        LIMIT %s
        """,
        (today, limit),
    )
    for row in expired or []:
        alerts.append({
            'type': 'expired_lot',
            'severity': 'critical',
            'title': 'Material vencido',
            'message': f"{row['item_name']} lote {row['lot_number']} venceu em {row['expiration_date']}.",
            'endpoint': 'admin.inventory',
        })

    expiring = query(
        """
        SELECT l.id, l.lot_number, l.expiration_date, l.quantity_current,
               i.name AS item_name, i.unit
        FROM inventory_lots l
        JOIN inventory_items i ON i.id = l.item_id
        WHERE l.active = TRUE
          AND i.active = TRUE
          AND l.quantity_current > 0
          AND l.expiration_date IS NOT NULL
          AND l.expiration_date >= %s
          AND l.expiration_date <= %s
        ORDER BY l.expiration_date ASC
        LIMIT %s
        """,
        (today, expiring_until, limit),
    )
    for row in expiring or []:
        alerts.append({
            'type': 'expiring_lot',
            'severity': 'warning',
            'title': 'Material vencendo',
            'message': f"{row['item_name']} lote {row['lot_number']} vence em {row['expiration_date']}.",
            'endpoint': 'admin.inventory',
        })

    pending_postop = query(
        """
        SELECT u.id, u.patient_id, u.post_op_due_date, p.nome AS patient_name,
               i.name AS item_name, l.lot_number
        FROM inventory_usage u
        JOIN patients p ON p.id = u.patient_id
        JOIN inventory_items i ON i.id = u.item_id
        JOIN inventory_lots l ON l.id = u.lot_id
        WHERE u.post_op_required = TRUE
          AND u.post_op_completed_at IS NULL
          AND u.post_op_due_date IS NOT NULL
          AND u.post_op_due_date <= %s
        ORDER BY u.post_op_due_date ASC
        LIMIT %s
        """,
        (today, limit),
    )
    for row in pending_postop or []:
        alerts.append({
            'type': 'implant_postop_pending',
            'severity': 'critical',
            'title': 'Implante sem pós-operatório',
            'message': f"{row['patient_name']} · {row['item_name']} lote {row['lot_number']}.",
            'endpoint': 'patients.view_patient',
            'endpoint_params': {'id': row['patient_id']},
        })

    return alerts[:limit]
