import datetime as dt

import pytest

import services.communication_service as communication_service
from services.communication_service import (
    calculate_age,
    channel_available,
    count_audience,
    create_campaign,
    enqueue_campaign_messages,
    resolve_audience,
    send_single_message,
    set_preferences,
    whatsapp_configured,
)


def test_whatsapp_configured_false_without_env(monkeypatch):
    monkeypatch.delenv('WHATSAPP_ACCESS_TOKEN', raising=False)
    monkeypatch.delenv('WHATSAPP_PHONE_NUMBER_ID', raising=False)
    assert whatsapp_configured() is False
    assert channel_available('whatsapp') is False
    assert channel_available('email') is True


def test_whatsapp_configured_true_with_env(monkeypatch):
    monkeypatch.setenv('WHATSAPP_ACCESS_TOKEN', 'token')
    monkeypatch.setenv('WHATSAPP_PHONE_NUMBER_ID', '12345')
    assert whatsapp_configured() is True
    assert channel_available('whatsapp') is True


def test_calculate_age_handles_both_date_formats():
    today = dt.date(2026, 6, 24)
    assert calculate_age('2000-06-25', reference_date=today) == 25
    assert calculate_age('25/06/2000', reference_date=today) == 25
    assert calculate_age('2000-06-23', reference_date=today) == 26
    assert calculate_age(None) is None
    assert calculate_age('lixo') is None


def test_resolve_audience_filters_by_municipio_and_opt_in(monkeypatch):
    rows = [
        {'patient_id': 1, 'nome': 'Ana', 'email': 'ana@x.com', 'celular': None,
         'data_nascimento': '1990-01-01', 'genero': 'Feminino',
         'endereco_cidade': 'Maceió', 'endereco_bairro': 'Centro'},
    ]
    captured = {}

    def fake_query(sql, params=()):
        captured['sql'] = sql
        captured['params'] = params
        return rows

    monkeypatch.setattr(communication_service, 'query', fake_query)

    result = resolve_audience({'municipios': ['Maceió']}, 'email')

    assert result == rows
    assert 'p.endereco_cidade = ANY(%s)' in captured['sql']
    assert captured['params'][0] == ['Maceió']


def test_resolve_audience_filters_by_age_in_python(monkeypatch):
    rows = [
        {'patient_id': 1, 'nome': 'Jovem', 'email': 'a@x.com', 'celular': None,
         'data_nascimento': '2015-01-01', 'genero': None,
         'endereco_cidade': None, 'endereco_bairro': None},
        {'patient_id': 2, 'nome': 'Adulto', 'email': 'b@x.com', 'celular': None,
         'data_nascimento': '1980-01-01', 'genero': None,
         'endereco_cidade': None, 'endereco_bairro': None},
    ]
    monkeypatch.setattr(communication_service, 'query', lambda sql, params=(): rows)

    result = resolve_audience({'idade_min': 18}, 'email')

    assert [row['patient_id'] for row in result] == [2]


def test_count_audience_returns_length(monkeypatch):
    monkeypatch.setattr(
        communication_service, 'query',
        lambda sql, params=(): [{'patient_id': 1, 'data_nascimento': None}] * 3,
    )
    assert count_audience({}, 'email') == 3


def test_create_campaign_rejects_whatsapp_when_not_configured(monkeypatch):
    monkeypatch.delenv('WHATSAPP_ACCESS_TOKEN', raising=False)
    monkeypatch.delenv('WHATSAPP_PHONE_NUMBER_ID', raising=False)

    with pytest.raises(ValueError, match='WhatsApp'):
        create_campaign(
            name='Campanha', channel='whatsapp', template_id=1,
            audience_filter={}, created_by=1,
        )


def test_create_campaign_inserts_with_rascunho_status(monkeypatch):
    captured = {}

    def fake_execute(sql, params=()):
        captured['sql'] = sql
        captured['params'] = params
        return 99

    monkeypatch.setattr(communication_service, 'execute', fake_execute)

    campaign_id = create_campaign(
        name='Campanha Teste', channel='email', template_id=5,
        audience_filter={'municipios': ['Maceió']}, created_by=3,
    )

    assert campaign_id == 99
    assert captured['params'][4] == 'rascunho'


