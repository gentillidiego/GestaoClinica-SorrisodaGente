import secrets

from flask import current_app, flash, g, jsonify, render_template, request, session
from flask_wtf.csrf import CSRFError


CONTENT_SECURITY_POLICY = '; '.join((
    "default-src 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    "frame-ancestors 'none'",
    "form-action 'self'",
    "img-src 'self' data: blob:",
    "media-src 'self' blob:",
    "font-src 'self' data: https://fonts.gstatic.com",
    (
        "style-src 'self' 'unsafe-inline' "
        "https://fonts.googleapis.com https://cdn.jsdelivr.net"
    ),
    (
        "script-src 'self' 'unsafe-inline' "
        "https://cdn.jsdelivr.net https://unpkg.com https://cdnjs.cloudflare.com"
    ),
    "connect-src 'self'",
    "frame-src 'self' blob:",
    "worker-src 'self' blob:",
    "manifest-src 'self'",
    "upgrade-insecure-requests",
))

DEFAULT_PUBLIC_ERROR = (
    'Não foi possível concluir a operação. Tente novamente e, se o problema '
    'persistir, informe o código de referência à equipe responsável.'
)


def configure_session_security(app):
    """Aplica os atributos de cookie exigidos para a publicação HTTPS."""
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        REMEMBER_COOKIE_SECURE=True,
        REMEMBER_COOKIE_HTTPONLY=True,
        REMEMBER_COOKIE_SAMESITE='Lax',
        PREFERRED_URL_SCHEME='https',
    )


def regenerate_session_after_authentication():
    """Descarta o conteúdo e troca o SID antes de gravar a identidade logada."""
    session.clear()
    regenerate = getattr(current_app.session_interface, 'regenerate', None)
    if callable(regenerate):
        # Flask-Session ignora sessões vazias ou contendo apenas `_permanent`.
        # O marcador existe somente durante a troca do SID.
        session['_session_regeneration_pending'] = True
        regenerate(session)
        session.pop('_session_regeneration_pending', None)
    session.permanent = True


def get_request_reference():
    reference = getattr(g, 'request_reference', None)
    if not reference:
        reference = secrets.token_hex(8).upper()
        g.request_reference = reference
    return reference


def public_error_message(message=DEFAULT_PUBLIC_ERROR):
    return f'{message} Referência: {get_request_reference()}.'


def report_internal_error(
    log_context='Falha interna durante o processamento da requisição',
    public_message=DEFAULT_PUBLIC_ERROR,
):
    reference = get_request_reference()
    current_app.logger.exception('%s [ref=%s]', log_context, reference)
    return f'{public_message} Referência: {reference}.'


def flash_internal_error(
    log_context='Falha interna durante o processamento da requisição',
    public_message=DEFAULT_PUBLIC_ERROR,
    category='danger',
):
    flash(
        report_internal_error(
            log_context=log_context,
            public_message=public_message,
        ),
        category,
    )


def flash_recorded_error(
    log_context,
    public_message=DEFAULT_PUBLIC_ERROR,
    category='danger',
):
    reference = get_request_reference()
    current_app.logger.error('%s [ref=%s]', log_context, reference)
    flash(f'{public_message} Referência: {reference}.', category)


def internal_error_response(
    log_context='Falha interna durante o processamento da requisição',
    public_message=DEFAULT_PUBLIC_ERROR,
    status_code=500,
):
    return report_internal_error(
        log_context=log_context,
        public_message=public_message,
    ), status_code


def _wants_json():
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or request.accept_mimetypes.best == 'application/json'
    )


def _safe_error_response(status_code, title, message, *, reference=None):
    payload = {
        'error': message,
        'reference': reference,
    }
    if _wants_json():
        return jsonify(payload), status_code
    return render_template(
        'error.html',
        status_code=status_code,
        error_title=title,
        error_message=message,
        error_reference=reference,
    ), status_code


def register_web_security(app):
    configure_session_security(app)

    @app.before_request
    def assign_request_reference():
        get_request_reference()

    @app.after_request
    def add_security_headers(response):
        response.headers['X-Request-ID'] = get_request_reference()
        response.headers['Content-Security-Policy'] = CONTENT_SECURITY_POLICY
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = (
            'camera=(), microphone=(), geolocation=(), payment=(), usb=()'
        )
        response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
        response.headers['Cross-Origin-Resource-Policy'] = 'same-origin'
        if request.is_secure:
            response.headers['Strict-Transport-Security'] = (
                'max-age=31536000; includeSubDomains'
            )
        return response

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        reference = get_request_reference()
        app.logger.warning(
            'Requisição rejeitada por CSRF em %s %s: %s [ref=%s]',
            request.method,
            request.path,
            error.description,
            reference,
        )
        return _safe_error_response(
            400,
            'Requisição inválida',
            'A página expirou ou a requisição não pôde ser validada. Atualize a página e tente novamente.',
            reference=reference,
        )

    @app.errorhandler(403)
    def handle_forbidden(error):
        return _safe_error_response(
            403,
            'Acesso negado',
            'Seu perfil não possui permissão para acessar este recurso.',
            reference=get_request_reference(),
        )

    @app.errorhandler(404)
    def handle_not_found(error):
        return _safe_error_response(
            404,
            'Página não encontrada',
            'O endereço solicitado não existe ou não está mais disponível.',
        )

    @app.errorhandler(413)
    def handle_request_too_large(error):
        return _safe_error_response(
            413,
            'Arquivo muito grande para um único envio',
            (
                'O envio excedeu o limite de contenção do servidor. '
                'Divida os arquivos em mais de um envio; os exames originais '
                'não precisam ser reduzidos.'
            ),
            reference=get_request_reference(),
        )

    @app.errorhandler(500)
    def handle_internal_error(error):
        safe_message = report_internal_error()
        return _safe_error_response(
            500,
            'Erro interno',
            safe_message.rsplit(' Referência:', 1)[0],
            reference=get_request_reference(),
        )
