import json
from functools import wraps

from flask import abort, current_app, jsonify, redirect, request, url_for
from flask_login import current_user

from constants import get_role_label, role_has_permission
from database import execute, query


AUDIT_SEVERITY_SQL = """
    CASE
        WHEN status IN ('denied', 'failed') THEN 'alta'
        WHEN action ILIKE '%%delete%%'
          OR action ILIKE '%%deleted%%'
          OR action ILIKE '%%blocked%%'
          OR action ILIKE '%%download%%'
          OR action ILIKE '%%export%%'
          OR action ILIKE '%%signature%%'
          OR module IN ('auth', 'security')
        THEN 'media'
        ELSE 'baixa'
    END
"""


def get_client_ip():
    forwarded_for = request.headers.get('X-Forwarded-For', '')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.headers.get('X-Real-IP') or request.remote_addr


def can(permission):
    if not current_user.is_authenticated:
        return False
    return role_has_permission(current_user.role, permission)


def permission_required(permission):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            if not can(permission):
                return deny_access(
                    permissions={'all_of': [permission], 'any_of': []},
                )
            return view_func(*args, **kwargs)
        return wrapped
    return decorator


def deny_access(*, permissions=None, reason='permission_denied', patient_id=None):
    details = {
        'reason': reason,
        'endpoint': request.endpoint,
        'permissions': permissions or {},
    }
    try:
        audit_log(
            action='access_denied',
            module='security',
            patient_id=patient_id,
            status='denied',
            details=details,
        )
    except Exception:
        current_app.logger.exception('Falha ao registrar negação de acesso')

    wants_json = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or request.accept_mimetypes.best == 'application/json'
    )
    if wants_json:
        return jsonify({'error': 'Acesso negado.'}), 403
    abort(403, description='Acesso negado.')


def _safe_json(details):
    if details is None:
        return None
    return json.dumps(details, ensure_ascii=False, default=str)


def audit_log(
    action,
    module,
    entity_type=None,
    entity_id=None,
    patient_id=None,
    status='success',
    details=None,
    user=None,
):
    actor = user or current_user
    user_id = None
    username = None
    user_role = None

    if getattr(actor, 'is_authenticated', False):
        user_id = actor.id
        username = actor.username
        user_role = actor.role

    execute(
        """
        INSERT INTO audit_logs (
            user_id, username, user_role, action, module, entity_type, entity_id,
            patient_id, ip_address, user_agent, method, path, status, details
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        """,
        (
            user_id,
            username,
            user_role,
            action,
            module,
            entity_type,
            str(entity_id) if entity_id is not None else None,
            patient_id,
            get_client_ip(),
            request.headers.get('User-Agent'),
            request.method,
            request.path,
            status,
            _safe_json(details),
        )
    )


def list_audit_logs(filters=None, limit=200):
    filters = filters or {}
    clauses = []
    params = []

    if filters.get('user_id'):
        clauses.append('user_id = %s')
        params.append(filters['user_id'])
    if filters.get('module'):
        clauses.append('module = %s')
        params.append(filters['module'])
    if filters.get('action'):
        clauses.append('action ILIKE %s')
        params.append(f"%{filters['action']}%")
    if filters.get('patient_id'):
        clauses.append('patient_id = %s')
        params.append(filters['patient_id'])
    if filters.get('status'):
        clauses.append('status = %s')
        params.append(filters['status'])
    if filters.get('ip_address'):
        clauses.append('ip_address ILIKE %s')
        params.append(f"%{filters['ip_address']}%")
    if filters.get('created_from'):
        clauses.append('created_at >= %s')
        params.append(f"{filters['created_from']} 00:00:00")
    if filters.get('created_to'):
        clauses.append('created_at <= %s')
        params.append(f"{filters['created_to']} 23:59:59")
    if filters.get('severity'):
        clauses.append(f"({AUDIT_SEVERITY_SQL}) = %s")
        params.append(filters['severity'])

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ''
    params.append(limit)
    return query(
        f"""
        SELECT *,
               {AUDIT_SEVERITY_SQL} AS severity
        FROM audit_logs
        {where_sql}
        ORDER BY created_at DESC
        LIMIT %s
        """,
        tuple(params)
    )


def role_label(role):
    return get_role_label(role)
