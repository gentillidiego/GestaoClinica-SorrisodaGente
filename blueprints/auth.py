from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import login_required, login_user, logout_user
from werkzeug.security import check_password_hash

from database import execute
from extensions import limiter
from services.auth_flow_service import (
    FIRST_ACCESS_SESSION_KEY,
    FIRST_ACCESS_VERIFIED_AT_KEY,
    complete_first_access as complete_first_access_record,
    consume_password_reset,
    create_password_reset_token,
    find_user_for_password_reset,
    get_user_by_reset_token,
    get_user_for_login,
    send_password_reset_email,
    validate_password_strength,
    verify_first_access_user,
)
from services.security_service import audit_log, get_client_ip
from services.web_security_service import regenerate_session_after_authentication
from utils import User


auth_bp = Blueprint('auth', __name__)


def _build_user(user_data):
    return User(
        id=user_data['id'],
        username=user_data['username'],
        role=user_data['role'],
        full_name=user_data.get('full_name'),
        matricula=user_data.get('matricula'),
        email=user_data.get('email'),
        celular=user_data.get('celular'),
        data_nascimento=user_data.get('data_nascimento'),
        cro=user_data.get('cro'),
        cro_uf=user_data.get('cro_uf'),
        cns=user_data.get('cns'),
        cbo=user_data.get('cbo'),
        cnes=user_data.get('cnes'),
        ine=user_data.get('ine'),
        active=user_data.get('active', True),
        is_first_access=user_data.get('is_first_access', False),
    )


def _mark_login(user_id):
    execute(
        "UPDATE users SET last_login_at = NOW(), last_login_ip = %s WHERE id = %s",
        (get_client_ip(), user_id),
    )


def _clear_first_access_session():
    session.pop(FIRST_ACCESS_SESSION_KEY, None)
    session.pop(FIRST_ACCESS_VERIFIED_AT_KEY, None)


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute; 20 per hour")
def login():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''

        user_data = get_user_for_login(username)

        if user_data and user_data.get('is_first_access'):
            audit_log(
                action='login_redirect_first_access',
                module='auth',
                status='denied',
                entity_type='user',
                entity_id=user_data['id'],
                details={'username': username},
            )
            flash('Este usuario ainda precisa concluir o primeiro acesso.', 'warning')
            return redirect(url_for('auth.first_access'))

        if user_data and check_password_hash(user_data['password'], password):
            if not user_data.get('active', True):
                audit_log(
                    action='login_blocked_inactive_user',
                    module='auth',
                    status='denied',
                    details={'username': username},
                )
                flash('Usuario inativo. Procure a administracao do sistema.', 'danger')
                return render_template('login.html')

            user = _build_user(user_data)
            regenerate_session_after_authentication()
            login_user(user)
            _mark_login(user_data['id'])
            audit_log(
                action='login_success',
                module='auth',
                entity_type='user',
                entity_id=user_data['id'],
                details={'username': username, 'role': user_data['role']},
            )
            return redirect(url_for('main.dashboard'))

        audit_log(
            action='login_failed',
            module='auth',
            status='failed',
            details={'username': username},
        )
        flash('Usuario ou senha invalidos.', 'danger')

    return render_template('login.html')


@auth_bp.route('/primeiro-acesso', methods=['GET', 'POST'])
@limiter.limit("5 per minute; 20 per hour")
def first_access():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        birthdate = request.form.get('birthdate')
        user_data = verify_first_access_user(username, birthdate)

        if not user_data:
            audit_log(
                action='first_access_failed',
                module='auth',
                status='failed',
                details={'username': username},
            )
            flash('Login ou data de nascimento invalidos para primeiro acesso.', 'danger')
            return render_template('auth/first_access.html')

        session[FIRST_ACCESS_SESSION_KEY] = user_data['id']
        session[FIRST_ACCESS_VERIFIED_AT_KEY] = True
        audit_log(
            action='first_access_verified',
            module='auth',
            entity_type='user',
            entity_id=user_data['id'],
            details={'username': username},
        )
        return redirect(url_for('auth.complete_first_access_page'))

    return render_template('auth/first_access.html')


