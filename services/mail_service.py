import os
import smtplib
from email.message import EmailMessage


def _bool_env(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def send_email(subject, to_email, text_body, html_body=None, attachments=None):
    if not to_email:
        raise ValueError('Destinatario de e-mail ausente.')

    host = os.getenv('SMTP_HOST', 'localhost')
    port = int(os.getenv('SMTP_PORT', '25'))
    username = os.getenv('SMTP_USERNAME') or None
    password = os.getenv('SMTP_PASSWORD') or None
    use_tls = _bool_env('SMTP_USE_TLS', False)
    use_ssl = _bool_env('SMTP_USE_SSL', False)
    from_email = os.getenv('MAIL_FROM', 'nao-responda@localhost')

    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = from_email
    message['To'] = to_email
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype='html')
    for filename, content, mime_type in attachments or []:
        maintype, subtype = (mime_type or 'application/octet-stream').split('/', 1)
        message.add_attachment(
            content,
            maintype=maintype,
            subtype=subtype,
            filename=filename,
        )

    smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with smtp_class(host, port, timeout=15) as server:
        if not use_ssl:
            server.ehlo()
            if use_tls:
                server.starttls()
                server.ehlo()
        if username:
            server.login(username, password or '')
        server.send_message(message)