def test_enqueue_campaign_messages_skips_existing_recipients(monkeypatch):
    campaign = {
        'id': 1, 'channel': 'email', 'template_id': 7,
        'audience_filter': {},
    }
    monkeypatch.setattr(communication_service, 'get_campaign', lambda cid: campaign)

    def fake_query(sql, params=()):
        if 'communication_messages WHERE campaign_id' in sql:
            return [{'patient_id': 1}]
        return []

    monkeypatch.setattr(communication_service, 'query', fake_query)
    monkeypatch.setattr(
        communication_service, 'resolve_audience',
        lambda audience_filter, channel: [
            {'patient_id': 1, 'email': 'a@x.com', 'celular': None},
            {'patient_id': 2, 'email': 'b@x.com', 'celular': None},
        ],
    )

    executed = []
    monkeypatch.setattr(
        communication_service, 'execute',
        lambda sql, params=(): (executed.append((sql, params)), 555)[1],
    )
    monkeypatch.setattr(communication_service, 'audit_log', lambda **kwargs: None)

    message_ids = enqueue_campaign_messages(1)

    assert message_ids == [555]
    insert_calls = [c for c in executed if 'INSERT INTO communication_messages' in c[0]]
    assert len(insert_calls) == 1
    assert insert_calls[0][1][1] == 2  # patient_id do único pendente


def test_send_single_message_email_marks_sent(monkeypatch):
    message = {
        'id': 10, 'channel': 'email', 'destination': 'a@x.com',
        'template_id': 1, 'patient_id': 2, 'campaign_id': None,
    }
    template = {'subject': 'Olá {{nome}}', 'body': 'Mensagem para {{nome}}'}
    patient = {'nome': 'Maria'}

    def fake_query(sql, params=(), one=False):
        if 'communication_messages WHERE id' in sql:
            return message
        if 'communication_templates' in sql:
            return template
        if 'patients' in sql:
            return patient
        return None

    sent = {}
    monkeypatch.setattr(communication_service, 'query', fake_query)
    monkeypatch.setattr(
        communication_service, 'send_email',
        lambda subject, to, body: sent.update(subject=subject, to=to, body=body),
    )

    executed = []
    monkeypatch.setattr(
        communication_service, 'execute',
        lambda sql, params=(): executed.append((sql, params)),
    )

    assert send_single_message(10) is True
    assert sent['to'] == 'a@x.com'
    assert sent['subject'] == 'Olá Maria'
    assert "status = 'enviado'" in executed[-1][0]


def test_send_single_message_marks_failed_on_error(monkeypatch):
    message = {
        'id': 10, 'channel': 'email', 'destination': 'a@x.com',
        'template_id': 1, 'patient_id': 2, 'campaign_id': None,
    }

    template = {'subject': 'Olá {{nome}}', 'body': 'Mensagem'}

    def fake_query(sql, params=(), one=False):
        if 'communication_messages WHERE id' in sql:
            return message
        if 'communication_templates' in sql:
            return template
        return None

    def fail_send_email(*args, **kwargs):
        raise RuntimeError('SMTP indisponível')

    executed = []
    monkeypatch.setattr(communication_service, 'query', fake_query)
    monkeypatch.setattr(communication_service, 'send_email', fail_send_email)
    monkeypatch.setattr(
        communication_service, 'execute',
        lambda sql, params=(): executed.append((sql, params)),
    )

    with pytest.raises(RuntimeError):
        send_single_message(10)

    assert "status = 'falhou'" in executed[-1][0]
    assert 'SMTP indisponível' in executed[-1][1][0]


def test_set_preferences_inserts_when_missing(monkeypatch):
    monkeypatch.setattr(communication_service, 'get_preferences', lambda pid: None)
    captured = {}
    monkeypatch.setattr(
        communication_service, 'execute',
        lambda sql, params=(): captured.update(sql=sql, params=params),
    )

    set_preferences(7, whatsapp_opt_in=True, source='paciente_respondeu')

    assert 'INSERT INTO communication_preferences' in captured['sql']
    assert captured['params'] == (7, True, True, False, 'paciente_respondeu')
