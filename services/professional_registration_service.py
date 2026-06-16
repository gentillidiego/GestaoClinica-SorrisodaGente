import json
import os
import re
import secrets
from datetime import date
from html import escape

from constants import Role, get_role_label
from database import execute, execute_returning, query
from services.mail_service import send_email
from werkzeug.security import generate_password_hash


PUBLIC_REGISTRATION_ROLES = (
    Role.CLINICOS,
    Role.RECEPCAO,
    Role.CME,
    Role.RADIOLOGIA,
    Role.COMUNICACAO,
    Role.COORDENACAO,
    Role.SSA_SMS,
    Role.AUDITORIA,
)

PROFESSIONAL_DOCUMENT_ROLES = {
    Role.CLINICOS,
    Role.CME,
    Role.RADIOLOGIA,
}

DENTAL_LICENSE_ROLES = {
    Role.CLINICOS,
}

COMMON_REQUIRED_FIELDS = {
    'full_name': 'Nome completo',
    'cpf': 'CPF',
    'data_nascimento': 'Data de nascimento',
    'email': 'E-mail',
    'celular': 'Celular/WhatsApp',
    'desired_username': 'Login desejado',
    'requested_role': 'Classe pretendida',
}


class RegistrationApprovalError(Exception):
    pass


def get_public_registration_role_choices():
    return [(role, get_role_label(role)) for role in PUBLIC_REGISTRATION_ROLES]


def role_requires_professional_documents(role):
    return role in PROFESSIONAL_DOCUMENT_ROLES


def role_requires_dental_license(role):
    return role in DENTAL_LICENSE_ROLES


def _clean(value):
    return (value or '').strip()


def only_digits(value):
    return re.sub(r'\D', '', value or '')


def is_valid_birthdate(value):
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError):
        return False
    return parsed <= date.today()


def is_valid_cpf(value):
    cpf = only_digits(value)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False

    first_sum = sum(int(cpf[i]) * (10 - i) for i in range(9))
    first_digit = 11 - (first_sum % 11)
    first_digit = 0 if first_digit >= 10 else first_digit
    if first_digit != int(cpf[9]):
        return False

    second_sum = sum(int(cpf[i]) * (11 - i) for i in range(10))
    second_digit = 11 - (second_sum % 11)
    second_digit = 0 if second_digit >= 10 else second_digit
    return second_digit == int(cpf[10])


def build_registration_payload(form):
    requested_role = _clean(form.get('requested_role'))
    return {
        'full_name': _clean(form.get('full_name')),
        'cpf': _clean(form.get('cpf')),
        'data_nascimento': _clean(form.get('data_nascimento')),
        'email': _clean(form.get('email')).lower(),
        'celular': _clean(form.get('celular')),
        'desired_username': _clean(form.get('desired_username')).lower(),
        'requested_role': requested_role,
        'cns': _clean(form.get('cns')),
        'cbo': _clean(form.get('cbo')),
        'cro': _clean(form.get('cro')),
        'cro_uf': _clean(form.get('cro_uf')).upper(),
        'notes': _clean(form.get('notes')),
        'truth_accepted': form.get('truth_accepted') == '1',
        'lgpd_accepted': form.get('lgpd_accepted') == '1',
    }


def validate_registration_payload(payload):
    errors = []

    for field, label in COMMON_REQUIRED_FIELDS.items():
        if not payload.get(field):
            errors.append(f'{label} é obrigatório.')

    if payload.get('requested_role') and payload['requested_role'] not in PUBLIC_REGISTRATION_ROLES:
        errors.append('Classe pretendida inválida.')

    if payload.get('cpf') and not is_valid_cpf(payload['cpf']):
        errors.append('CPF inválido.')

    if payload.get('data_nascimento') and not is_valid_birthdate(payload['data_nascimento']):
        errors.append('Data de nascimento inválida.')

    if payload.get('email') and '@' not in payload['email']:
        errors.append('E-mail inválido.')

    username = payload.get('desired_username')
    if username and not re.match(r'^[a-z0-9._-]{3,50}$', username):
        errors.append('Login desejado deve ter 3 a 50 caracteres e usar apenas letras, números, ponto, hífen ou sublinhado.')

    role = payload.get('requested_role')
    if role_requires_professional_documents(role):
        for field, label in (('cns', 'CNS do profissional'), ('cbo', 'CBO')):
            if not payload.get(field):
                errors.append(f'{label} é obrigatório para esta classe.')

    if role_requires_dental_license(role):
        for field, label in (('cro', 'CRO'), ('cro_uf', 'CRO-UF')):
            if not payload.get(field):
                errors.append(f'{label} é obrigatório para Clínicos.')

    if not payload.get('truth_accepted'):
        errors.append('Confirme a veracidade das informações.')

    if not payload.get('lgpd_accepted'):
        errors.append('Autorize o tratamento dos dados para o pré-cadastro.')

    return errors


