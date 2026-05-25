from celery import Celery
import os
from flask import Flask

# Instância Global importável pelo trabalhador celery e pelas tasks
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
celery = Celery(
    'gestaoclinica',
    backend=redis_url,
    broker=redis_url,
    include=['tasks.pdf_tasks']
)

# Evita DeprecationWarning no Celery 6+ e falha silenciosa no boot
# quando o broker (Redis) ainda não está disponível.
celery.conf.broker_connection_retry_on_startup = True

def make_celery(app):
    celery.conf.update(app.config)
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery
