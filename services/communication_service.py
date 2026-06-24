import datetime as dt
import json
import os

import requests

from database import execute, query
from services.mail_service import send_email
from services.security_service import audit_log


WHATSAPP_GRAPH_VERSION = 'v20.0'


def whatsapp_configured():
    return bool(os.getenv('WHATSAPP_ACCESS_TOKEN') and os.getenv('WHATSAPP_PHONE_NUMBER_ID'))


def channel_available(channel):
    if channel == 'whatsapp':
        return whatsapp_configured()
    return channel == 'email'


def _parse_birthdate(value):
    if not value:
        return None
    value = str(value).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return dt.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def calculate_age(data_nascimento, reference_date=None):
    birth = _parse_birthdate(data_nascimento)
    if not birth:
        return None
    reference_date = reference_date or dt.date.today()
    years = reference_date.year - birth.year
    if (reference_date.month, reference_date.day) < (birth.month, birth.day):
        years -= 1
    return years


# ── Templates ────────────────────────────────────────────────────────────────

def list_templates(channel=None, active_only=False):
    conditions = []
    params = []
    if channel:
        conditions.append('channel = %s')
        params.append(channel)
    if active_only:
        conditions.append('active = TRUE')
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ''
    return query(
        f"SELECT * FROM communication_templates {where} ORDER BY created_at DESC",
        tuple(params),
    ) or []


def get_template(template_id):
    return query(
        'SELECT * FROM communication_templates WHERE id = %s',
        (template_id,),
        one=True,
    )


