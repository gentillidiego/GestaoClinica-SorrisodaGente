"""Leitura do XML da NF-e (modelo 55) para alimentar a conciliação de estoque.

Lê apenas os campos necessários para rastreabilidade fiscal (fornecedor,
número/série, chave de acesso, itens com NCM/CFOP/EAN e valores). Não calcula
nem valida impostos, e não consulta a SEFAZ — o XML enviado pelo usuário é a
única fonte.
"""
from lxml import etree


NFE_NAMESPACE = 'http://www.portalfiscal.inf.fazenda.gov.br/nfe'
_NS = {'nfe': NFE_NAMESPACE}


class NFeParsingError(ValueError):
    """Erro seguro para exibição ao usuário quando o XML não é uma NF-e válida."""


def _text(node, path):
    if node is None:
        return None
    found = node.find(path, _NS)
    if found is None or found.text is None:
        return None
    return found.text.strip() or None


def calc_access_key_check_digit(digits43):
    """Dígito verificador (mod 11) dos 43 primeiros dígitos da chave de acesso."""
    weights = [2, 3, 4, 5, 6, 7, 8, 9]
    total = sum(int(ch) * weights[i % 8] for i, ch in enumerate(reversed(digits43)))
    remainder = total % 11
    return '0' if remainder < 2 else str(11 - remainder)


def validate_access_key_checksum(digits44):
    if not digits44 or len(digits44) != 44 or not digits44.isdigit():
        return False
    return digits44[43] == calc_access_key_check_digit(digits44[:43])


def decode_access_key(digits44):
    """Extrai cUF, ano/mês, CNPJ, série e número da NF diretamente da chave
    de acesso (estrutura fixa definida pela SEFAZ), sem depender do layout
    visual do DANFE."""
    if not digits44 or len(digits44) != 44 or not digits44.isdigit():
        return {}
    return {
        'supplier_cnpj': digits44[6:20],
        'invoice_series': str(int(digits44[22:25])),
        'invoice_number': str(int(digits44[25:34])),
        'issue_year_month': digits44[2:6],
    }


def _clean_ean(value):
    if not value or value.strip().upper() in {'SEM GTIN', 'SEMGTIN'}:
        return None
    return value


def _parse_access_key(inf_nfe):
    raw_id = inf_nfe.get('Id') or ''
    digits = ''.join(ch for ch in raw_id if ch.isdigit())
    return digits or None


def parse_nfe_xml(xml_bytes):
    """Retorna (header, rows) a partir dos bytes do XML da NF-e.

    header: dict com supplier_name, supplier_cnpj, invoice_number,
    invoice_series, issue_date, total_value, access_key.
    rows: lista de dicts com description_raw, ncm, cfop, ean, unit,
    quantity, unit_value, total_value.
    """
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
    try:
        root = etree.fromstring(xml_bytes, parser=parser)
    except etree.XMLSyntaxError as exc:
        raise NFeParsingError('O arquivo não é um XML bem formado.') from exc

    inf_nfe = root.find('.//nfe:infNFe', _NS)
    if inf_nfe is None:
        # Alguns ERPs exportam o XML sem o namespace declarado no elemento raiz.
        inf_nfe = root.find('.//infNFe')
        if inf_nfe is None:
            raise NFeParsingError(
                'O arquivo não contém a estrutura esperada de uma NF-e (infNFe não encontrado).'
            )

    ide = inf_nfe.find('nfe:ide', _NS)
    emit = inf_nfe.find('nfe:emit', _NS)
    total = inf_nfe.find('nfe:total/nfe:ICMSTot', _NS)

    issue_date = _text(ide, 'nfe:dhEmi') or _text(ide, 'nfe:dEmi')
    if issue_date:
        issue_date = issue_date[:10]

    header = {
        'access_key': _parse_access_key(inf_nfe),
        'invoice_number': _text(ide, 'nfe:nNF'),
        'invoice_series': _text(ide, 'nfe:serie'),
        'issue_date': issue_date,
        'supplier_name': _text(emit, 'nfe:xNome'),
        'supplier_cnpj': _text(emit, 'nfe:CNPJ') or _text(emit, 'nfe:CPF'),
        'total_value': _text(total, 'nfe:vNF') if total is not None else None,
    }

    rows = []
    for det in inf_nfe.findall('nfe:det', _NS):
        prod = det.find('nfe:prod', _NS)
        if prod is None:
            continue
        rows.append({
            'description_raw': _text(prod, 'nfe:xProd'),
            'ncm': _text(prod, 'nfe:NCM'),
            'cfop': _text(prod, 'nfe:CFOP'),
            'ean': _clean_ean(_text(prod, 'nfe:cEAN')) or _clean_ean(_text(prod, 'nfe:cEANTrib')),
            'unit': _text(prod, 'nfe:uCom'),
            'quantity': _text(prod, 'nfe:qCom'),
            'unit_value': _text(prod, 'nfe:vUnCom'),
            'total_value': _text(prod, 'nfe:vProd'),
        })

    if not rows:
        raise NFeParsingError('A NF-e não possui itens (det/prod) para importar.')

    return header, rows
