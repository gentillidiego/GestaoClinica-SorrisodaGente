import hashlib
import os
import secrets
from datetime import date, datetime, timedelta, timezone
from html import escape

from flask import url_for
from werkzeug.security import generate_password_hash

from database import execute, query
from services.mail_service import send_email


FIRST_ACCESS_SESSION_KEY = 'pending_first_access_user_id'
FIRST_ACCESS_VERIFIED_AT_KEY = 'pending_first_access_verified_at'
PASSWORD_RESET_HOURS = 2


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def parse_birthdate_input(value):
    raw = (value or '').strip()
    if not raw:
        return None

    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d%m%Y'):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def hash_token(raw_token):
    return hashlib.sha256((raw_token or '').encode('utf-8')).hexdigest()


def validate_password_strength(password):
    if len(password or '') < 8:
        return 'A senha definitiva deve ter pelo menos 8 caracteres.'
    if not any(char.isalpha() for char in password):
        return 'A senha definitiva deve conter pelo menos uma letra.'
    if not any(char.isdigit() for char in password):
        return 'A senha definitiva deve conter pelo menos um numero.'
    return None


def get_user_for_login(username):
    return query("SELECT * FROM users WHERE username = %s", ((username or '').strip(),), one=True)


def verify_first_access_user(username, birthdate_input):
    user = get_user_for_login(username)
    if not user or not user.get('active', True) or not user.get('is_first_access'):
        return None

    birthdate = parse_birthdate_input(birthdate_input)
    stored_birthdate = user.get('data_nascimento')
    if not birthdate or not stored_birthdate:
        return None

    if isinstance(stored_birthdate, datetime):
        stored_birthdate = stored_birthdate.date()
    elif isinstance(stored_birthdate, str):
        try:
            stored_birthdate = date.fromisoformat(stored_birthdate)
        except ValueError:
            return None

    return user if stored_birthdate == birthdate else None


def complete_first_access(user_id, email, password):
    now = utcnow()
    execute(
        """
        UPDATE users
        SET password = %s,
            email = %s,
            is_first_access = FALSE,
            first_access_completed_at = %s,
            email_confirmed_at = %s,
            password_changed_at = %s,
            password_reset_token_hash = NULL,
            password_reset_expires_at = NULL,
            password_reset_used_at = NULL
        WHERE id = %s
        """,
        (generate_password_hash(password), email, now, now, now, user_id),
    )


def create_password_reset_token(user_id):
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_token(raw_token)
    expires_at = utcnow() + timedelta(hours=PASSWORD_RESET_HOURS)
    execute(
        """
        UPDATE users
        SET password_reset_token_hash = %s,
            password_reset_expires_at = %s,
            password_reset_used_at = NULL
        WHERE id = %s
        """,
        (token_hash, expires_at, user_id),
    )
    return raw_token, expires_at


def build_reset_url(token):
    base_url = os.getenv('APP_BASE_URL', '').rstrip('/')
    path = url_for('auth.reset_password', token=token)
    return f'{base_url}{path}' if base_url else url_for('auth.reset_password', token=token, _external=True)


def build_static_url(filename):
    base_url = os.getenv('APP_BASE_URL', '').rstrip('/')
    path = url_for('static', filename=filename)
    return f'{base_url}{path}' if base_url else url_for('static', filename=filename, _external=True)


