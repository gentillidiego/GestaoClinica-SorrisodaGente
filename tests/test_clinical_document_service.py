import datetime as dt

import pytest

from services.clinical_document_service import (
    DOCUMENT_TYPE_ATESTADO,
    DOCUMENT_TYPE_DECLARACAO,
    document_type_label,
    format_date_pt,
    format_time,
    normalize_document_type,
    normalize_time_range,
)


def test_document_type_normalization_accepts_only_supported_values():
    assert normalize_document_type(None) == DOCUMENT_TYPE_ATESTADO
    assert normalize_document_type('ATESTADO') == DOCUMENT_TYPE_ATESTADO
    assert (
        normalize_document_type('declaracao_comparecimento')
        == DOCUMENT_TYPE_DECLARACAO
    )
    assert normalize_document_type('relatorio') is None


def test_declaration_time_range_requires_complete_chronological_period():
    assert normalize_time_range('', '') == (None, None)
    assert normalize_time_range('08:00', '09:30') == ('08:00', '09:30')

    with pytest.raises(ValueError, match='início e término'):
        normalize_time_range('08:00', '')
    with pytest.raises(ValueError, match='posterior'):
        normalize_time_range('10:00', '09:00')


def test_clinical_document_labels_and_formatting():
    assert document_type_label(DOCUMENT_TYPE_ATESTADO) == 'Atestado Odontológico'
    assert (
        document_type_label(DOCUMENT_TYPE_DECLARACAO)
        == 'Declaração de Comparecimento'
    )
    assert format_date_pt(dt.date(2026, 6, 23)) == '23 de junho de 2026'
    assert format_time(dt.time(8, 5)) == '08:05'
