import os
import time
import logging
from logging.handlers import RotatingFileHandler
import redis
from flask import Flask, render_template, g, request
from flask_session import Session
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

from database import init_db
from utils import User
from extensions import limiter
from constants import get_role_label
from services.security_service import can
from blueprints.admin import admin_bp
from blueprints.patients import patients_bp
from blueprints.anamnesis import anamnesis_bp
from blueprints.exams import exams_bp
from blueprints.prosthesis import prosthesis_bp
from blueprints.agenda import agenda_bp
from blueprints.triage import triage_bp

load_dotenv()

# ── Logging ────────────────────────────────────────────────────────────────
def configure_logging(app):
    """Configura logging rotativo em arquivo (apenas fora do modo debug)."""
    if not app.debug:
        import os
        os.makedirs('logs', exist_ok=True)
        handler = RotatingFileHandler(
            'logs/app.log',
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5
        )
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s %(levelname)s [%(name)s] %(message)s'
        )
        handler.setFormatter(formatter)
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('GestaoClinica iniciando...')

def register_request_hooks(app):
    """Registra hooks para medir e logar o tempo de cada request."""
    @app.before_request
    def start_timer():
        g.start_time = time.time()

    @app.after_request
    def log_request(response):
        start_time = getattr(g, 'start_time', time.time())
        duration = round((time.time() - start_time) * 1000, 2)
        app.logger.info(
            f"{request.method} {request.path} → {response.status_code} [{duration}ms]"
        )
        return response

def create_app():
    app = Flask(__name__)

    secret_key = os.getenv('SECRET_KEY')
    if not secret_key:
        raise RuntimeError(
            "SECRET_KEY não está definida. "
            "Configure a variável de ambiente no arquivo .env antes de iniciar a aplicação."
        )
    app.config['SECRET_KEY'] = secret_key
    
    # Configuração do ProxyFix para Nginx
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # Inicializações
    csrf = CSRFProtect(app)
    limiter.init_app(app)
    
    # Configuração do Cache (Redis)
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    app.config['CACHE_TYPE'] = 'RedisCache'
    app.config['CACHE_REDIS_URL'] = redis_url
    app.config['CACHE_DEFAULT_TIMEOUT'] = 300  # 5 minutos
    
    from extensions import cache
    cache.init_app(app)
    
    from celery_app import make_celery
    make_celery(app)
    
    # Sessões server-side via Redis
    app.config['SESSION_TYPE'] = 'redis'
    app.config['SESSION_REDIS'] = redis.from_url(redis_url)
    app.config['SESSION_PERMANENT'] = True
    app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 horas
    app.config['SESSION_USE_SIGNER'] = True           # Assina o ID da sessão
    Session(app)
    
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.get(user_id)

    @app.context_processor
    def inject_security_helpers():
        return {
            'can': can,
            'role_label': get_role_label,
        }

    # Inicializar Banco de Dados
    with app.app_context():
        init_db()

    # Criação dos diretórios de upload
    os.makedirs('uploads/exames', exist_ok=True)

    # Registro de Blueprints
    from blueprints.auth import auth_bp
    from blueprints.main import main_bp
    from blueprints.documents import documents_bp
    from blueprints.endodontia import endodontia_bp
    from blueprints.reports_bp import reports_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(patients_bp)
    app.register_blueprint(anamnesis_bp)
    app.register_blueprint(exams_bp)
    app.register_blueprint(prosthesis_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(endodontia_bp)
    app.register_blueprint(agenda_bp)
    app.register_blueprint(triage_bp)
    app.register_blueprint(reports_bp)

    # Configura logging e hooks de monitoramento
    configure_logging(app)
    register_request_hooks(app)

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)
