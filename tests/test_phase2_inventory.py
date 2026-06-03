import datetime as dt
from decimal import Decimal

import services.command_center_service as command_center_service
import services.inventory_service as inventory_service
import services.traceability_service as traceability_service
from services.inventory_service import (
    _parse_decimal,
    get_inventory_alerts,
    register_inventory_adjustment,
    register_patient_material_usage,
)
from services.traceability_service import TraceabilityService


def test_parse_decimal_accepts_brazilian_money_format():
    assert _parse_decimal('R$ 1.234,56') == Decimal('1234.56')
    assert _parse_decimal('12.50') == Decimal('12.50')


def test_register_patient_material_usage_decrements_lot_and_requires_implant_postop(monkeypatch):
    queries = []

    def fake_query(sql, params=(), one=False):
        queries.append((sql, params, one))
        if 'FROM patients' in sql:
            return {'id': 42}
        if 'FROM tratamento_procedimentos' in sql:
            return {'id': 9}
        return None

    class FakeCursor:
        def __init__(self):
            self.calls = []
            self.result = None

        def execute(self, sql, params=()):
            self.calls.append((sql, params))
            if 'FOR UPDATE' in sql:
                self.result = {
                    'lot_id': 3,
                    'item_id': 5,
                    'quantity_current': Decimal('2'),
                    'unit_cost': Decimal('1500.00'),
                    'lot_number': 'IMP-001',
                    'category': 'implante',
                    'item_name': 'Implante Cone Morse',
                }
            elif 'RETURNING id' in sql:
                self.result = {'id': 77}
            else:
                self.result = None

        def fetchone(self):
            return self.result

    class FakeConnection:
        def __init__(self):
            self.cursor_obj = FakeCursor()
            self.committed = False
            self.rolled_back = False

        def cursor(self):
            return self.cursor_obj

        def commit(self):
            self.committed = True

        def rollback(self):
            self.rolled_back = True

    fake_conn = FakeConnection()
    monkeypatch.setattr(inventory_service, 'query', fake_query)
    monkeypatch.setattr(inventory_service, 'get_db_connection', lambda: fake_conn)
    monkeypatch.setattr(inventory_service, 'put_db_connection', lambda conn: None)

    result = register_patient_material_usage(42, {
        'lot_id': 3,
        'treatment_procedure_id': 9,
        'quantity': '1',
        'used_at': '2026-06-03T10:00',
    }, actor_id=8)

    assert result['usage_id'] == 77
    assert result['post_op_required'] is True
    assert result['post_op_due_date'] == dt.date(2026, 6, 10)
    assert fake_conn.committed is True
    assert any('UPDATE inventory_lots SET quantity_current' in sql for sql, _params in fake_conn.cursor_obj.calls)