def build_password_reset_email(user, token):
    reset_url = build_reset_url(token)
    logo_url = build_static_url('logo_sorriso_horizontal.png')
    display_name = user.get('full_name') or user.get('username') or 'profissional'
    safe_display_name = escape(str(display_name))
    text_body = (
        f'Ola, {display_name}.\n\n'
        'Recebemos uma solicitacao para redefinir sua senha.\n'
        f'Acesse o link abaixo em ate {PASSWORD_RESET_HOURS} horas:\n\n'
        f'{reset_url}\n\n'
        'Se voce nao pediu esta redefinicao, ignore esta mensagem.'
    )
    html_body = f"""<!doctype html>
<html lang="pt-BR">
  <body style="margin:0; padding:0; background:#f4f7fb; font-family:Arial, Helvetica, sans-serif; color:#172033;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f7fb; padding:32px 12px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:620px;">
            <tr>
              <td align="center" style="padding:12px 0 22px;">
                <img src="{logo_url}" alt="Sorriso da Gente" width="220" style="display:block; max-width:220px; height:auto;">
              </td>
            </tr>
            <tr>
              <td style="background:#ffffff; border:1px solid #dbe4f0; border-radius:8px; padding:32px; box-shadow:0 12px 28px rgba(15, 23, 42, 0.08);">
                <div style="font-size:13px; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; color:#0f766e; margin-bottom:12px;">
                  Redefinicao de senha
                </div>
                <h1 style="margin:0; color:#0d47a1; font-size:26px; line-height:1.2; font-weight:800;">
                  Ola, {safe_display_name}
                </h1>
                <p style="margin:18px 0 0; color:#475569; font-size:16px; line-height:1.65;">
                  Recebemos uma solicitacao para redefinir sua senha no Programa Sorriso da Gente.
                </p>
                <p style="margin:12px 0 0; color:#475569; font-size:16px; line-height:1.65;">
                  O link abaixo e valido por {PASSWORD_RESET_HOURS} horas.
                </p>
                <div style="padding:26px 0 20px; text-align:center;">
                  <a href="{reset_url}" style="display:inline-block; background:#0d47a1; color:#ffffff; text-decoration:none; padding:14px 24px; border-radius:8px; font-weight:800; font-size:16px;">
                    Redefinir senha
                  </a>
                </div>
                <p style="margin:0; color:#64748b; font-size:13px; line-height:1.6;">
                  Se o botao nao funcionar, acesse este link:
                </p>
                <p style="margin:8px 0 0; color:#0d47a1; font-size:13px; line-height:1.6; word-break:break-all;">
                  {reset_url}
                </p>
                <div style="height:1px; background:#e2e8f0; margin:24px 0;"></div>
                <p style="margin:0; color:#64748b; font-size:13px; line-height:1.6;">
                  Se voce nao pediu esta redefinicao, ignore esta mensagem. Sua senha atual permanecera inalterada.
                </p>
              </td>
            </tr>
            <tr>
              <td align="center" style="padding:18px 8px 0; color:#64748b; font-size:12px; line-height:1.5;">
                Programa Sorriso da Gente<br>
                E-mail automatico. Nao responda esta mensagem.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""
    return text_body, html_body


def send_password_reset_email(user, token):
    subject = 'Redefinicao de senha - Sorriso da Gente'
    text_body, html_body = build_password_reset_email(user, token)
    send_email(subject, user.get('email'), text_body, html_body=html_body)


def find_user_for_password_reset(identifier):
    value = (identifier or '').strip().lower()
    if not value:
        return None
    return query(
        """
        SELECT *
        FROM users
        WHERE lower(username) = %s OR lower(email) = %s
        ORDER BY id ASC
        LIMIT 1
        """,
        (value, value),
        one=True,
    )


def get_user_by_reset_token(token):
    token_hash = hash_token(token)
    return query(
        """
        SELECT *
        FROM users
        WHERE password_reset_token_hash = %s
          AND password_reset_expires_at IS NOT NULL
          AND password_reset_expires_at >= NOW()
          AND password_reset_used_at IS NULL
        LIMIT 1
        """,
        (token_hash,),
        one=True,
    )


def consume_password_reset(user_id, email, password):
    now = utcnow()
    execute(
        """
        UPDATE users
        SET password = %s,
            email = %s,
            email_confirmed_at = COALESCE(email_confirmed_at, %s),
            is_first_access = FALSE,
            first_access_completed_at = COALESCE(first_access_completed_at, %s),
            password_changed_at = %s,
            password_reset_token_hash = NULL,
            password_reset_used_at = %s,
            password_reset_expires_at = NULL
        WHERE id = %s
        """,
        (generate_password_hash(password), email, now, now, now, now, user_id),
    )
