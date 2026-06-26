import datetime as dt
import difflib
import re
import unicodedata
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

ADJUSTMENT_TYPES = [
    ('perda', 'Perda operacional'),
    ('descarte_vencido', 'Descarte por vencimento'),
    ('ajuste_saida', 'Ajuste de saída'),
    ('ajuste_entrada', 'Ajuste de entrada'),
    ('inventario_positivo', 'Inventário físico positivo'),
]

INVOICE_SOURCE_TYPES = [
    ('xml_nfe', 'XML da NF-e'),
    ('pdf_danfe', 'PDF (DANFE)'),
    ('manual', 'Lançamento manual de nota'),
    ('avulsa', 'Compra avulsa (sem nota)'),
]

_ITEM_MATCH_MIN_SCORE = 0.72
_CATEGORY_SLUGS = {value for value, _label in ITEM_CATEGORIES}
_USAGE_TYPE_SLUGS = {value for value, _label in USAGE_TYPES}
_ADJUSTMENT_TYPE_SLUGS = {value for value, _label in ADJUSTMENT_TYPES}
_NEGATIVE_ADJUSTMENTS = {'perda', 'descarte_vencido', 'ajuste_saida'}
_POSITIVE_ADJUSTMENTS = {'ajuste_entrada', 'inventario_positivo'}


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


def _normalize_adjustment_type(value):
    adjustment_type = _clean(value) or 'perda'
    return adjustment_type if adjustment_type in _ADJUSTMENT_TYPE_SLUGS else 'perda'


def _format_money(value):
    return float(value or 0)


def get_item_category_options():
    return ITEM_CATEGORIES


def get_usage_type_options():
    return USAGE_TYPES


def get_adjustment_type_options():
    return ADJUSTMENT_TYPES


