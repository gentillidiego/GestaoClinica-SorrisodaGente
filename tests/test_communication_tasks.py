import sys
import types
from types import SimpleNamespace


class _FakeCelery:
    def task(self, *args, **kwargs):
        def decorator(func):
            func.delay = lambda *call_args, **call_kwargs: SimpleNamespace(id='test-task')
            return func
        return decorator


fake_celery_app = types.ModuleType('celery_app')
fake_celery_app.celery = _FakeCelery()
sys.modules.setdefault('celery_app', fake_celery_app)

import tasks.communication_tasks as communication_tasks


def test_send_campaign_task_enqueues_each_message(monkeypatch):
    monkeypatch.setattr(
        communication_tasks, 'enqueue_campaign_messages', lambda campaign_id: [1, 2, 3],
    )
    delayed = []
    monkeypatch.setattr(
        communication_tasks.send_single_message_task, 'delay',
        lambda message_id: delayed.append(message_id),
        raising=False,
    )

    result = communication_tasks.send_campaign_task(42)

    assert delayed == [1, 2, 3]
    assert result == {'campaign_id': 42, 'total_queued': 3}


def test_send_appointment_reminders_task_disabled_by_default(monkeypatch):
    monkeypatch.delenv('APPOINTMENT_REMINDERS_ENABLED', raising=False)
    result = communication_tasks.send_appointment_reminders_task()
    assert result == {'status': 'disabled'}


def test_send_appointment_reminders_task_queues_for_configured_channels(monkeypatch):
    monkeypatch.setenv('APPOINTMENT_REMINDERS_ENABLED', 'true')
    monkeypatch.setattr(communication_tasks, 'channel_available', lambda channel: channel == 'email')
    monkeypatch.setattr(
        communication_tasks, 'list_templates',
        lambda channel, active_only=False: [
            {'id': 9, 'category': 'lembrete_consulta', 'channel': 'email'},
        ],
    )
    monkeypatch.setattr(
        communication_tasks, 'find_consultas_pending_reminder',
        lambda channel, hours_ahead=48: [{'consulta_id': 1, 'patient_id': 2}],
    )
    monkeypatch.setattr(
        communication_tasks, 'enqueue_appointment_reminder',
        lambda consulta, channel, template_id: 555,
    )
    queued = []
    monkeypatch.setattr(
        communication_tasks.send_single_message_task, 'delay',
        lambda message_id: queued.append(message_id),
        raising=False,
    )
    audited = []
    monkeypatch.setattr(communication_tasks, 'audit_log', lambda **kwargs: audited.append(kwargs))

    result = communication_tasks.send_appointment_reminders_task()

    assert queued == [555]
    assert result == {'total_queued': 1}
    assert audited[0]['details']['total_queued'] == 1


def test_send_appointment_reminders_task_skips_channel_without_template(monkeypatch):
    monkeypatch.setenv('APPOINTMENT_REMINDERS_ENABLED', 'true')
    monkeypatch.setattr(communication_tasks, 'channel_available', lambda channel: True)
    monkeypatch.setattr(
        communication_tasks, 'list_templates',
        lambda channel, active_only=False: [],
    )

    def fail_find(*args, **kwargs):
        raise AssertionError('não deveria buscar consultas sem template de lembrete')

    monkeypatch.setattr(communication_tasks, 'find_consultas_pending_reminder', fail_find)

    result = communication_tasks.send_appointment_reminders_task()

    assert result == {'total_queued': 0}