def create_registration_request(payload, source_ip=None, user_agent=None):
    submitted_payload = dict(payload)
    submitted_payload['role_label'] = get_role_label(payload.get('requested_role'))

    return execute_returning(
        """
        INSERT INTO professional_registration_requests (
            full_name, cpf, data_nascimento, email, celular, desired_username, requested_role,
            cns, cbo, cro, cro_uf, notes, truth_accepted, lgpd_accepted,
            source_ip, user_agent, submitted_payload
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        """,
        (
            payload['full_name'],
            payload['cpf'],
            payload['data_nascimento'],
            payload['email'],
            payload['celular'],
            payload['desired_username'],
            payload['requested_role'],
            payload.get('cns'),
            payload.get('cbo'),
            payload.get('cro'),
            payload.get('cro_uf'),
            payload.get('notes'),
            payload.get('truth_accepted'),
            payload.get('lgpd_accepted'),
            source_ip,
            user_agent,
            json.dumps(submitted_payload, ensure_ascii=False),
        ),
    )


def list_registration_requests(limit=200):
    rows = query(
        """
        SELECT *
        FROM professional_registration_requests
        ORDER BY created_at DESC, id DESC
        LIMIT %s
        """,
        (limit,),
    )
    for row in rows:
        row['requested_role_label'] = get_role_label(row.get('requested_role'))
    return rows


def get_registration_request(registration_id):
    row = query(
        """
        SELECT *
        FROM professional_registration_requests
        WHERE id = %s
        """,
        (registration_id,),
        one=True,
    )
    if row:
        row['requested_role_label'] = get_role_label(row.get('requested_role'))
    return row


def approve_registration_request(registration_id, reviewer_id):
    registration = get_registration_request(registration_id)
    if not registration:
        raise RegistrationApprovalError('Pre-cadastro nao encontrado.')
    if registration.get('status') != 'pending':
        raise RegistrationApprovalError('Este pre-cadastro ja foi revisado.')

    existing_user = query(
        "SELECT id FROM users WHERE username = %s",
        (registration['desired_username'],),
        one=True,
    )
    if existing_user:
        raise RegistrationApprovalError('Ja existe usuario com o login escolhido.')

    random_password = generate_password_hash(secrets.token_urlsafe(32))
    user_id = execute_returning(
        """
        INSERT INTO users (
            username, password, role, full_name, email, celular, data_nascimento,
            is_first_access, cro, cro_uf, cns, cbo, cnes, ine, active
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, %s, %s, %s, %s, NULL, NULL, TRUE)
        """,
        (
            registration['desired_username'],
            random_password,
            registration['requested_role'],
            registration['full_name'],
            registration['email'],
            registration['celular'],
            registration['data_nascimento'],
            registration.get('cro'),
            registration.get('cro_uf'),
            registration.get('cns'),
            registration.get('cbo'),
        ),
    )
    execute(
        """
        UPDATE professional_registration_requests
        SET status = 'approved',
            reviewed_by = %s,
            reviewed_at = NOW(),
            created_user_id = %s,
            updated_at = NOW()
        WHERE id = %s
        """,
        (reviewer_id, user_id, registration_id),
    )
    registration['created_user_id'] = user_id
    registration['status'] = 'approved'
    return registration


def reject_registration_request(registration_id, reviewer_id, review_notes=None):
    registration = get_registration_request(registration_id)
    if not registration:
        raise RegistrationApprovalError('Pre-cadastro nao encontrado.')
    if registration.get('status') != 'pending':
        raise RegistrationApprovalError('Este pre-cadastro ja foi revisado.')

    execute(
        """
        UPDATE professional_registration_requests
        SET status = 'rejected',
            review_notes = %s,
            reviewed_by = %s,
            reviewed_at = NOW(),
            updated_at = NOW()
        WHERE id = %s
        """,
        ((review_notes or '').strip(), reviewer_id, registration_id),
    )
    registration['status'] = 'rejected'
    registration['review_notes'] = (review_notes or '').strip()
    return registration


def _app_base_url():
    return (os.getenv('APP_BASE_URL') or 'https://sorrisodagentealagoas.com').rstrip('/')