@auth_bp.route('/primeiro-acesso/definir-senha', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def complete_first_access_page():
    user_id = session.get(FIRST_ACCESS_SESSION_KEY)
    verified = session.get(FIRST_ACCESS_VERIFIED_AT_KEY)
    if not user_id or not verified:
        flash('Valide primeiro o seu primeiro acesso.', 'warning')
        return redirect(url_for('auth.first_access'))

    user_data = User.get(user_id)
    if not user_data:
        _clear_first_access_session()
        flash('Usuario nao encontrado.', 'danger')
        return redirect(url_for('auth.first_access'))

    current_email = user_data.email or ''
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        password_confirm = request.form.get('password_confirm') or ''

        if not email:
            flash('Informe o e-mail para recuperacao futura de senha.', 'danger')
            return render_template('auth/first_access_set_password.html', user=user_data, current_email=current_email)

        if password != password_confirm:
            flash('As senhas informadas nao conferem.', 'danger')
            return render_template('auth/first_access_set_password.html', user=user_data, current_email=email)

        password_error = validate_password_strength(password)
        if password_error:
            flash(password_error, 'danger')
            return render_template('auth/first_access_set_password.html', user=user_data, current_email=email)

        complete_first_access_record(user_id, email, password)
        fresh_user_data = get_user_for_login(user_data.username)
        user = _build_user(fresh_user_data)
        regenerate_session_after_authentication()
        login_user(user)
        _mark_login(user_id)
        audit_log(
            action='first_access_completed',
            module='auth',
            entity_type='user',
            entity_id=user_id,
            details={'username': user.username},
        )
        flash('Primeiro acesso concluido com sucesso.', 'success')
        return redirect(url_for('main.dashboard'))

    return render_template('auth/first_access_set_password.html', user=user_data, current_email=current_email)


@auth_bp.route('/esqueci-senha', methods=['GET', 'POST'])
@limiter.limit("5 per minute; 20 per hour")
def forgot_password():
    if request.method == 'POST':
        identifier = (request.form.get('identifier') or '').strip()
        user_data = find_user_for_password_reset(identifier)

        if user_data and user_data.get('active', True) and user_data.get('email'):
            token, expires_at = create_password_reset_token(user_data['id'])
            try:
                send_password_reset_email(user_data, token)
                audit_log(
                    action='password_reset_requested',
                    module='auth',
                    entity_type='user',
                    entity_id=user_data['id'],
                    details={'identifier': identifier, 'expires_at': expires_at.isoformat()},
                )
            except Exception as exc:
                current_app.logger.exception('Falha ao enviar e-mail de redefinicao')
                audit_log(
                    action='password_reset_email_failed',
                    module='auth',
                    entity_type='user',
                    entity_id=user_data['id'],
                    status='failed',
                    details={'identifier': identifier, 'error': str(exc)},
                )
        else:
            audit_log(
                action='password_reset_requested_unknown',
                module='auth',
                details={'identifier': identifier},
            )

        flash('Se o cadastro existir, enviaremos um link de redefinicao para o e-mail informado.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')


@auth_bp.route('/redefinir-senha', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def reset_password():
    token = (request.args.get('token') or request.form.get('token') or '').strip()
    user_data = get_user_by_reset_token(token) if token else None

    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        password_confirm = request.form.get('password_confirm') or ''

        if not user_data:
            flash('O link de redefinicao e invalido ou expirou.', 'danger')
            return render_template('auth/reset_password.html', token=token, user=None), 400

        if not email:
            flash('Informe o e-mail do cadastro.', 'danger')
            return render_template('auth/reset_password.html', token=token, user=user_data), 400

        if password != password_confirm:
            flash('As senhas informadas nao conferem.', 'danger')
            return render_template('auth/reset_password.html', token=token, user=user_data), 400

        password_error = validate_password_strength(password)
        if password_error:
            flash(password_error, 'danger')
            return render_template('auth/reset_password.html', token=token, user=user_data), 400

        consume_password_reset(user_data['id'], email, password)
        audit_log(
            action='password_reset_completed',
            module='auth',
            entity_type='user',
            entity_id=user_data['id'],
            details={'username': user_data['username']},
        )
        flash('Senha redefinida com sucesso. Voce ja pode entrar no sistema.', 'success')
        return redirect(url_for('auth.login'))

    if token and not user_data:
        flash('O link de redefinicao e invalido ou expirou.', 'danger')

    return render_template('auth/reset_password.html', token=token, user=user_data)


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    audit_log(action='logout', module='auth')
    logout_user()
    session.clear()
    return redirect(url_for('auth.login'))
