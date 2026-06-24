from datetime import datetime
from zoneinfo import ZoneInfo


DOCUMENT_TYPE_ATESTADO = 'atestado'
DOCUMENT_TYPE_DECLARACAO = 'declaracao_comparecimento'
DOCUMENT_TYPES = {
    DOCUMENT_TYPE_ATESTADO,
    DOCUMENT_TYPE_DECLARACAO,
}
LOCAL_TIMEZONE = ZoneInfo('America/Maceio')


def normalize_document_type(value):
    normalized = (value or DOCUMENT_TYPE_ATESTADO).strip().lower()
    return normalized if normalized in DOCUMENT_TYPES else None


def local_now():
    return datetime.now(LOCAL_TIMEZONE)


def normalize_time_range(start_time, end_time):
    start_time = (start_time or '').strip() or None
    end_time = (end_time or '').strip() or None
    if bool(start_time) != bool(end_time):
        raise ValueError('Informe os horários de início e término, ou deixe ambos em branco.')
    if start_time and end_time and end_time <= start_time:
        raise ValueError('O horário de término deve ser posterior ao horário de início.')
    return start_time, end_time


def document_type_label(value):
    if value == DOCUMENT_TYPE_DECLARACAO:
        return 'Declaração de Comparecimento'
    return 'Atestado Odontológico'


def format_date_pt(value):
    if not value:
        return ''
    months = (
        'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
        'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro',
    )
    return f'{value.day} de {months[value.month - 1]} de {value.year}'


def format_time(value):
    if not value:
        return ''
    return value.strftime('%H:%M')