def create_inventory_item(form_data, actor_id=None):
    name = _clean(form_data.get('name'))
    if not name:
        raise ValueError('Nome do material é obrigatório.')

    item_id = execute(
        """
        INSERT INTO inventory_items (
            name, category, unit, min_quantity, center_cost, notes, ean, active, created_by
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            name,
            _normalize_category(form_data.get('category')),
            _clean(form_data.get('unit')) or 'unidade',
            _parse_decimal(form_data.get('min_quantity')),
            _clean(form_data.get('center_cost')),
            _clean(form_data.get('notes')),
            _clean(form_data.get('ean')),
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
               s.name AS supplier_name, inv.invoice_number, inv.source_type AS invoice_source_type,
               (l.quantity_current * COALESCE(l.unit_cost, 0)) AS current_value
        FROM inventory_lots l
        JOIN inventory_items i ON i.id = l.item_id
        LEFT JOIN inventory_suppliers s ON s.id = l.supplier_id
        LEFT JOIN inventory_invoices inv ON inv.id = l.invoice_id
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
    recent_adjustments = query(
        """
        SELECT a.*, i.name AS item_name, i.unit, l.lot_number,
               adjusted.username AS adjusted_by_username,
               authorized.username AS authorized_by_username,
               (a.quantity * COALESCE(a.unit_cost_snapshot, 0)) AS total_cost
        FROM inventory_adjustments a
        JOIN inventory_items i ON i.id = a.item_id
        JOIN inventory_lots l ON l.id = a.lot_id
        LEFT JOIN users adjusted ON adjusted.id = a.adjusted_by
        LEFT JOIN users authorized ON authorized.id = a.authorized_by
        ORDER BY a.created_at DESC, a.id DESC
        LIMIT 30
        """
    )
    alerts = get_inventory_alerts(limit=30)
    pending_invoices = query(
        "SELECT COUNT(*) AS total FROM inventory_invoices WHERE status = 'rascunho'",
        one=True,
    )
    stats = {
        'materials_count': len(items or []),
        'lots': len(lots or []),
        'low_stock': sum(1 for alert in alerts if alert['type'] == 'low_stock'),
        'expired': sum(1 for alert in alerts if alert['type'] == 'expired_lot'),
        'expiring': sum(1 for alert in alerts if alert['type'] == 'expiring_lot'),
        'postop_pending': sum(1 for alert in alerts if alert['type'] == 'implant_postop_pending'),
        'current_value': sum(_format_money(row.get('current_value')) for row in lots or []),
        'pending_invoices': (pending_invoices or {}).get('total', 0),
    }
    return {
        'materials': items,
        'lots': lots,
        'recent_usage': recent_usage,
        'recent_adjustments': recent_adjustments,
        'alerts': alerts,
        'stats': stats,
        'filters': filters,
        'category_options': get_item_category_options(),
        'usage_type_options': get_usage_type_options(),
        'adjustment_type_options': get_adjustment_type_options(),
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


def register_inventory_adjustment(form_data, actor_id=None, authorized_by=None):
    quantity = _parse_decimal(form_data.get('quantity'), default='0')
    if quantity <= 0:
        raise ValueError('Quantidade do ajuste deve ser maior que zero.')

    reason = _clean(form_data.get('reason'))
    if not reason:
        raise ValueError('Motivo do ajuste é obrigatório.')

    adjustment_type = _normalize_adjustment_type(form_data.get('adjustment_type'))

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT l.id AS lot_id, l.item_id, l.quantity_current, l.unit_cost,
                   l.lot_number, i.name AS item_name, i.unit
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

        previous_quantity = Decimal(lot['quantity_current'])
        if adjustment_type in _NEGATIVE_ADJUSTMENTS:
            if previous_quantity < quantity:
                raise ValueError('Quantidade do ajuste é maior que o saldo atual do lote.')
            new_quantity = previous_quantity - quantity
        elif adjustment_type in _POSITIVE_ADJUSTMENTS:
            new_quantity = previous_quantity + quantity
        else:
            raise ValueError('Tipo de ajuste inválido.')

        cur.execute(
            """
            INSERT INTO inventory_adjustments (
                item_id, lot_id, adjustment_type, quantity, previous_quantity,
                new_quantity, unit_cost_snapshot, reason, notes, adjusted_by,
                authorized_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                lot['item_id'],
                lot['lot_id'],
                adjustment_type,
                quantity,
                previous_quantity,
                new_quantity,
                lot['unit_cost'] or Decimal('0'),
                reason,
                _clean(form_data.get('notes')),
                actor_id,
                authorized_by or actor_id,
            ),
        )
        adjustment_id = cur.fetchone()['id']
        cur.execute(
            "UPDATE inventory_lots SET quantity_current = %s WHERE id = %s",
            (new_quantity, lot['lot_id']),
        )
        conn.commit()
        return {
            'adjustment_id': adjustment_id,
            'item_id': lot['item_id'],
            'item_name': lot['item_name'],
            'lot_id': lot['lot_id'],
            'lot_number': lot['lot_number'],
            'adjustment_type': adjustment_type,
            'quantity': quantity,
            'previous_quantity': previous_quantity,
            'new_quantity': new_quantity,
            'reason': reason,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        put_db_connection(conn)


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


def get_invoice_source_type_options():
    return INVOICE_SOURCE_TYPES


def list_active_items():
    return query(
        "SELECT id, name, category, unit FROM inventory_items WHERE active = TRUE ORDER BY name ASC"
    )


# --- CNPJ -------------------------------------------------------------

def normalize_cnpj(value):
    digits = re.sub(r'\D', '', str(value or ''))
    return digits or None


def _cnpj_check_digits(base_digits):
    def calc(nums, weights):
        total = sum(int(n) * w for n, w in zip(nums, weights))
        remainder = total % 11
        return '0' if remainder < 2 else str(11 - remainder)

    d1 = calc(base_digits, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    d2 = calc(base_digits + d1, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return d1 + d2


def is_valid_cnpj(value):
    digits = normalize_cnpj(value)
    if not digits or len(digits) != 14 or len(set(digits)) == 1:
        return False
    return digits[12:] == _cnpj_check_digits(digits[:12])


def format_cnpj(value):
    digits = normalize_cnpj(value)
    if not digits or len(digits) != 14:
        return _clean(value)
    return f"{digits[0:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:14]}"


# --- Fornecedores -------------------------------------------------------

def get_supplier(supplier_id):
    supplier = query("SELECT * FROM inventory_suppliers WHERE id = %s", (supplier_id,), one=True)
    if not supplier:
        raise ValueError('Fornecedor não encontrado.')
    return supplier


def list_suppliers(q=None):
    q = _clean(q)
    if q:
        return query(
            "SELECT * FROM inventory_suppliers WHERE name ILIKE %s OR cnpj ILIKE %s ORDER BY name ASC",
            (f'%{q}%', f'%{q}%'),
        )
    return query("SELECT * FROM inventory_suppliers ORDER BY name ASC")


def create_supplier(form_data):
    name = _clean(form_data.get('name'))
    if not name:
        raise ValueError('Nome do fornecedor é obrigatório.')
    cnpj = normalize_cnpj(form_data.get('cnpj'))
    if cnpj and not is_valid_cnpj(cnpj):
        raise ValueError('CNPJ inválido.')
    return execute(
        """
        INSERT INTO inventory_suppliers (name, cnpj, document, phone, email, active)
        VALUES (%s, %s, %s, %s, %s, TRUE)
        RETURNING id
        """,
        (name, cnpj, cnpj, _clean(form_data.get('phone')), _clean(form_data.get('email'))),
    )


def update_supplier(supplier_id, form_data):
    name = _clean(form_data.get('name'))
    if not name:
        raise ValueError('Nome do fornecedor é obrigatório.')
    cnpj = normalize_cnpj(form_data.get('cnpj'))
    if cnpj and not is_valid_cnpj(cnpj):
        raise ValueError('CNPJ inválido.')
    execute(
        """
        UPDATE inventory_suppliers
        SET name = %s, cnpj = %s, document = %s, phone = %s, email = %s, active = %s
        WHERE id = %s
        """,
        (
            name, cnpj, cnpj, _clean(form_data.get('phone')), _clean(form_data.get('email')),
            form_data.get('active', '1') != '0', supplier_id,
        ),
    )


def get_or_create_supplier(name=None, cnpj=None):
    normalized_cnpj = normalize_cnpj(cnpj)
    if normalized_cnpj:
        existing = query(
            "SELECT id, name FROM inventory_suppliers WHERE cnpj = %s LIMIT 1",
            (normalized_cnpj,),
            one=True,
        )
        if existing:
            return existing['id']

    supplier_name = _clean(name)
    if supplier_name:
        existing = query(
            "SELECT id, cnpj FROM inventory_suppliers WHERE LOWER(name) = LOWER(%s) LIMIT 1",
            (supplier_name,),
            one=True,
        )
        if existing:
            if normalized_cnpj and not existing.get('cnpj'):
                execute(
                    "UPDATE inventory_suppliers SET cnpj = %s, document = %s WHERE id = %s",
                    (normalized_cnpj, normalized_cnpj, existing['id']),
                )
            return existing['id']

    if not supplier_name and not normalized_cnpj:
        return None

    return execute(
        "INSERT INTO inventory_suppliers (name, cnpj, document) VALUES (%s, %s, %s) RETURNING id",
        (supplier_name or normalized_cnpj, normalized_cnpj, normalized_cnpj),
    )


# --- Conciliação de itens (matching) ------------------------------------

def _normalize_text(value):
    text = _clean(value) or ''
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^a-z0-9]+', ' ', text.lower()).strip()


def suggest_item_match(description_raw, ean=None):
    ean = _clean(ean)
    if ean:
        match = query(
            "SELECT id FROM inventory_items WHERE ean = %s AND active = TRUE LIMIT 1",
            (ean,),
            one=True,
        )
        if match:
            return match['id'], 'exact'

    normalized = _normalize_text(description_raw)
    if not normalized:
        return None, 'new'

    candidates = query("SELECT id, name FROM inventory_items WHERE active = TRUE")
    best_id, best_score = None, 0.0
    for candidate in candidates or []:
        score = difflib.SequenceMatcher(None, normalized, _normalize_text(candidate['name'])).ratio()
        if score > best_score:
            best_score, best_id = score, candidate['id']
    if best_id and best_score >= _ITEM_MATCH_MIN_SCORE:
        return best_id, 'suggested'
    return None, 'new'


# --- Notas fiscais / compras --------------------------------------------

def _insert_invoice_item(invoice_id, row):
    description_raw = _clean(row.get('description_raw')) or 'Item sem descrição'
    ean = _clean(row.get('ean'))
    item_id, confidence = suggest_item_match(description_raw, ean)
    return execute(
        """
        INSERT INTO inventory_invoice_items (
            invoice_id, item_id, description_raw, ncm, cfop, ean, unit, quantity,
            unit_value, total_value, match_confidence, expiration_date,
            manufacturer_lot_number
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            invoice_id, item_id, description_raw, _clean(row.get('ncm')), _clean(row.get('cfop')),
            ean, _clean(row.get('unit')) or 'unidade',
            _parse_decimal(row.get('quantity')), _parse_decimal(row.get('unit_value')),
            _parse_decimal(row.get('total_value')), confidence,
            _parse_date(row.get('expiration_date')), _clean(row.get('manufacturer_lot_number')),
        ),
    )


def create_invoice_draft(source_type, header, rows, actor_id=None, raw_file_path=None, raw_file_type=None):
    valid_types = {value for value, _label in INVOICE_SOURCE_TYPES}
    if source_type not in valid_types:
        raise ValueError('Origem da entrada de mercadoria inválida.')

    header = header or {}
    access_key = None
    raw_access_key = _clean(header.get('access_key'))
    if raw_access_key:
        access_key = re.sub(r'\D', '', raw_access_key)
        if len(access_key) != 44:
            raise ValueError('Chave de acesso da NF-e deve ter 44 dígitos.')
        existing = query(
            "SELECT id, invoice_number FROM inventory_invoices WHERE access_key = %s",
            (access_key,),
            one=True,
        )
        if existing:
            raise ValueError(
                f"Esta NF-e já foi importada (nota nº {existing['invoice_number'] or existing['id']})."
            )

    supplier_id = get_or_create_supplier(header.get('supplier_name'), header.get('supplier_cnpj'))

    invoice_id = execute(
        """
        INSERT INTO inventory_invoices (
            supplier_id, source_type, status, access_key, invoice_number, invoice_series,
            issue_date, total_value, raw_file_path, raw_file_type, notes, created_by
        )
        VALUES (%s, %s, 'rascunho', %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            supplier_id, source_type, access_key,
            _clean(header.get('invoice_number')), _clean(header.get('invoice_series')),
            _parse_date(header.get('issue_date')), _parse_decimal(header.get('total_value')),
            raw_file_path, raw_file_type, _clean(header.get('notes')), actor_id,
        ),
    )

    rows = rows or [{}]
    for row in rows:
        _insert_invoice_item(invoice_id, row)
    return invoice_id


def list_invoices(filters=None):
    filters = filters or {}
    clauses, params = ["1=1"], []
    status = _clean(filters.get('status'))
    if status:
        clauses.append("inv.status = %s")
        params.append(status)
    q = _clean(filters.get('q'))
    if q:
        clauses.append("(s.name ILIKE %s OR inv.invoice_number ILIKE %s)")
        params.extend([f'%{q}%', f'%{q}%'])
    where_sql = " AND ".join(clauses)
    return query(
        f"""
        SELECT inv.*, s.name AS supplier_name, s.cnpj AS supplier_cnpj,
               COUNT(ii.id) AS item_count
        FROM inventory_invoices inv
        LEFT JOIN inventory_suppliers s ON s.id = inv.supplier_id
        LEFT JOIN inventory_invoice_items ii ON ii.invoice_id = inv.id
        WHERE {where_sql}
        GROUP BY inv.id, s.name, s.cnpj
        ORDER BY inv.created_at DESC
        LIMIT 200
        """,
        tuple(params),
    )


def list_confirmed_invoices_for_period(start_date, end_date):
    return query(
        """
        SELECT inv.*, s.name AS supplier_name, s.cnpj AS supplier_cnpj,
               COUNT(ii.id) AS item_count
        FROM inventory_invoices inv
        LEFT JOIN inventory_suppliers s ON s.id = inv.supplier_id
        LEFT JOIN inventory_invoice_items ii ON ii.invoice_id = inv.id
        WHERE inv.status = 'confirmada'
          AND COALESCE(inv.issue_date, inv.confirmed_at::date) BETWEEN %s AND %s
        GROUP BY inv.id, s.name, s.cnpj
        ORDER BY COALESCE(inv.issue_date, inv.confirmed_at::date) ASC, inv.id ASC
        """,
        (start_date, end_date),
    )


def get_invoice_detail(invoice_id):
    invoice = query(
        """
        SELECT inv.*, s.name AS supplier_name, s.cnpj AS supplier_cnpj,
               creator.username AS created_by_username,
               confirmer.username AS confirmed_by_username
        FROM inventory_invoices inv
        LEFT JOIN inventory_suppliers s ON s.id = inv.supplier_id
        LEFT JOIN users creator ON creator.id = inv.created_by
        LEFT JOIN users confirmer ON confirmer.id = inv.confirmed_by
        WHERE inv.id = %s
        """,
        (invoice_id,),
        one=True,
    )
    if not invoice:
        raise ValueError('Nota fiscal/compra não encontrada.')
    invoice['lines'] = query(
        """
        SELECT ii.*, i.name AS item_name, i.category AS item_category
        FROM inventory_invoice_items ii
        LEFT JOIN inventory_items i ON i.id = ii.item_id
        WHERE ii.invoice_id = %s
        ORDER BY ii.id ASC
        """,
        (invoice_id,),
    )
    return invoice


def _require_draft_invoice(invoice_id):
    invoice = query(
        "SELECT id, status FROM inventory_invoices WHERE id = %s",
        (invoice_id,),
        one=True,
    )
    if not invoice:
        raise ValueError('Nota fiscal/compra não encontrada.')
    if invoice['status'] != 'rascunho':
        raise ValueError('Esta nota/compra já foi confirmada ou descartada.')
    return invoice


def add_invoice_item_row(invoice_id):
    _require_draft_invoice(invoice_id)
    return _insert_invoice_item(invoice_id, {})


def delete_invoice_item_row(invoice_id, invoice_item_id):
    _require_draft_invoice(invoice_id)
    remaining = query(
        "SELECT COUNT(*) AS total FROM inventory_invoice_items WHERE invoice_id = %s",
        (invoice_id,),
        one=True,
    )
    if remaining and remaining['total'] <= 1:
        raise ValueError('A nota/compra precisa ter ao menos um item.')
    execute(
        "DELETE FROM inventory_invoice_items WHERE id = %s AND invoice_id = %s",
        (invoice_item_id, invoice_id),
    )


def discard_invoice(invoice_id):
    _require_draft_invoice(invoice_id)
    execute("UPDATE inventory_invoices SET status = 'descartada' WHERE id = %s", (invoice_id,))


def confirm_invoice(invoice_id, header, rows_updates, actor_id=None):
    """Concilia e confirma uma nota/compra em rascunho, gerando um lote de
    estoque por item (mesma semântica de create_inventory_lot, mas dentro de
    uma única transação para garantir atomicidade entre todos os itens)."""
    header = header or {}
    rows_updates = rows_updates or {}

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, status FROM inventory_invoices WHERE id = %s FOR UPDATE",
            (invoice_id,),
        )
        invoice = cur.fetchone()
        if not invoice:
            raise ValueError('Nota fiscal/compra não encontrada.')
        if invoice['status'] != 'rascunho':
            raise ValueError('Esta nota/compra já foi confirmada ou descartada.')

        supplier_id = get_or_create_supplier(header.get('supplier_name'), header.get('supplier_cnpj'))

        cur.execute(
            """
            UPDATE inventory_invoices
            SET supplier_id = %s, invoice_number = %s, invoice_series = %s,
                issue_date = %s, total_value = %s, notes = %s
            WHERE id = %s
            """,
            (
                supplier_id, _clean(header.get('invoice_number')), _clean(header.get('invoice_series')),
                _parse_date(header.get('issue_date')), _parse_decimal(header.get('total_value')),
                _clean(header.get('notes')), invoice_id,
            ),
        )

        cur.execute(
            "SELECT id FROM inventory_invoice_items WHERE invoice_id = %s ORDER BY id ASC",
            (invoice_id,),
        )
        row_ids = [row['id'] for row in cur.fetchall()]
        if not row_ids:
            raise ValueError('A nota/compra não possui itens para confirmar.')

        created_lots = []
        missing_rows = []
        for row_id in row_ids:
            update = rows_updates.get(str(row_id)) or {}
            item_id = update.get('item_id') or None
            new_item_name = _clean(update.get('new_item_name'))
            if not item_id and new_item_name:
                cur.execute(
                    """
                    INSERT INTO inventory_items (name, category, unit, active, created_by)
                    VALUES (%s, %s, %s, TRUE, %s)
                    RETURNING id
                    """,
                    (
                        new_item_name,
                        _normalize_category(update.get('new_item_category')),
                        _clean(update.get('unit')) or 'unidade',
                        actor_id,
                    ),
                )
                item_id = cur.fetchone()['id']

            expiration_date = _parse_date(update.get('expiration_date'))
            try:
                quantity = _parse_decimal(update.get('quantity'))
            except ValueError:
                quantity = Decimal('0')

            if not item_id or not expiration_date or quantity <= 0:
                missing_rows.append(row_id)
                continue

            unit_cost = _parse_decimal(update.get('unit_value'))
            lot_number = _clean(update.get('manufacturer_lot_number')) or f"NF-{invoice_id}-{row_id}"

            cur.execute(
                """
                UPDATE inventory_invoice_items
                SET item_id = %s, quantity = %s, unit_value = %s, total_value = %s,
                    expiration_date = %s, manufacturer_lot_number = %s
                WHERE id = %s
                """,
                (item_id, quantity, unit_cost, quantity * unit_cost, expiration_date, lot_number, row_id),
            )
            cur.execute(
                """
                INSERT INTO inventory_lots (
                    item_id, supplier_id, lot_number, expiration_date, quantity_initial,
                    quantity_current, unit_cost, received_at, active, created_by,
                    invoice_id, invoice_item_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE, %s, %s, %s)
                RETURNING id
                """,
                (
                    item_id, supplier_id, lot_number, expiration_date, quantity, quantity,
                    unit_cost, dt.date.today(), actor_id, invoice_id, row_id,
                ),
            )
            lot_id = cur.fetchone()['id']
            cur.execute(
                "UPDATE inventory_invoice_items SET lot_id = %s WHERE id = %s",
                (lot_id, row_id),
            )
            created_lots.append(lot_id)

        if missing_rows:
            raise ValueError(
                f"Preencha material e validade para {len(missing_rows)} item(ns) antes de confirmar."
            )

        cur.execute(
            "UPDATE inventory_invoices SET status = 'confirmada', confirmed_by = %s, confirmed_at = NOW() WHERE id = %s",
            (actor_id, invoice_id),
        )
        conn.commit()
        return {'invoice_id': invoice_id, 'lot_ids': created_lots}
    except Exception:
        conn.rollback()
        raise
    finally:
        put_db_connection(conn)
