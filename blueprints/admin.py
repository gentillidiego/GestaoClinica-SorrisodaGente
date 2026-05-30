from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from database import query, execute, execute_returning
from functools import wraps
from constants import Role, get_role_choices
from services.security_service import audit_log, list_audit_logs, permission_required

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != Role.ADMIN:
            flash('Acesso negado. Apenas administradores podem acessar esta página.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def admin_or_atendente_required(f):
    """Permite visualização da lista de usuários para admin e atendente."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.can('users:view'):
            flash('Acesso negado.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/users')
@login_required
@admin_or_atendente_required
def list_users():
    users = query("""
        SELECT id, username, role, full_name, active, last_login_at, last_login_ip
        FROM users
        ORDER BY role, username
    """)
    return render_template('admin/users.html', users=users)

@admin_bp.route('/users/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_user():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        active = request.form.get('active') == '1'
        # matricula não é mais usada — campo removido
        cro = request.form.get('cro')
        cro_uf = request.form.get('cro_uf')

        valid_roles = {role_value for role_value, _ in get_role_choices()}
        if role not in valid_roles:
            flash('Perfil de acesso inválido.', 'danger')
            return render_template('admin/add_user.html', role_choices=get_role_choices())

        hashed_password = generate_password_hash(password)

        try:
            user_id = execute_returning(
                """
                INSERT INTO users (username, password, role, full_name, cro, cro_uf, active)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (username, hashed_password, role, full_name, cro, cro_uf, active)
            )
            audit_log(
                action='user_created',
                module='admin',
                entity_type='user',
                entity_id=user_id,
                details={'username': username, 'role': role, 'active': active}
            )
            flash(f'Usuário {full_name or username} criado com sucesso!', 'success')
            return redirect(url_for('admin.list_users'))
        except Exception as e:
            flash(f'Erro ao criar usuário: {str(e)}', 'danger')

    return render_template('admin/add_user.html', role_choices=get_role_choices())

@admin_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash('Você não pode excluir a si mesmo.', 'danger')
    else:
        user = query("SELECT id, username, role FROM users WHERE id = %s", (user_id,), one=True)
        execute("DELETE FROM users WHERE id = %s", (user_id,))
        audit_log(
            action='user_deleted',
            module='admin',
            entity_type='user',
            entity_id=user_id,
            details={'username': user['username'], 'role': user['role']} if user else None
        )
        flash('Usuário excluído com sucesso.', 'success')
    return redirect(url_for('admin.list_users'))

@admin_bp.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = query("SELECT id, username, role, full_name, cro, cro_uf, active FROM users WHERE id = %s", (user_id,), one=True)
    if not user:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('admin.list_users'))

    if request.method == 'POST':
        full_name = request.form.get('full_name')
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        active = request.form.get('active') == '1'
        cro = request.form.get('cro')
        cro_uf = request.form.get('cro_uf')

        valid_roles = {role_value for role_value, _ in get_role_choices()}
        if role not in valid_roles:
            flash('Perfil de acesso inválido.', 'danger')
            return render_template('admin/edit_user.html', user=user, role_choices=get_role_choices())

        try:
            if password:
                hashed_password = generate_password_hash(password)
                execute(
                    "UPDATE users SET username=%s, password=%s, role=%s, full_name=%s, cro=%s, cro_uf=%s, active=%s WHERE id=%s",
                    (username, hashed_password, role, full_name, cro, cro_uf, active, user_id)
                )
            else:
                execute(
                    "UPDATE users SET username=%s, role=%s, full_name=%s, cro=%s, cro_uf=%s, active=%s WHERE id=%s",
                    (username, role, full_name, cro, cro_uf, active, user_id)
                )
            audit_log(
                action='user_updated',
                module='admin',
                entity_type='user',
                entity_id=user_id,
                details={
                    'username': username,
                    'previous_role': user['role'],
                    'new_role': role,
                    'active': active,
                    'password_changed': bool(password)
                }
            )
            flash(f'Usuário {full_name or username} atualizado com sucesso!', 'success')
            return redirect(url_for('admin.list_users'))
        except Exception as e:
            flash(f'Erro ao atualizar usuário: {str(e)}', 'danger')

    return render_template('admin/edit_user.html', user=user, role_choices=get_role_choices())


@admin_bp.route('/audit')
@login_required
@permission_required('audit:view')
def audit_logs():
    filters = {
        'user_id': request.args.get('user_id') or None,
        'module': request.args.get('module') or None,
        'action': request.args.get('action') or None,
        'patient_id': request.args.get('patient_id') or None,
        'status': request.args.get('status') or None,
    }
    logs = list_audit_logs(filters=filters, limit=300)
    users = query("SELECT id, username, full_name FROM users ORDER BY username")
    modules = query("SELECT DISTINCT module FROM audit_logs ORDER BY module")
    return render_template(
        'admin/audit_logs.html',
        logs=logs,
        users=users,
        modules=modules,
        filters=filters,
    )
