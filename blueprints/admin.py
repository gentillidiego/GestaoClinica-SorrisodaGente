from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from database import query, execute
from functools import wraps
from constants import Role

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
        if not current_user.is_authenticated or current_user.role not in [Role.ADMIN, Role.ATENDENTE]:
            flash('Acesso negado.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/users')
@login_required
@admin_or_atendente_required
def list_users():
    users = query("SELECT id, username, role, full_name FROM users ORDER BY role, username")
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
        # matricula não é mais usada — campo removido
        cro = request.form.get('cro')
        cro_uf = request.form.get('cro_uf')

        hashed_password = generate_password_hash(password)

        try:
            execute(
                "INSERT INTO users (username, password, role, full_name, cro, cro_uf) VALUES (%s, %s, %s, %s, %s, %s)",
                (username, hashed_password, role, full_name, cro, cro_uf)
            )
            flash(f'Usuário {full_name or username} criado com sucesso!', 'success')
            return redirect(url_for('admin.list_users'))
        except Exception as e:
            flash(f'Erro ao criar usuário: {str(e)}', 'danger')

    return render_template('admin/add_user.html')

@admin_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash('Você não pode excluir a si mesmo.', 'danger')
    else:
        execute("DELETE FROM users WHERE id = %s", (user_id,))
        flash('Usuário excluído com sucesso.', 'success')
    return redirect(url_for('admin.list_users'))

@admin_bp.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = query("SELECT id, username, role, full_name, cro, cro_uf FROM users WHERE id = %s", (user_id,), one=True)
    if not user:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('admin.list_users'))

    if request.method == 'POST':
        full_name = request.form.get('full_name')
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        cro = request.form.get('cro')
        cro_uf = request.form.get('cro_uf')

        try:
            if password:
                hashed_password = generate_password_hash(password)
                execute(
                    "UPDATE users SET username=%s, password=%s, role=%s, full_name=%s, cro=%s, cro_uf=%s WHERE id=%s",
                    (username, hashed_password, role, full_name, cro, cro_uf, user_id)
                )
            else:
                execute(
                    "UPDATE users SET username=%s, role=%s, full_name=%s, cro=%s, cro_uf=%s WHERE id=%s",
                    (username, role, full_name, cro, cro_uf, user_id)
                )
            flash(f'Usuário {full_name or username} atualizado com sucesso!', 'success')
            return redirect(url_for('admin.list_users'))
        except Exception as e:
            flash(f'Erro ao atualizar usuário: {str(e)}', 'danger')

    return render_template('admin/edit_user.html', user=user)