def test_register_inventory_adjustment_records_loss_and_updates_balance(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.calls = []
            self.result = None

        def execute(self, sql, params=()):
            self.calls.append((sql, params))
            if 'FOR UPDATE' in sql:
                self.result = {
                    'lot_id': 3,
                    'item_id': 5,
                    'quantity_current': Decimal('10'),
                    'unit_cost': Decimal('25.00'),
                    'lot_number': 'MAT-001',
                    'item_name': 'Resina',
                    'unit': 'unidade',
                }
            elif 'RETURNING id' in sql:
                self.result = {'id': 88}
            else:
                self.result = None

        def fetchone(self):
            return self.result

    class FakeConnection:
        def __init__(self):
            self.cursor_obj = FakeCursor()
            self.committed = False

        def cursor(self):
            return self.cursor_obj

        def commit(self):
            self.committed = True

        def rollback(self):
            pass

    fake_conn = FakeConnection()
    monkeypatch.setattr(inventory_service, 'get_db_connection', lambda: fake_conn)
    monkeypatch.setattr(inventory_service, 'put_db_connection', lambda conn: None)

    result = register_inventory_adjustment({
        'lot_id': 3,
        'adjustment_type': 'perda',
        'quantity': '2',
        'reason': 'Frasco quebrado',
    }, actor_id=8, authorized_by=8)

    assert result['adjustment_id'] == 88
    assert result['previous_quantity'] == Decimal('10')
    assert result['new_quantity'] == Decimal('8')
    assert fake_conn.committed is True
    assert any('INSERT INTO inventory_adjustments' in sql for sql, _params in fake_conn.cursor_obj.calls)
    assert any('UPDATE inventory_lots SET quantity_current = %s' in sql for sql, _params in fake_conn.cursor_obj.calls)


def test_inventory_alerts_include_stock_expiration_and_postop(monkeypatch):
    def fake_query(sql, params=(), one=False):
        if 'WITH stock AS' in sql:
            return [{
                'id': 1,
                'name': 'Broca cirúrgica',
                'unit': 'unidade',
                'min_quantity': Decimal('5'),
                'total_quantity': Decimal('2'),
            }]
        if 'l.expiration_date <' in sql:
            return [{
                'id': 2,
                'lot_number': 'VENC-1',
                'expiration_date': dt.date(2026, 5, 1),
                'quantity_current': Decimal('3'),
                'item_name': 'Anestésico',
                'unit': 'tubete',
            }]
        if 'l.expiration_date >=' in sql:
            return [{
                'id': 3,
                'lot_number': 'PROX-1',
                'expiration_date': dt.date(2026, 6, 20),
                'quantity_current': Decimal('4'),
                'item_name': 'Resina',
                'unit': 'unidade',
            }]
        if 'post_op_required = TRUE' in sql:
            return [{
                'id': 4,
                'patient_id': 42,
                'post_op_due_date': dt.date(2026, 6, 1),
                'patient_name': 'Paciente Teste',
                'item_name': 'Implante',
                'lot_number': 'IMP-1',
            }]
        return []

    monkeypatch.setattr(inventory_service, 'query', fake_query)

    alerts = get_inventory_alerts(today=dt.date(2026, 6, 3))

    assert [alert['type'] for alert in alerts] == [
        'low_stock',
        'expired_lot',
        'expiring_lot',
        'implant_postop_pending',
    ]
    assert alerts[1]['severity'] == 'critical'
    assert alerts[3]['endpoint_params'] == {'id': 42}


def test_command_center_appends_inventory_alerts():
    alerts = command_center_service.build_operational_alerts(
        red_alert_count=0,
        pending_treatments=0,
        agenda_by_status={},
        priority_queue=[],
        inventory_alerts=[{
            'type': 'expired_lot',
            'severity': 'critical',
            'title': 'Material vencido',
            'message': 'Anestésico vencido.',
            'endpoint': 'admin.inventory',
        }],
    )

    assert alerts[-1]['type'] == 'expired_lot'
    assert alerts[-1]['title'] == 'Material vencido'


def test_material_events_enter_patient_timeline(monkeypatch):
    def fake_query(sql, params=(), one=False):
        assert params == (42,)
        return [{
            'id': 7,
            'used_at': dt.datetime(2026, 6, 3, 9, 30),
            'quantity': Decimal('1'),
            'usage_type': 'implante',
            'notes': 'Torque final registrado.',
            'post_op_required': True,
            'post_op_due_date': dt.date(2026, 6, 10),
            'post_op_completed_at': None,
            'item_name': 'Implante Cone Morse',
            'unit': 'unidade',
            'category': 'implante',
            'lot_number': 'IMP-001',
            'expiration_date': dt.date(2028, 6, 1),
            'supplier_name': 'Fornecedor Demo',
            'treatment_description': 'Instalação de implante',
            'dente': '36',
            'professional_name': 'Dra. Teste',
            'professional_username': 'teste',
        }]

    monkeypatch.setattr(traceability_service, 'query', fake_query)

    events = TraceabilityService._material_events(42)

    assert events[0]['category'] == 'Material'
    assert events[0]['title'] == 'Implante utilizado'
    assert events[0]['status'] == 'Pós-operatório pendente'
    assert 'lote IMP-001' in events[0]['description']
