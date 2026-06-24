import os

from celery_app import celery
from services.communication_service import (
    channel_available,
    enqueue_appointment_reminder,
    enqueue_campaign_messages,
    find_consultas_pending_reminder,
    list_templates,
    send_single_message,
)
from services.security_service import audit_log


@celery.task(name='tasks.communication_tasks.send_campaign_task', ignore_result=True)
def send_campaign_task(campaign_id):
    message_ids = enqueue_campaign_messages(campaign_id)
    for message_id in message_ids:
        send_single_message_task.delay(message_id)
    return {'campaign_id': campaign_id, 'total_queued': len(message_ids)}


@celery.task(
    bind=True,
    name='tasks.communication_tasks.send_single_message_task',
    max_retries=5,
    acks_late=True,
)
def send_single_message_task(self, message_id):
    try:
        return send_single_message(message_id)
    except Exception as exc:
        countdown = min(30 * (2 ** self.request.retries), 1800)
        raise self.retry(exc=exc, countdown=countdown)


def _env_enabled(name, default='false'):
    return os.getenv(name, default).strip().lower() in {'1', 'true', 'yes', 'sim', 'on'}


@celery.task(name='tasks.communication_tasks.send_appointment_reminders_task', ignore_result=True)
def send_appointment_reminders_task():
    if not _env_enabled('APPOINTMENT_REMINDERS_ENABLED'):
        return {'status': 'disabled'}

    hours_ahead = int(os.getenv('APPOINTMENT_REMINDER_HOURS_AHEAD', '48'))
    queued = 0

    for channel in ('email', 'whatsapp'):
        if not channel_available(channel):
            continue
        templates = list_templates(channel=channel, active_only=True)
        reminder_template = next(
            (t for t in templates if t['category'] == 'lembrete_consulta'), None
        )
        if not reminder_template:
            continue

        consultas = find_consultas_pending_reminder(channel, hours_ahead=hours_ahead)
        for consulta in consultas:
            message_id = enqueue_appointment_reminder(
                consulta, channel, reminder_template['id']
            )
            send_single_message_task.delay(message_id)
            queued += 1

    if queued:
        audit_log(
            action='appointment_reminders_queued',
            module='comunicacao',
            details={'total_queued': queued},
        )
    return {'total_queued': queued}
