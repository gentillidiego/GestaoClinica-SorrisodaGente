from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.security import check_password_hash, generate_password_hash
from database import query, execute
from utils import User
from extensions import limiter
from services.security_service import audit_log, get_client_ip

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute; 20 per hour")
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user_data = query("SELECT * FROM users WHERE username = %s", (username,), one=True)
        
        if user_data and check_password_hash(user_data['password'], password):
            if not user_data.get('active', True):
                audit_log(
                    action='login_blocked_inactive_user',
                    module='auth',
                    status='denied',
                    details={'username': username}
                )
                flash('Usuário inativo. Procure a administração do sistema.', 'danger')
                return render_template('login.html')

            user = User(
                id=user_data['id'], 
                username=user_data['username'], 
                role=user_data['role'],
                full_name=user_data.get('full_name'),
                matricula=user_data.get('matricula'),
                cro=user_data.get('cro'),
                cro_uf=user_data.get('cro_uf'),
                cns=user_data.get('cns'),
                cbo=user_data.get('cbo'),
                cnes=user_data.get('cnes'),
                ine=user_data.get('ine'),
                active=user_data.get('active', True)
            )
            login_user(user)
            execute(
                "UPDATE users SET last_login_at = NOW(), last_login_ip = %s WHERE id = %s",
                (get_client_ip(), user_data['id'])
            )
            audit_log(
                action='login_success',
                module='auth',
                entity_type='user',
                entity_id=user_data['id'],
                details={'username': username, 'role': user_data['role']}
            )
            return redirect(url_for('main.dashboard'))

        audit_log(
            action='login_failed',
            module='auth',
            status='failed',
            details={'username': username}
        )
        flash('Usuário ou senha inválidos', 'danger')
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    audit_log(action='logout', module='auth')
    logout_user()
    return redirect(url_for('auth.login'))
