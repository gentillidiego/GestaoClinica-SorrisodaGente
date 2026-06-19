import io
import os
from types import SimpleNamespace

import pytest
from werkzeug.datastructures import FileStorage

import services.exam_file_sync_service as sync_service


def make_upload(filename='resultado.pdf', content=b'%PDF-1.7 staged'):
    return FileStorage(
        stream=io.BytesIO(content),
        filename=filename,
        content_type='application/pdf',
    )


def test_stage_uploaded_file_is_atomic_private_and_removable(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_service, 'STAGING_ROOT', tmp_path / 'staging')

    staged_path = sync_service.stage_uploaded_file(
        make_upload(),
        'clinical_lab',
        patient_id=9,
        exam_id=88,
        filename='resultado.pdf',
    )

    assert os.path.isfile(staged_path)
    assert open(staged_path, 'rb').read() == b'%PDF-1.7 staged'
    assert oct(os.stat(staged_path).st_mode & 0o777) == '0o640'
    assert not list((tmp_path / 'staging').rglob('*.part'))
    assert sync_service.remove_staged_file(staged_path) is True
    assert not os.path.exists(staged_path)


def test_remove_staged_file_refuses_path_outside_staging(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_service, 'STAGING_ROOT', tmp_path / 'staging')
    outside = tmp_path / 'outside.pdf'
    outside.write_bytes(b'keep')

    assert sync_service.remove_staged_file(str(outside)) is False
    assert outside.exists()


def test_sync_staged_exam_file_updates_drive_then_deletes_local(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_service, 'STAGING_ROOT', tmp_path / 'staging')
    local_path = sync_service.stage_uploaded_file(
        make_upload(),
        'clinical_lab',
        patient_id=9,
        exam_id=88,
        filename='hemograma.pdf',
    )
    state = {
        'id': 301,
        'exam_id': 88,
        'patient_id': 9,
        'filename': 'hemograma.pdf',
        'file_path': local_path,
        'staging_path': local_path,
        'storage_status': 'pending',
        'storage_error': None,
        'sync_attempts': 0,
        'storage_updated_at': None,
        'synced_at': None,
    }
    uploads = []
    promoted = []

    monkeypatch.setattr(
        sync_service,
        'get_exam_file_sync_record',
        lambda source, record_id: dict(state),
    )
    monkeypatch.setattr(sync_service, '_claim_record', lambda source, record_id: True)
    monkeypatch.setattr(sync_service, 'get_drive_service', lambda: object())
    monkeypatch.setattr(
        sync_service,
        'ensure_patient_drive_folder',
        lambda patient_id, service: {'id': 'patient-folder-9'},
    )

    def fake_upload(**kwargs):
        uploads.append(kwargs)
        return {'id': 'drive-file-301'}

    def fake_execute(sql, params=()):
        if 'SET file_path = %s' in sql:
            state['file_path'] = params[0]
            state['storage_status'] = 'synced'
        if 'SET staging_path = NULL' in sql:
            state['staging_path'] = None
        return None

    monkeypatch.setattr(sync_service, 'upload_file_in_memory', fake_upload)
    monkeypatch.setattr(sync_service, 'execute', fake_execute)
    monkeypatch.setattr(
        sync_service,
        'promote_staging_to_cache',
        lambda path, drive_id: promoted.append((path, drive_id)) or '/cache/drive-file-301',
    )

    result = sync_service.sync_staged_exam_file('clinical_lab', 301)

    assert result['status'] == 'synced'
    assert state['file_path'] == 'gdrive://drive-file-301'
    assert state['staging_path'] is None
    assert os.path.exists(local_path)
    assert uploads[0]['parent_id'] == 'patient-folder-9'
    assert uploads[0]['remote_filename'] == 'gso-laudo-301-hemograma.pdf'
    assert promoted == [(local_path, 'drive-file-301')]


def test_sync_failure_keeps_local_file_and_marks_retryable(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_service, 'STAGING_ROOT', tmp_path / 'staging')
    local_path = sync_service.stage_uploaded_file(
        make_upload(),
        'exam_image',
        patient_id=9,
        exam_id=77,
        filename='imagem.jpg',
    )
    record = {
        'id': 101,
        'exam_id': 77,
        'patient_id': 9,
        'filename': 'imagem.jpg',
        'file_path': local_path,
        'staging_path': local_path,
        'storage_status': 'pending',
    }
    failures = []

    monkeypatch.setattr(
        sync_service,
        'get_exam_file_sync_record',
        lambda source, record_id: dict(record),
    )
    monkeypatch.setattr(sync_service, '_claim_record', lambda source, record_id: True)
    monkeypatch.setattr(
        sync_service,
        'get_drive_service',
        lambda: (_ for _ in ()).throw(RuntimeError('Drive indisponível')),
    )
    monkeypatch.setattr(
        sync_service,
        '_mark_sync_failed',
        lambda source, record_id, exc: failures.append((source, record_id, str(exc))),
    )

    with pytest.raises(RuntimeError, match='Drive indisponível'):
        sync_service.sync_staged_exam_file('exam_image', 101)

    assert os.path.exists(local_path)
    assert failures == [('exam_image', 101, 'Drive indisponível')]