def _professional_email_shell(title, intro, body_html, action_url=None, action_label=None):
    base_url = _app_base_url()
    logo_url = f'{base_url}/static/logo_sorriso_horizontal.png'
    action_html = ''
    if action_url and action_label:
        action_html = f"""
                <div style="padding:26px 0 18px; text-align:center;">
                  <a href="{escape(action_url)}" style="display:inline-block; background:#0d47a1; color:#ffffff; text-decoration:none; padding:14px 24px; border-radius:8px; font-weight:800; font-size:16px;">
                    {escape(action_label)}
                  </a>
                </div>"""

    return f"""<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escape(title)}</title>
  </head>
  <body style="margin:0; padding:0; background:#f5f8fd; font-family:Arial, Helvetica, sans-serif; color:#0f172a;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f5f8fd; padding:28px 12px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;">
            <tr>
              <td align="center" style="padding:10px 0 22px;">
                <img src="{escape(logo_url)}" alt="Sorriso da Gente" style="width:220px; max-width:80%; height:auto; display:block;">
              </td>
            </tr>
            <tr>
              <td style="background:#ffffff; border:1px solid #dbe4f0; border-radius:8px; padding:30px;">
                <h1 style="margin:0; color:#0d47a1; font-size:24px; line-height:1.25; font-weight:800;">{escape(title)}</h1>
                <p style="margin:14px 0 0; color:#475569; font-size:16px; line-height:1.65;">{escape(intro)}</p>
                <div style="margin-top:24px; color:#0f172a; font-size:15px; line-height:1.65;">
                  {body_html}
                </div>
                {action_html}
                <div style="height:1px; background:#e2e8f0; margin:24px 0;"></div>
                <p style="margin:0; color:#64748b; font-size:13px; line-height:1.6;">
                  E-mail automatico do Programa Sorriso da Gente. Nao responda esta mensagem.
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def build_registration_approved_email(registration):
    base_url = _app_base_url()
    first_access_url = f'{base_url}/primeiro-acesso'
    role_label = get_role_label(registration.get('requested_role'))
    name = registration.get('full_name') or 'Profissional'
    username = registration.get('desired_username') or ''

    text_body = f"""Ola, {name}.

Seu pre-cadastro no Programa Sorriso da Gente foi aprovado.

Login liberado: {username}
Classe: {role_label}

Para concluir o primeiro acesso, abra:
{first_access_url}

Na primeira etapa, informe seu login e sua data de nascimento. Em seguida, defina sua senha definitiva e confirme seu e-mail de recuperacao.

E-mail automatico. Nao responda esta mensagem.
"""
    body_html = f"""
                  <p style="margin:0 0 12px;"><strong>Login liberado:</strong> {escape(username)}</p>
                  <p style="margin:0 0 12px;"><strong>Classe:</strong> {escape(role_label)}</p>
                  <p style="margin:0;">Para concluir o primeiro acesso, informe seu login e sua data de nascimento. Em seguida, defina sua senha definitiva e confirme seu e-mail de recuperacao.</p>
"""
    html_body = _professional_email_shell(
        'Pre-cadastro aprovado',
        f'Ola, {name}. Seu acesso ao Programa Sorriso da Gente foi aprovado pela administracao.',
        body_html,
        action_url=first_access_url,
        action_label='Fazer primeiro acesso',
    )
    return text_body, html_body


def build_registration_rejected_email(registration):
    name = registration.get('full_name') or 'Profissional'
    notes = (registration.get('review_notes') or '').strip()
    notes_text = notes or 'A administracao nao informou observacoes adicionais.'

    text_body = f"""Ola, {name}.

Seu pre-cadastro no Programa Sorriso da Gente foi recusado apos analise administrativa.

Observacoes da administracao:
{notes_text}

Revise as informacoes e entre em contato com a administracao se precisar reenviar ou corrigir seu cadastro.

E-mail automatico. Nao responda esta mensagem.
"""
    body_html = f"""
                  <p style="margin:0 0 12px;">Seu pre-cadastro foi recusado apos analise administrativa.</p>
                  <div style="margin-top:16px; padding:16px; background:#fef2f2; border:1px solid #fecaca; border-radius:8px;">
                    <div style="font-weight:800; color:#991b1b; margin-bottom:8px;">Observacoes da administracao</div>
                    <div style="white-space:pre-wrap; color:#7f1d1d;">{escape(notes_text)}</div>
                  </div>
                  <p style="margin:18px 0 0;">Revise as informacoes e entre em contato com a administracao se precisar reenviar ou corrigir seu cadastro.</p>
"""
    html_body = _professional_email_shell(
        'Pre-cadastro recusado',
        f'Ola, {name}. Sua solicitacao foi analisada pela administracao.',
        body_html,
    )
    return text_body, html_body


def send_registration_approved_email(registration):
    text_body, html_body = build_registration_approved_email(registration)
    send_email('Pre-cadastro aprovado - Sorriso da Gente', registration.get('email'), text_body, html_body=html_body)


def send_registration_rejected_email(registration):
    text_body, html_body = build_registration_rejected_email(registration)
    send_email('Pre-cadastro recusado - Sorriso da Gente', registration.get('email'), text_body, html_body=html_body)
