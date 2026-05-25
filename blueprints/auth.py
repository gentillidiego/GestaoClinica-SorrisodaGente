from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.security import check_password_hash, generate_password_hash
from database import query, execute
from utils import User
from extensions import limiter

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute; 20 per hour")
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user_data = query("SELECT * FROM users WHERE username = %s", (username,), one=True)
        
        if user_data and check_password_hash(user_data['password'], password):
            user = User(
                id=user_data['id'], 
                username=user_data['username'], 
                role=user_data['role'],
                full_name=user_data.get('full_name'),
                matricula=user_data.get('matricula'),
                cro=user_data.get('cro'),
                cro_uf=user_data.get('cro_uf')
            )
            login_user(user)
            return redirect(url_for('main.dashboard'))
        
        flash('Usuário ou senha inválidos', 'danger')
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
