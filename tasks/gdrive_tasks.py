from celery_app import celery
from services.google_drive_service import get_drive_service, ensure_patient_drive_folder
from services.security_service import audit_log
from services.exam_file_sync_service import (
    reconcile_staged_exam_files,
    sync_staged_exam_file,
)
from services.protected_file_delivery_service import cleanup_drive_cache

@celery.task(name='tasks.gdrive_tasks.create_patient_gdrive_folder_task', ignore_result=True)
def create_patient_gdrive_folder_task(patient_id):
    try:
        service = get_drive_service()
        ensure_patient_drive_folder(patient_id, service)
    except Exception as e:
        audit_log(
            action='gdrive_folder_creation_failed',
            module='gdrive',
            patient_id=patient_id,
            status='failed',
            details={'error': str(e)}
        )

@celery.task(name='tasks.gdrive_tasks.cleanup_gdrive_cache_task', ignore_result=True)
def cleanup_gdrive_cache_task():
    return cleanup_drive_cache()


@celery.task(
    bind=True,
    name='tasks.gdrive_tasks.sync_staged_exam_file_task',
    max_retries=8,
    acks_late=True,
    reject_on_worker_lost=True,
)
def sync_staged_exam_file_task(self, source, record_id):
    try:
        return sync_staged_exam_file(source, record_id)
    except FileNotFoundError as exc:
        return {
            'status': 'failed_missing_local_file',
            'source': source,
            'record_id': record_id,
            'error': str(exc),
        }
    except Exception as exc:
        countdown = min(30 * (2 ** self.request.retries), 1800)
        raise self.retry(exc=exc, countdown=countdown)


@celery.task(
    name='tasks.gdrive_tasks.reconcile_staged_exam_files_task',
    ignore_result=True,
)
def reconcile_staged_exam_files_task():
    return reconcile_staged_exam_files()
