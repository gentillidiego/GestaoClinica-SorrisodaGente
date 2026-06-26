from celery import Celery
from celery.schedules import crontab
import os
from flask import Flask

# Instância Global importável pelo trabalhador celery e pelas tasks
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
celery = Celery(
    'gestaoclinica',
    backend=redis_url,
    broker=redis_url,
    include=[
        'tasks.pdf_tasks', 'tasks.report_tasks', 'tasks.gdrive_tasks', 'tasks.esus_tasks',
        'tasks.communication_tasks',
    ]
)

# Evita DeprecationWarning no Celery 6+ e falha silenciosa no boot
# quando o broker (Redis) ainda não está disponível.
celery.conf.broker_connection_retry_on_startup = True
celery.conf.timezone = os.getenv('TZ', 'America/Maceio')


def _env_enabled(name, default='true'):
    return os.getenv(name, default).strip().lower() in {'1', 'true', 'yes', 'sim', 'on'}


if _env_enabled('REPORTS_SCHEDULER_ENABLED'):
    celery.conf.beat_schedule = {
        'generate-monthly-government-reports': {
            'task': 'tasks.report_tasks.generate_monthly_reports_task',
            'schedule': crontab(
                minute=os.getenv('REPORTS_SCHEDULE_MINUTE', '20'),
                hour=os.getenv('REPORTS_SCHEDULE_HOUR', '2'),
                day_of_month=os.getenv('REPORTS_SCHEDULE_DAY', '1'),
            ),
            'kwargs': {
                'report_type': os.getenv('REPORTS_SCHEDULE_TYPES', 'all'),
                'output_dir': os.getenv('REPORTS_OUTPUT_DIR', 'pdf_temp'),
            },
        },
    }

celery.conf.beat_schedule = celery.conf.beat_schedule or {}
celery.conf.beat_schedule['cleanup-gdrive-cache-hourly'] = {
    'task': 'tasks.gdrive_tasks.cleanup_gdrive_cache_task',
    'schedule': crontab(minute='0'),  # Executa a cada hora cheia
}
celery.conf.beat_schedule['reconcile-staged-exam-files'] = {
    'task': 'tasks.gdrive_tasks.reconcile_staged_exam_files_task',
    'schedule': crontab(minute='*/5'),
}

# Remessa quinzenal e-SUS APS: executa todo dia às 06:00 e verifica se é dia de envio
celery.conf.beat_schedule['esus-remessa-quinzenal'] = {
    'task': 'tasks.esus_tasks.gerar_e_enviar_remessa_quinzenal',
    'schedule': crontab(
        hour=os.getenv('ESUS_REMESSA_HORA', '6'),
        minute=os.getenv('ESUS_REMESSA_MINUTO', '0'),
    ),
}

# Lembretes automáticos de consulta: verifica a cada hora se há consultas
# próximas sem lembrete enviado ainda (a tarefa em si fica inerte se
# APPOINTMENT_REMINDERS_ENABLED não estiver ligado).
celery.conf.beat_schedule['comunicacao-lembretes-consulta'] = {
    'task': 'tasks.communication_tasks.send_appointment_reminders_task',
    'schedule': crontab(minute='30'),
}


def make_celery(app):
    celery.conf.update(app.config)
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery
