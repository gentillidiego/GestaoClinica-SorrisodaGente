import logging
import mimetypes
import os
import shutil
import time
import uuid
from pathlib import Path

from database import execute, query
from services.google_drive_service import (
    ensure_patient_drive_folder,
    get_drive_service,
    upload_file_in_memory,
)
from services.protected_file_delivery_service import (
    cleanup_drive_cache,
    ensure_image_derivatives,
    promote_staging_to_cache,
    set_delivery_permissions,
)


logger = logging.getLogger(__name__)

SYNC_SOURCES = {
    'exam_image': {
        'table': 'exam_imagem_arquivos',
        'remote_prefix': 'imagem',
    },
    'clinical_lab': {
        'table': 'exam_clinico_laboratorial_arquivos',
        'remote_prefix': 'laudo',
    },
}

STAGING_ROOT = Path(
    os.getenv('EXAM_FILE_STAGING_DIR', 'uploads/staging/exams')
)
MAX_RECONCILE_ATTEMPTS = int(os.getenv('EXAM_FILE_SYNC_MAX_ATTEMPTS', '100'))


def _source_config(source):
    try:
        return SYNC_SOURCES[source]
    except KeyError as exc:
        raise ValueError(f'Origem de arquivo não suportada: {source}') from exc


def _absolute_staging_path(path):
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    return candidate.resolve()


def is_safe_staging_path(path):
    if not path:
        return False
    try:
        root = _absolute_staging_path(STAGING_ROOT)
        candidate = _absolute_staging_path(path)
        return os.path.commonpath([str(root), str(candidate)]) == str(root)
    except (OSError, ValueError):
        return False


def stage_uploaded_file(file, source, patient_id, exam_id, filename):
    """Grava o arquivo de forma atômica no volume persistente compartilhado."""
    _source_config(source)
    target_dir = (
        STAGING_ROOT
        / source
        / f'patient-{int(patient_id)}'
        / f'exam-{int(exam_id)}'
    )
    target_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(target_dir, 0o700)
    except OSError:
        pass

    suffix = Path(filename).suffix.lower()
    target_path = target_dir / f'{uuid.uuid4().hex}{suffix}'
    temporary_path = target_path.with_suffix(f'{target_path.suffix}.part')
    try:
        file.stream.seek(0)
        with open(temporary_path, 'wb') as output:
            shutil.copyfileobj(file.stream, output, length=1024 * 1024)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, target_path)
        set_delivery_permissions(target_path)
        return str(target_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        target_path.unlink(missing_ok=True)
        raise


def remove_staged_file(path):
    """Remove somente arquivos dentro da raiz de staging configurada."""
    if not is_safe_staging_path(path):
        logger.warning('Recusa ao remover caminho fora do staging: %s', path)
        return False

    absolute_path = _absolute_staging_path(path)
    absolute_path.unlink(missing_ok=True)
    root = _absolute_staging_path(STAGING_ROOT)
    parent = absolute_path.parent
    while parent != root and root in parent.parents:
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent
    return True


def enqueue_exam_file_sync(source, record_id):
    from tasks.gdrive_tasks import sync_staged_exam_file_task

    return sync_staged_exam_file_task.delay(source, int(record_id))


def get_exam_file_sync_record(source, record_id):
    config = _source_config(source)
    return query(
        f"""
        SELECT id, exam_id, patient_id, filename, file_path, staging_path,
               storage_status, storage_error, sync_attempts,
               storage_updated_at, synced_at
        FROM {config['table']}
        WHERE id = %s
          AND COALESCE(active, TRUE) = TRUE
        """,
        (record_id,),
        one=True,
    )


def get_exam_file_sync_status(source, record_id):
    record = get_exam_file_sync_record(source, record_id)
    if not record:
        return None
    status = record.get('storage_status') or (
        'synced' if str(record.get('file_path', '')).startswith('gdrive://') else 'pending'
    )
    labels = {
        'pending': 'Salvo no prontuário · aguardando sincronização',
        'syncing': 'Salvo no prontuário · sincronizando com o Drive',
        'synced': 'Protegido no Google Drive institucional',
        'failed': 'Salvo no prontuário · nova tentativa será automática',
    }
    return {
        'id': record['id'],
        'status': status,
        'label': labels.get(status, labels['pending']),
        'synced_at': record.get('synced_at'),
        'attempts': record.get('sync_attempts') or 0,
    }


def _claim_record(source, record_id):
    config = _source_config(source)
    claimed_id = execute(
        f"""
        UPDATE {config['table']}
        SET storage_status = 'syncing',
            storage_error = NULL,
            sync_attempts = COALESCE(sync_attempts, 0) + 1,
            storage_updated_at = NOW()
        WHERE id = %s
          AND COALESCE(active, TRUE) = TRUE
          AND (
              storage_status IN ('pending', 'failed')
              OR (
                  storage_status = 'syncing'
                  AND storage_updated_at < NOW() - INTERVAL '20 minutes'
              )
          )
        RETURNING id
        """,
        (record_id,),
    )
    return bool(claimed_id)


def _mark_sync_failed(source, record_id, exc):
    config = _source_config(source)
    execute(
        f"""
        UPDATE {config['table']}
        SET storage_status = 'failed',
            storage_error = %s,
            storage_updated_at = NOW()
        WHERE id = %s
        """,
        (str(exc)[-1500:], record_id),
    )


def sync_staged_exam_file(source, record_id):
    """Sincroniza um arquivo local com o Drive e só então remove a cópia local."""
    config = _source_config(source)
    existing = get_exam_file_sync_record(source, record_id)
    if not existing:
        return {'status': 'missing', 'source': source, 'record_id': record_id}

    if str(existing.get('file_path', '')).startswith('gdrive://'):
        staging_path = existing.get('staging_path')
        if staging_path:
            remove_staged_file(staging_path)
            execute(
                f"""
                UPDATE {config['table']}
                SET staging_path = NULL,
                    storage_status = 'synced',
                    storage_error = NULL,
                    storage_updated_at = NOW(),
                    synced_at = COALESCE(synced_at, NOW())
                WHERE id = %s
                """,
                (record_id,),
            )
        return {
            'status': 'already_synced',
            'source': source,
            'record_id': record_id,
        }

    if not _claim_record(source, record_id):
        return {
            'status': 'already_processing',
            'source': source,
            'record_id': record_id,
        }

    record = get_exam_file_sync_record(source, record_id)
    staging_path = record.get('staging_path') or record.get('file_path')
    try:
        if not is_safe_staging_path(staging_path):
            raise RuntimeError('Caminho local do arquivo não pertence ao staging seguro.')
        absolute_path = _absolute_staging_path(staging_path)
        if not absolute_path.is_file():
            raise FileNotFoundError('Arquivo local de staging não encontrado.')

        if source == 'exam_image' or Path(record['filename']).suffix.lower() in {
            '.jpg', '.jpeg', '.png', '.webp'
        }:
            try:
                ensure_image_derivatives(
                    source,
                    record_id,
                    absolute_path,
                )
            except Exception:
                logger.exception(
                    'Falha ao gerar miniatura/prévia de %s #%s',
                    source,
                    record_id,
                )

        service = get_drive_service()
        folder = ensure_patient_drive_folder(record['patient_id'], service)
        mime_type = (
            mimetypes.guess_type(record['filename'])[0]
            or 'application/octet-stream'
        )
        remote_filename = (
            f"gso-{config['remote_prefix']}-{record_id}-{record['filename']}"
        )
        with open(absolute_path, 'rb') as file_stream:
            drive_file = upload_file_in_memory(
                service=service,
                file_stream=file_stream,
                filename=record['filename'],
                mime_type=mime_type,
                parent_id=folder['id'],
                remote_filename=remote_filename,
            )

        execute(
            f"""
            UPDATE {config['table']}
            SET file_path = %s,
                storage_status = 'synced',
                storage_error = NULL,
                storage_updated_at = NOW(),
                synced_at = NOW()
            WHERE id = %s
            """,
            (f"gdrive://{drive_file['id']}", record_id),
        )
        promote_staging_to_cache(staging_path, drive_file['id'])
        execute(
            f"""
            UPDATE {config['table']}
            SET staging_path = NULL,
                storage_updated_at = NOW()
            WHERE id = %s
            """,
            (record_id,),
        )
        return {
            'status': 'synced',
            'source': source,
            'record_id': record_id,
            'drive_file_id': drive_file['id'],
        }
    except Exception as exc:
        _mark_sync_failed(source, record_id, exc)
        raise


def reconcile_staged_exam_files(limit_per_source=100):
    """Reenfileira pendências e recupera arquivos presos após queda de worker."""
    queued = []
    cleaned = []
    for source, config in SYNC_SOURCES.items():
        execute(
            f"""
            UPDATE {config['table']}
            SET storage_status = 'pending',
                storage_error = 'Sincronização anterior interrompida; reenfileirada.',
                storage_updated_at = NOW()
            WHERE storage_status = 'syncing'
              AND storage_updated_at < NOW() - INTERVAL '20 minutes'
            """
        )

        synced_with_staging = query(
            f"""
            SELECT id, staging_path
            FROM {config['table']}
            WHERE storage_status = 'synced'
              AND staging_path IS NOT NULL
            LIMIT %s
            """,
            (limit_per_source,),
        )
        for record in synced_with_staging:
            remove_staged_file(record['staging_path'])
            execute(
                f"""
                UPDATE {config['table']}
                SET staging_path = NULL,
                    storage_updated_at = NOW()
                WHERE id = %s
                """,
                (record['id'],),
            )
            cleaned.append((source, record['id']))

        pending = query(
            f"""
            SELECT id
            FROM {config['table']}
            WHERE storage_status IN ('pending', 'failed')
              AND COALESCE(sync_attempts, 0) < %s
              AND (
                  storage_status = 'pending'
                  OR storage_updated_at < NOW() - INTERVAL '5 minutes'
              )
            ORDER BY data_upload ASC, id ASC
            LIMIT %s
            """,
            (MAX_RECONCILE_ATTEMPTS, limit_per_source),
        )
        for record in pending:
            try:
                enqueue_exam_file_sync(source, record['id'])
                queued.append((source, record['id']))
            except Exception:
                logger.exception(
                    'Falha ao reenfileirar %s #%s',
                    source,
                    record['id'],
                )
    orphaned = cleanup_orphaned_staging_files()
    cache_cleanup = cleanup_drive_cache()
    return {
        'queued': queued,
        'cleaned': cleaned,
        'orphaned': orphaned,
        'cache_cleanup': cache_cleanup,
    }


def cleanup_orphaned_staging_files(grace_seconds=24 * 3600, limit=500):
    """Limpa resíduos sem registro no banco após uma janela ampla de segurança."""
    root = _absolute_staging_path(STAGING_ROOT)
    if not root.exists():
        return []

    referenced = set()
    for config in SYNC_SOURCES.values():
        rows = query(
            f"""
            SELECT staging_path
            FROM {config['table']}
            WHERE staging_path IS NOT NULL
            """
        )
        for row in rows:
            if row.get('staging_path'):
                referenced.add(str(_absolute_staging_path(row['staging_path'])))

    now = time.time()
    removed = []
    for candidate in root.rglob('*'):
        if len(removed) >= limit or not candidate.is_file():
            continue
        candidate_path = str(candidate.resolve())
        if candidate_path in referenced:
            continue
        age = now - candidate.stat().st_mtime
        minimum_age = 3600 if candidate.name.endswith('.part') else grace_seconds
        if age < minimum_age:
            continue
        if remove_staged_file(candidate):
            removed.append(candidate_path)
    return removed
