import datetime as dt
from io import BytesIO
from decimal import Decimal

import pytest

import services.inventory_service as inventory_service
from constants import Role, role_has_permission
from services.danfe_pdf_service import parse_danfe_pdf
from services.inventory_service import (
    confirm_invoice,
    create_invoice_draft,
    format_cnpj,
    is_valid_cnpj,
    normalize_cnpj,
    suggest_item_match,
)
from services.nfe_xml_service import (
    NFeParsingError,
    calc_access_key_check_digit,
    decode_access_key,
    parse_nfe_xml,
    validate_access_key_checksum,
)

# CNPJ de teste oficialmente divulgado pela Receita Federal como exemplo válido.
VALID_CNPJ = '11.222.333/0001-81'


def _sample_access_key():
    base = '13' + '2606' + '11222333000181' + '55' + '001' + '000000123' + '1' + '00000001'
    assert len(base) == 43
    return base + calc_access_key_check_digit(base)


def _sample_nfe_xml(access_key, *, with_item=True):
    items = ''
    if with_item:
        items = """
        <det nItem="1">
            <prod>
                <cProd>001</cProd>
                <xProd>Resina composta A2</xProd>
                <NCM>30063000</NCM>
                <CFOP>5102</CFOP>
                <cEAN>7891234567890</cEAN>
                <uCom>UN</uCom>
                <qCom>10.0000</qCom>
                <vUnCom>25.50</vUnCom>
                <vProd>255.00</vProd>
            </prod>
        </det>
        """
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <nfeProc xmlns="http://www.portalfiscal.inf.fazenda.gov.br/nfe">
        <NFe>
            <infNFe Id="NFe{access_key}" versao="4.00">
                <ide>
                    <cUF>13</cUF>
                    <nNF>123</nNF>
                    <serie>1</serie>
                    <dhEmi>2026-06-26T10:00:00-03:00</dhEmi>
                </ide>
                <emit>
                    <CNPJ>11222333000181</CNPJ>
                    <xNome>Fornecedor Odontológico LTDA</xNome>
                </emit>
                {items}
                <total>
                    <ICMSTot>
                        <vNF>255.00</vNF>
                    </ICMSTot>
                </total>
            </infNFe>
        </NFe>
    </nfeProc>
    """.encode('utf-8')


# --- CNPJ -----------------------------------------------------------------

def test_cnpj_validation_accepts_known_valid_document():
    assert normalize_cnpj(VALID_CNPJ) == '11222333000181'
    assert is_valid_cnpj(VALID_CNPJ)
    assert format_cnpj('11222333000181') == VALID_CNPJ


def test_cnpj_validation_rejects_wrong_check_digit():
    assert not is_valid_cnpj('11.222.333/0001-00')
    assert not is_valid_cnpj('111111111111')


def test_get_or_create_supplier_rejects_invalid_cnpj():
    with pytest.raises(ValueError, match='CNPJ inválido'):
        inventory_service.get_or_create_supplier('Fornecedor inválido', '11.222.333/0001-00')


# --- Chave de acesso --------------------------------------------------------

def test_access_key_checksum_and_decoding_roundtrip():
    key = _sample_access_key()
    assert validate_access_key_checksum(key)

    decoded = decode_access_key(key)
    assert decoded['supplier_cnpj'] == '11222333000181'
    assert decoded['invoice_number'] == '123'
    assert decoded['invoice_series'] == '1'


def test_access_key_checksum_rejects_tampered_digits():
    key = _sample_access_key()
    tampered = key[:-1] + ('0' if key[-1] != '0' else '1')
    assert not validate_access_key_checksum(tampered)


# --- XML da NF-e -------------------------------------------------------------

def test_parse_nfe_xml_extracts_header_and_items():
    key = _sample_access_key()
    header, rows = parse_nfe_xml(_sample_nfe_xml(key))

    assert header['access_key'] == key
    assert header['invoice_number'] == '123'
    assert header['invoice_series'] == '1'
    assert header['supplier_cnpj'] == '11222333000181'
    assert header['supplier_name'] == 'Fornecedor Odontológico LTDA'
    assert header['total_value'] == '255.00'

    assert len(rows) == 1
    assert rows[0]['description_raw'] == 'Resina composta A2'
    assert rows[0]['ncm'] == '30063000'
    assert rows[0]['ean'] == '7891234567890'
    assert rows[0]['quantity'] == '10.0000'


def test_parse_nfe_xml_rejects_malformed_xml():
    with pytest.raises(NFeParsingError):
        parse_nfe_xml(b'<not-even-xml')


def test_parse_nfe_xml_rejects_missing_inf_nfe():
    with pytest.raises(NFeParsingError):
        parse_nfe_xml(b'<?xml version="1.0"?><root></root>')


def test_parse_nfe_xml_rejects_invoice_without_items():
    key = _sample_access_key()
    with pytest.raises(NFeParsingError):
        parse_nfe_xml(_sample_nfe_xml(key, with_item=False))


# --- PDF do DANFE (best effort) ---------------------------------------------

def test_parse_danfe_pdf_extracts_access_key_total_and_decodes_header():
    pytest.importorskip('weasyprint')
    from weasyprint import HTML

    key = _sample_access_key()
    grouped_key = ' '.join(key[i:i + 4] for i in range(0, 44, 4))
    html = f"""
    <html><body>
        <p>DANFE - Documento Auxiliar da Nota Fiscal Eletrônica</p>
        <p>CHAVE DE ACESSO {grouped_key}</p>
        <p>EMISSÃO 26/06/2026</p>
        <p>VALOR TOTAL DA NOTA R$ 255,00</p>
    </body></html>
    """
    pdf_bytes = HTML(string=html).write_pdf()

    header, _rows = parse_danfe_pdf(pdf_bytes)

    assert header['access_key'] == key
    assert header['supplier_cnpj'] == '11222333000181'
    assert header['invoice_number'] == '123'
    assert header['invoice_series'] == '1'
    assert header['total_value'] == '255.00'
    assert header['issue_date'] == '2026-06-26'


def test_parse_danfe_pdf_without_recognizable_data_returns_empty_header():
    pytest.importorskip('weasyprint')
    from weasyprint import HTML

    pdf_bytes = HTML(string='<html><body><p>Documento ilegível</p></body></html>').write_pdf()
    header, rows = parse_danfe_pdf(pdf_bytes)

    assert header['access_key'] is None
    assert rows == []


# --- Conciliação de itens (matching) ----------------------------------------

def test_suggest_item_match_prefers_exact_ean(monkeypatch):
    def fake_query(sql, params=(), one=False):
        if 'WHERE ean = %s' in sql:
            return {'id': 7}
        return []

    monkeypatch.setattr(inventory_service, 'query', fake_query)

    item_id, confidence = suggest_item_match('Qualquer descrição', ean='123')
    assert (item_id, confidence) == (7, 'exact')


def test_suggest_item_match_falls_back_to_fuzzy_name(monkeypatch):
    def fake_query(sql, params=(), one=False):
        if 'WHERE ean = %s' in sql:
            return None
        return [{'id': 1, 'name': 'Resina composta A2'}, {'id': 2, 'name': 'Luva de procedimento M'}]

    monkeypatch.setattr(inventory_service, 'query', fake_query)

    item_id, confidence = suggest_item_match('Resina composta A2 - cor A2')
    assert item_id == 1
    assert confidence == 'suggested'


def test_suggest_item_match_returns_new_when_nothing_close(monkeypatch):
    monkeypatch.setattr(inventory_service, 'query', lambda *a, **k: [])
    item_id, confidence = suggest_item_match('Produto totalmente desconhecido')
    assert (item_id, confidence) == (None, 'new')


# --- Rascunho de nota / compra -----------------------------------------------

def test_create_invoice_draft_rejects_duplicate_access_key(monkeypatch):
    monkeypatch.setattr(inventory_service, 'get_or_create_supplier', lambda *a, **k: None)

    def fake_query(sql, params=(), one=False):
        if 'WHERE access_key = %s' in sql:
            return {'id': 5, 'invoice_number': '999'}
        return []

    monkeypatch.setattr(inventory_service, 'query', fake_query)

    with pytest.raises(ValueError, match='já foi importada'):
        create_invoice_draft(
            'xml_nfe',
            {'access_key': _sample_access_key()},
            [{'description_raw': 'Item'}],
        )


def test_create_invoice_draft_rejects_unknown_source_type():
    with pytest.raises(ValueError):
        create_invoice_draft('fonte_inventada', {}, [])


# --- Confirmação (transação) -------------------------------------------------

class _FakeCursor:
    def __init__(self, item_rows):
        self._item_rows = item_rows
        self.calls = []
        self._result = None
        self._rows = []
        self._next_item_id = 700

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if 'SELECT id, status FROM inventory_invoices' in sql:
            self._result = {'id': params[0], 'status': 'rascunho'}
        elif 'SELECT id, name FROM inventory_suppliers WHERE cnpj' in sql:
            self._result = None
        elif 'SELECT id, cnpj FROM inventory_suppliers WHERE LOWER(name)' in sql:
            self._result = None
        elif sql.strip().startswith('INSERT INTO inventory_suppliers'):
            self._result = {'id': 3}
        elif 'SELECT id FROM inventory_invoice_items WHERE invoice_id' in sql:
            self._result = None
            self._rows = [{'id': row_id} for row_id in self._item_rows]
        elif sql.strip().startswith('INSERT INTO inventory_items'):
            self._result = {'id': self._next_item_id}
            self._next_item_id += 1
        elif sql.strip().startswith('INSERT INTO inventory_lots'):
            self._result = {'id': 900 + len(self.calls)}
        else:
            self._result = None

    def fetchone(self):
        return self._result

    def fetchall(self):
        return getattr(self, '_rows', [])


class _FakeConnection:
    def __init__(self, item_rows):
        self.cursor_obj = _FakeCursor(item_rows)
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def test_confirm_invoice_creates_one_lot_per_resolved_item(monkeypatch):
    fake_conn = _FakeConnection(item_rows=[1, 2])
    monkeypatch.setattr(inventory_service, 'get_db_connection', lambda: fake_conn)
    monkeypatch.setattr(inventory_service, 'put_db_connection', lambda conn: None)

    rows_updates = {
        '1': {'item_id': '10', 'quantity': '5', 'unit_value': '2.00', 'expiration_date': '2027-01-01'},
        '2': {'item_id': '11', 'quantity': '2', 'unit_value': '3.00', 'expiration_date': '2027-02-01'},
    }
    result = confirm_invoice(42, {'supplier_name': 'Fornecedor X'}, rows_updates, actor_id=1)

    assert result['invoice_id'] == 42
    assert len(result['lot_ids']) == 2
    assert fake_conn.committed is True
    assert any(sql.strip().startswith('INSERT INTO inventory_lots') for sql, _ in fake_conn.cursor_obj.calls)
    assert any("status = 'confirmada'" in sql for sql, _ in fake_conn.cursor_obj.calls)


def test_confirm_invoice_blocks_when_expiration_date_missing(monkeypatch):
    fake_conn = _FakeConnection(item_rows=[1])
    monkeypatch.setattr(inventory_service, 'get_db_connection', lambda: fake_conn)
    monkeypatch.setattr(inventory_service, 'put_db_connection', lambda conn: None)

    rows_updates = {
        '1': {'item_id': '10', 'quantity': '5', 'unit_value': '2.00'},  # sem expiration_date
    }
    with pytest.raises(ValueError, match='validade'):
        confirm_invoice(42, {}, rows_updates, actor_id=1)

    assert fake_conn.rolled_back is True
    assert fake_conn.committed is False


def test_confirm_invoice_creates_new_material_when_invoice_row_uses_new_marker(monkeypatch):
    fake_conn = _FakeConnection(item_rows=[1])
    monkeypatch.setattr(inventory_service, 'get_db_connection', lambda: fake_conn)
    monkeypatch.setattr(inventory_service, 'put_db_connection', lambda conn: None)

    rows_updates = {
        '1': {
            'item_id': '__new__',
            'new_item_name': 'Resina Bulk Fill',
            'new_item_category': 'material',
            'unit': 'seringa',
            'quantity': '2',
            'unit_value': '15.00',
            'expiration_date': '2027-01-01',
        },
    }
    result = confirm_invoice(42, {'supplier_name': 'Fornecedor X'}, rows_updates, actor_id=1)

    item_insert = next(sql for sql, _ in fake_conn.cursor_obj.calls if sql.strip().startswith('INSERT INTO inventory_items'))
    lot_insert = next(
        params for sql, params in fake_conn.cursor_obj.calls
        if sql.strip().startswith('INSERT INTO inventory_lots')
    )

    assert result['invoice_id'] == 42
    assert 'INSERT INTO inventory_items' in item_insert
    assert lot_insert[0] == 700
    assert fake_conn.committed is True


def test_xml_import_checks_duplicate_before_drive_upload(monkeypatch):
    from flask import Flask

    import blueprints.admin as admin_module

    app = Flask(__name__)
    app.secret_key = 'test'

    class FakeInspection:
        safe_filename = 'nfe.xml'
        mime_type = 'application/xml'

    uploaded = {'called': False}

    def fake_store(*args, **kwargs):
        uploaded['called'] = True
        return 'gdrive://unexpected'

    def raise_duplicate(access_key):
        raise ValueError('Esta NF-e já foi importada.')

    monkeypatch.setattr(admin_module, 'inspect_uploaded_file', lambda *args, **kwargs: FakeInspection())
    monkeypatch.setattr(admin_module, 'parse_nfe_xml', lambda _data: ({'access_key': _sample_access_key()}, [{'description_raw': 'Item'}]))
    monkeypatch.setattr(admin_module, 'ensure_invoice_access_key_available', raise_duplicate)
    monkeypatch.setattr(admin_module, '_store_invoice_file', fake_store)

    with app.test_request_context(
        '/admin/inventory/invoices/import',
        method='POST',
        data={'file': (BytesIO(b'<xml/>'), 'nfe.xml')},
        content_type='multipart/form-data',
    ):
        with pytest.raises(ValueError, match='já foi importada'):
            admin_module._import_invoice_from_xml()

    assert uploaded['called'] is False


def test_xml_import_checks_invalid_supplier_cnpj_before_drive_upload(monkeypatch):
    from flask import Flask

    import blueprints.admin as admin_module

    app = Flask(__name__)
    app.secret_key = 'test'

    class FakeInspection:
        safe_filename = 'nfe.xml'
        mime_type = 'application/xml'

    uploaded = {'called': False}

    def fake_store(*args, **kwargs):
        uploaded['called'] = True
        return 'gdrive://unexpected'

    monkeypatch.setattr(admin_module, 'inspect_uploaded_file', lambda *args, **kwargs: FakeInspection())
    monkeypatch.setattr(
        admin_module,
        'parse_nfe_xml',
        lambda _data: ({'supplier_cnpj': '11.222.333/0001-00'}, [{'description_raw': 'Item'}]),
    )
    monkeypatch.setattr(admin_module, '_store_invoice_file', fake_store)

    with app.test_request_context(
        '/admin/inventory/invoices/import',
        method='POST',
        data={'file': (BytesIO(b'<xml/>'), 'nfe.xml')},
        content_type='multipart/form-data',
    ):
        with pytest.raises(ValueError, match='CNPJ inválido'):
            admin_module._import_invoice_from_xml()

    assert uploaded['called'] is False


# --- RBAC: as rotas novas reaproveitam as mesmas permissões de hoje ---------

def test_inventory_permissions_unchanged_for_write_and_view_roles():
    # As novas rotas (/inventory/invoices/..., /inventory/suppliers/...) usam
    # exatamente @permission_required('inventory:write'/'inventory:view'),
    # então a matriz de papéis já validada continua valendo para elas.
    for role in (Role.ADMIN, Role.COORDENACAO, Role.CME):
        assert role_has_permission(role, 'inventory:view')
        assert role_has_permission(role, 'inventory:write')

    for role in (Role.CLINICOS, Role.RECEPCAO, Role.RADIOLOGIA, Role.ANALISES_CLINICAS, Role.COMUNICACAO):
        assert not role_has_permission(role, 'inventory:view')
        assert not role_has_permission(role, 'inventory:write')


# --- Regressão do bug do dashboard -------------------------------------------

def test_inventory_dashboard_stats_key_does_not_collide_with_dict_items(monkeypatch):
    def fake_query(sql, params=(), one=False):
        if 'COUNT(*) AS total FROM inventory_invoices' in sql:
            return {'total': 2}
        if 'FROM inventory_items i' in sql:
            return [{'id': 1, 'name': 'Material X'}]
        if 'FROM inventory_lots l' in sql:
            return []
        return []

    monkeypatch.setattr(inventory_service, 'query', fake_query)
    monkeypatch.setattr(inventory_service, 'get_inventory_alerts', lambda limit=30: [])

    dashboard = inventory_service.get_inventory_dashboard()

    assert dashboard['stats']['materials_count'] == 1
    assert dashboard['stats']['pending_invoices'] == 2
    assert 'items' not in dashboard['stats']
