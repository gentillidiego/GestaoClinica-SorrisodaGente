"""Extração de melhor esforço de dados fiscais a partir do PDF do DANFE.

O DANFE é só a representação visual da NF-e — não existe um schema fixo de
posição/coluna garantido entre os diferentes emissores/ERPs. Por isso, esta
extração:

- é sempre best-effort: nunca é tratada como confirmada;
- prioriza a chave de acesso (44 dígitos, com dígito verificador), porque a
  partir dela é possível decodificar CNPJ do emitente, série e número da NF
  de forma determinística, sem depender do layout da página;
- tenta extrair a tabela de itens quando o PDF tem uma tabela reconhecível;
  quando não consegue, devolve a lista de itens vazia e quem importou
  completa manualmente na tela de revisão.
"""
import re

import pdfplumber

from services.nfe_xml_service import decode_access_key, validate_access_key_checksum


_ACCESS_KEY_RE = re.compile(r'(?:\d[\s.]?){44}')
_CNPJ_RE = re.compile(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}')
_DATE_RE = re.compile(r'\b(\d{2}/\d{2}/\d{4})\b')
_MONEY_RE = re.compile(r'\d{1,3}(?:\.\d{3})*,\d{2}')

_ITEM_HEADER_KEYWORDS = ('descricao', 'descrição', 'produto', 'servico', 'serviço')
_COLUMN_KEYWORDS = {
    'description_raw': ('descricao', 'descrição', 'produto', 'xprod'),
    'ncm': ('ncm',),
    'cfop': ('cfop',),
    'unit': ('unid', 'un.', 'und'),
    'quantity': ('quant', 'qtd'),
    'unit_value': ('vl unit', 'v.unit', 'valor unit', 'vunit'),
    'total_value': ('vl total', 'v.total', 'valor total', 'vtotal', 'vprod'),
}


def _extract_text(pdf):
    parts = []
    for page in pdf.pages:
        text = page.extract_text() or ''
        parts.append(text)
    return '\n'.join(parts)


def _money_to_decimal_text(value):
    if not value:
        return None
    return value.replace('.', '').replace(',', '.')


def _find_access_key(text):
    for match in _ACCESS_KEY_RE.finditer(text):
        digits = re.sub(r'\D', '', match.group(0))
        if len(digits) == 44:
            return digits
    return None


def _find_total_value(text):
    marker = re.search(r'VALOR\s+TOTAL\s+DA\s+NOTA', text, re.IGNORECASE)
    search_text = text[marker.end():marker.end() + 200] if marker else text
    money_match = _MONEY_RE.search(search_text)
    return _money_to_decimal_text(money_match.group(0)) if money_match else None


def _find_issue_date(text):
    marker = re.search(r'EMISS[ÃA]O', text, re.IGNORECASE)
    search_text = text[marker.end():marker.end() + 60] if marker else text
    date_match = _DATE_RE.search(search_text)
    if not date_match:
        date_match = _DATE_RE.search(text)
    if not date_match:
        return None
    day, month, year = date_match.group(1).split('/')
    return f'{year}-{month}-{day}'


def _find_cnpj(text):
    match = _CNPJ_RE.search(text)
    return match.group(0) if match else None


def _normalize_header_cell(value):
    text = (value or '').strip().lower()
    text = (
        text.replace('ç', 'c').replace('ã', 'a').replace('õ', 'o')
        .replace('á', 'a').replace('é', 'e').replace('í', 'i')
        .replace('ó', 'o').replace('ú', 'u')
    )
    return text


def _map_header_columns(header_row):
    mapping = {}
    for index, cell in enumerate(header_row):
        normalized = _normalize_header_cell(cell)
        for field, keywords in _COLUMN_KEYWORDS.items():
            if any(_normalize_header_cell(keyword) in normalized for keyword in keywords):
                mapping[field] = index
                break
    return mapping


def _extract_item_rows(pdf):
    for page in pdf.pages:
        for table in page.extract_tables() or []:
            if not table or len(table) < 2:
                continue
            header_row = table[0]
            header_text = ' '.join(_normalize_header_cell(cell) for cell in header_row if cell)
            if not any(keyword in header_text for keyword in _ITEM_HEADER_KEYWORDS):
                continue
            column_map = _map_header_columns(header_row)
            if 'description_raw' not in column_map:
                continue

            rows = []
            for data_row in table[1:]:
                description = (data_row[column_map['description_raw']] or '').strip() if column_map.get('description_raw') is not None else ''
                if not description:
                    continue
                row = {'description_raw': description}
                for field in ('ncm', 'cfop', 'unit'):
                    index = column_map.get(field)
                    if index is not None and index < len(data_row):
                        row[field] = (data_row[index] or '').strip() or None
                for field in ('quantity', 'unit_value', 'total_value'):
                    index = column_map.get(field)
                    if index is not None and index < len(data_row):
                        row[field] = _money_to_decimal_text((data_row[index] or '').strip())
                rows.append(row)
            if rows:
                return rows
    return []


def parse_danfe_pdf(pdf_bytes):
    """Retorna (header, rows) com melhor esforço a partir do PDF do DANFE.

    Nenhum campo aqui deve ser tratado como definitivo: tudo cai editável na
    tela de revisão. Quando a chave de acesso é encontrada e o dígito
    verificador confere, CNPJ/série/número derivam dela (mais confiável que
    qualquer posição de texto no layout do DANFE).
    """
    import io

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = _extract_text(pdf)
        rows = _extract_item_rows(pdf)

    access_key = _find_access_key(text)
    header = {
        'access_key': access_key if access_key and validate_access_key_checksum(access_key) else None,
        'supplier_cnpj': _find_cnpj(text),
        'invoice_number': None,
        'invoice_series': None,
        'issue_date': _find_issue_date(text),
        'total_value': _find_total_value(text),
    }

    if header['access_key']:
        decoded = decode_access_key(header['access_key'])
        header['supplier_cnpj'] = decoded.get('supplier_cnpj') or header['supplier_cnpj']
        header['invoice_number'] = decoded.get('invoice_number')
        header['invoice_series'] = decoded.get('invoice_series')

    return header, rows