def create_template(*, channel, category, name, subject, body,
                     whatsapp_template_name, whatsapp_template_lang, created_by):
    return execute(
        """
        INSERT INTO communication_templates (
            channel, category, name, subject, body,
            whatsapp_template_name, whatsapp_template_lang, created_by
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (channel, category, name, subject, body,
         whatsapp_template_name, whatsapp_template_lang, created_by),
    )


def update_template(template_id, *, name, subject, body,
                     whatsapp_template_name, whatsapp_template_lang, active):
    execute(
        """
        UPDATE communication_templates
        SET name = %s, subject = %s, body = %s,
            whatsapp_template_name = %s, whatsapp_template_lang = %s, active = %s
        WHERE id = %s
        """,
        (name, subject, body, whatsapp_template_name, whatsapp_template_lang,
         active, template_id),
    )


def render_template_text(text, variables):
    rendered = text or ''
    for key, value in (variables or {}).items():
        rendered = rendered.replace('{{' + key + '}}', str(value or ''))
    return rendered


# ── Público (segmentação) ───────────────────────────────────────────────────

def list_municipios():
    return query("SELECT id, nome FROM municipios WHERE ativo = 1 ORDER BY nome ASC") or []


def list_bairros():
    rows = query(
        """
        SELECT DISTINCT endereco_bairro FROM patients
        WHERE endereco_bairro IS NOT NULL AND endereco_bairro != ''
        ORDER BY endereco_bairro ASC
        """
    ) or []
    return [row['endereco_bairro'] for row in rows]


def _audience_base_query(audience_filter, channel):
    conditions = []
    params = []

    municipios = [m for m in (audience_filter.get('municipios') or []) if m]
    if municipios:
        conditions.append('p.endereco_cidade = ANY(%s)')
        params.append(municipios)

    bairros = [b for b in (audience_filter.get('bairros') or []) if b]
    if bairros:
        conditions.append('p.endereco_bairro = ANY(%s)')
        params.append(bairros)

    generos = [g for g in (audience_filter.get('generos') or []) if g]
    if generos:
        conditions.append('p.genero = ANY(%s)')
        params.append(generos)

    destination_column = 'p.email' if channel == 'email' else 'p.celular'
    conditions.append(f"{destination_column} IS NOT NULL AND {destination_column} != ''")

    if channel == 'whatsapp':
        conditions.append('COALESCE(cp.whatsapp_opt_in, FALSE) = TRUE')
    else:
        conditions.append('COALESCE(cp.email_opt_in, TRUE) = TRUE')

    if audience_filter.get('somente_marketing'):
        conditions.append('COALESCE(cp.marketing_opt_in, FALSE) = TRUE')

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ''
    sql = f"""
        SELECT p.id AS patient_id, p.nome, p.email, p.celular, p.data_nascimento,
               p.genero, p.endereco_cidade, p.endereco_bairro
        FROM patients p
        LEFT JOIN communication_preferences cp ON cp.patient_id = p.id
        {where}
        ORDER BY p.nome ASC
    """
    return sql, params


def resolve_audience(audience_filter, channel):
    audience_filter = audience_filter or {}
    sql, params = _audience_base_query(audience_filter, channel)
    rows = query(sql, tuple(params)) or []

    idade_min = audience_filter.get('idade_min')
    idade_max = audience_filter.get('idade_max')
    if idade_min in ('', None) and idade_max in ('', None):
        return rows

    filtered = []
    for row in rows:
        age = calculate_age(row.get('data_nascimento'))
        if age is None:
            continue
        if idade_min not in ('', None) and age < int(idade_min):
            continue
        if idade_max not in ('', None) and age > int(idade_max):
            continue
        filtered.append(row)
    return filtered


def count_audience(audience_filter, channel):
    return len(resolve_audience(audience_filter, channel))


# ── Campanhas ────────────────────────────────────────────────────────────────

def create_campaign(*, name, channel, template_id, audience_filter, created_by,
                     scheduled_at=None):
    if not channel_available(channel):
        raise ValueError('Canal WhatsApp não está configurado nesta instância.')
    status = 'agendada' if scheduled_at else 'rascunho'
    return execute(
        """
        INSERT INTO communication_campaigns (
            name, channel, template_id, audience_filter, status, scheduled_at, created_by
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (name, channel, template_id, json.dumps(audience_filter or {}), status,
         scheduled_at, created_by),
    )


def list_campaigns():
    return query(
        """
        SELECT c.*, t.name AS template_name, u.full_name AS created_by_name
        FROM communication_campaigns c
        LEFT JOIN communication_templates t ON t.id = c.template_id
        LEFT JOIN users u ON u.id = c.created_by
        ORDER BY c.created_at DESC
        """
    ) or []


def get_campaign(campaign_id):
    return query(
        'SELECT * FROM communication_campaigns WHERE id = %s',
        (campaign_id,),
        one=True,
    )


def list_campaign_messages(campaign_id):
    return query(
        """
        SELECT m.*, p.nome AS patient_name
        FROM communication_messages m
        LEFT JOIN patients p ON p.id = m.patient_id
        WHERE m.campaign_id = %s
        ORDER BY m.id ASC
        """,
        (campaign_id,),
    ) or []


def enqueue_campaign_messages(campaign_id):
    """Resolve a audiência da campanha e grava as linhas de fila (idempotente)."""
    campaign = get_campaign(campaign_id)
    if not campaign:
        return []

    already = query(
        'SELECT patient_id FROM communication_messages WHERE campaign_id = %s',
        (campaign_id,),
    ) or []
    already_ids = {row['patient_id'] for row in already}

    audience_filter = campaign['audience_filter'] or {}
    recipients = resolve_audience(audience_filter, campaign['channel'])

    message_ids = []
    for recipient in recipients:
        if recipient['patient_id'] in already_ids:
            continue
        destination = (
            recipient['email'] if campaign['channel'] == 'email' else recipient['celular']
        )
        message_id = execute(
            """
            INSERT INTO communication_messages (
                campaign_id, patient_id, channel, destination, template_id, status
            )
            VALUES (%s, %s, %s, %s, %s, 'fila')
            RETURNING id
            """,
            (campaign_id, recipient['patient_id'], campaign['channel'], destination,
             campaign['template_id']),
        )
        message_ids.append(message_id)

    execute(
        "UPDATE communication_campaigns SET total_recipients = %s, status = 'enviando' WHERE id = %s",
        (len(recipients), campaign_id),
    )
    audit_log(
        action='communication_campaign_enqueued',
        module='comunicacao',
        entity_type='communication_campaigns',
        entity_id=campaign_id,
        details={'total_recipients': len(recipients), 'channel': campaign['channel']},
    )
    return message_ids


# ── Envio (canais) ───────────────────────────────────────────────────────────

def _send_email_message(message, template, patient):
    variables = {'nome': patient.get('nome') if patient else ''}
    subject = render_template_text(template['subject'], variables)
    body = render_template_text(template['body'], variables)
    send_email(subject, message['destination'], body)


def _send_whatsapp_message(message, template, patient):
    if not whatsapp_configured():
        raise RuntimeError('Canal WhatsApp não configurado (variáveis de ambiente ausentes).')

    phone_number_id = os.getenv('WHATSAPP_PHONE_NUMBER_ID')
    access_token = os.getenv('WHATSAPP_ACCESS_TOKEN')
    url = f'https://graph.facebook.com/{WHATSAPP_GRAPH_VERSION}/{phone_number_id}/messages'

    payload = {
        'messaging_product': 'whatsapp',
        'to': message['destination'],
        'type': 'template',
        'template': {
            'name': template['whatsapp_template_name'],
            'language': {'code': template.get('whatsapp_template_lang') or 'pt_BR'},
            'components': [{
                'type': 'body',
                'parameters': [
                    {'type': 'text', 'text': (patient.get('nome') if patient else '') or ''},
                ],
            }],
        },
    }
    response = requests.post(
        url,
        headers={'Authorization': f'Bearer {access_token}'},
        json=payload,
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def send_single_message(message_id):
    """Envia uma mensagem da fila pelo canal correto e atualiza o status."""
    message = query(
        'SELECT * FROM communication_messages WHERE id = %s',
        (message_id,),
        one=True,
    )
    if not message:
        return None

    template = get_template(message['template_id']) if message['template_id'] else None
    patient = query(
        'SELECT nome FROM patients WHERE id = %s',
        (message['patient_id'],),
        one=True,
    ) if message['patient_id'] else None

    try:
        if message['channel'] == 'email':
            _send_email_message(message, template, patient)
        else:
            result = _send_whatsapp_message(message, template, patient)
            provider_message_id = None
            if isinstance(result, dict):
                messages = result.get('messages') or []
                if messages:
                    provider_message_id = messages[0].get('id')
            execute(
                "UPDATE communication_messages SET provider_message_id = %s WHERE id = %s",
                (provider_message_id, message_id),
            )
        execute(
            "UPDATE communication_messages SET status = 'enviado', sent_at = NOW() WHERE id = %s",
            (message_id,),
        )
        if message['campaign_id']:
            execute(
                "UPDATE communication_campaigns SET total_sent = total_sent + 1 WHERE id = %s",
                (message['campaign_id'],),
            )
        return True
    except Exception as exc:
        execute(
            """
            UPDATE communication_messages
            SET status = 'falhou', error_message = %s, failed_at = NOW()
            WHERE id = %s
            """,
            (str(exc), message_id),
        )
        if message['campaign_id']:
            execute(
                "UPDATE communication_campaigns SET total_failed = total_failed + 1 WHERE id = %s",
                (message['campaign_id'],),
            )
        raise


# ── Preferências / opt-out ──────────────────────────────────────────────────

def get_preferences(patient_id):
    return query(
        'SELECT * FROM communication_preferences WHERE patient_id = %s',
        (patient_id,),
        one=True,
    )


def set_preferences(patient_id, *, email_opt_in=None, whatsapp_opt_in=None,
                     marketing_opt_in=None, source='admin'):
    existing = get_preferences(patient_id)
    if existing is None:
        execute(
            """
            INSERT INTO communication_preferences (
                patient_id, email_opt_in, whatsapp_opt_in, marketing_opt_in, source
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                patient_id,
                email_opt_in if email_opt_in is not None else True,
                whatsapp_opt_in if whatsapp_opt_in is not None else False,
                marketing_opt_in if marketing_opt_in is not None else False,
                source,
            ),
        )
        return

    execute(
        """
        UPDATE communication_preferences
        SET email_opt_in = COALESCE(%s, email_opt_in),
            whatsapp_opt_in = COALESCE(%s, whatsapp_opt_in),
            marketing_opt_in = COALESCE(%s, marketing_opt_in),
            source = %s,
            updated_at = NOW()
        WHERE patient_id = %s
        """,
        (email_opt_in, whatsapp_opt_in, marketing_opt_in, source, patient_id),
    )


def opt_out_whatsapp_by_phone(phone):
    rows = query('SELECT id FROM patients WHERE celular = %s', (phone,)) or []
    for row in rows:
        set_preferences(row['id'], whatsapp_opt_in=False, source='paciente_respondeu')


def list_opt_outs():
    return query(
        """
        SELECT cp.*, p.nome
        FROM communication_preferences cp
        JOIN patients p ON p.id = cp.patient_id
        WHERE cp.email_opt_in = FALSE OR cp.whatsapp_opt_in = FALSE
        ORDER BY cp.updated_at DESC
        """
    ) or []


# ── Lembretes automáticos de consulta ───────────────────────────────────────

def find_consultas_pending_reminder(channel, hours_ahead=48):
    destination_column = 'p.email' if channel == 'email' else 'p.celular'
    opt_in_clause = (
        'COALESCE(cp.whatsapp_opt_in, FALSE) = TRUE'
        if channel == 'whatsapp'
        else 'COALESCE(cp.email_opt_in, TRUE) = TRUE'
    )
    return query(
        f"""
        SELECT c.id AS consulta_id, c.patient_id, c.data_consulta,
               p.nome, p.email, p.celular
        FROM consultas c
        JOIN patients p ON p.id = c.patient_id
        LEFT JOIN communication_preferences cp ON cp.patient_id = p.id
        WHERE c.status IN ('Pendente', 'Confirmado')
          AND c.data_consulta BETWEEN NOW() AND NOW() + (%s * INTERVAL '1 hour')
          AND {destination_column} IS NOT NULL AND {destination_column} != ''
          AND {opt_in_clause}
          AND NOT EXISTS (
              SELECT 1 FROM communication_messages m
              WHERE m.consulta_id = c.id AND m.channel = %s
          )
        """,
        (hours_ahead, channel),
    ) or []


def enqueue_appointment_reminder(consulta, channel, template_id):
    destination = consulta['email'] if channel == 'email' else consulta['celular']
    return execute(
        """
        INSERT INTO communication_messages (
            consulta_id, patient_id, channel, destination, template_id, status
        )
        VALUES (%s, %s, %s, %s, %s, 'fila')
        RETURNING id
        """,
        (consulta['consulta_id'], consulta['patient_id'], channel, destination, template_id),
    )
