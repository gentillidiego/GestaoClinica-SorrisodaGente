from celery_app import celery
from services.google_drive_service import get_drive_service, ensure_patient_drive_folder
import os
import time
from services.security_service import audit_log

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
    cache_dir = os.path.join('uploads', 'cache', 'gdrive')
    if not os.path.exists(cache_dir):
        return
        
    now = time.time()
    # 2 hours TTL (7200 seconds)
    ttl_seconds = 2 * 3600
    
    for filename in os.listdir(cache_dir):
        file_path = os.path.join(cache_dir, filename)
        if os.path.isfile(file_path):
            stat = os.stat(file_path)
            # Use atime (last access time) to keep files if they are frequently accessed
            if now - stat.st_atime > ttl_seconds:
                try:
                    os.remove(file_path)
                except Exception:
                    pass
