import io
import json

import services.google_drive_service as drive_service


class FakeRequest:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class FakeFiles:
    def __init__(self):
        self.created = []
        self.updated = []
        self.list_payloads = []
        self.list_results = []

    def list(self, **kwargs):
        self.list_payloads.append(kwargs)
        return FakeRequest({'files': self.list_results})

    def create(self, body=None, **kwargs):
        self.created.append({'body': body, 'kwargs': kwargs})
        return FakeRequest({
            'id': f"folder-{len(self.created)}",
            'name': body['name'],
            'webViewLink': f"https://drive.test/{len(self.created)}",
        })

    def update(self, **kwargs):
        self.updated.append(kwargs)
        return FakeRequest({
            'id': kwargs['fileId'],
            'name': 'gso-laudo-301-hemograma.pdf',
            'webViewLink': 'https://drive.test/existing-file',
        })


class FakePermissions:
    def __init__(self):
        self.created = []
        self.updated = []
        self.list_payloads = []

    def list(self, **kwargs):
        self.list_payloads.append(kwargs)
        return FakeRequest({'permissions': []})

    def create(self, body=None, **kwargs):
        self.created.append({'body': body, 'kwargs': kwargs})
        return FakeRequest({
            'id': 'permission-1',
            'type': body['type'],
            'role': body['role'],
            'emailAddress': body['emailAddress'],
        })

    def update(self, body=None, **kwargs):
        self.updated.append({'body': body, 'kwargs': kwargs})
        return FakeRequest({
            'id': kwargs['permissionId'],
            'type': 'user',
            'role': body['role'],
            'emailAddress': 'sorrisodagentealagoas@gmail.com',
        })


class FakeDrive:
    def __init__(self):
        self._files = FakeFiles()
        self._permissions = FakePermissions()

    def files(self):
        return self._files

    def permissions(self):
        return self._permissions


def test_build_patient_folder_name_uses_cpf_and_sanitized_name():
    folder_name = drive_service.build_patient_folder_name({
        'id': 42,
        'cpf': '000.111.222-33',
        'nome': 'Maria / Souza',
    })

    assert folder_name == '000.111.222-33 - Maria Souza'


def test_ensure_patient_drive_folder_creates_and_persists(monkeypatch):
    fake_drive = FakeDrive()
    persisted = []
    monkeypatch.setenv('GDRIVE_UPLOAD_MODE', 'service_account')

    monkeypatch.setattr(
        drive_service,
        'query',
        lambda *args, **kwargs: {
            'id': 42,
            'cpf': '000.111.222-33',
            'nome': 'Maria Souza',
            'gdrive_folder_id': None,
        },
    )
    monkeypatch.setattr(drive_service, 'execute', lambda sql, params=(): persisted.append((sql, params)))
    monkeypatch.setenv('GDRIVE_ROOT_FOLDER_ID', 'root-prontuarios')

    folder = drive_service.ensure_patient_drive_folder(42, service=fake_drive)

    assert folder['id'] == 'folder-1'
    assert folder['name'] == '000.111.222-33 - Maria Souza'
    assert folder['created'] is True
    assert persisted[0][1] == ('folder-1', 42)
    assert fake_drive._files.created[0]['body']['parents'] == ['root-prontuarios']


def test_ensure_patient_drive_folder_reuses_stored_id(monkeypatch):
    fake_drive = FakeDrive()

    monkeypatch.setattr(
        drive_service,
        'query',
        lambda *args, **kwargs: {
            'id': 42,
            'cpf': '000.111.222-33',
            'nome': 'Maria Souza',
            'gdrive_folder_id': 'existing-folder',
        },
    )

    folder = drive_service.ensure_patient_drive_folder(42, service=fake_drive)

    assert folder == {
        'id': 'existing-folder',
        'name': '000.111.222-33 - Maria Souza',
        'created': False,
        'stored': True,
    }
    assert fake_drive._files.created == []


def test_ensure_user_permission_creates_permission():
    fake_drive = FakeDrive()

    permission = drive_service.ensure_user_permission(
        fake_drive,
        'folder-1',
        'SorrisodaGenteAlagoas@gmail.com',
        role='writer',
    )

    assert permission['created'] is True
    assert permission['role'] == 'writer'
    assert permission['emailAddress'] == 'sorrisodagentealagoas@gmail.com'
    assert fake_drive._permissions.created[0]['kwargs']['fileId'] == 'folder-1'
    assert fake_drive._permissions.created[0]['kwargs']['sendNotificationEmail'] is False


def test_rclone_upload_uses_oauth_owner_and_returns_drive_id(monkeypatch):
    calls = []

    def fake_run(arguments, **kwargs):
        calls.append(arguments)
        if arguments[0] == 'lsjson':
            return json.dumps({
                'ID': 'oauth-file-1',
                'Name': arguments[1].split(':', 1)[1],
                'MimeType': 'image/jpeg',
            })
        return ''

    monkeypatch.setenv('GDRIVE_UPLOAD_MODE', 'rclone')
    monkeypatch.setattr(drive_service, '_run_rclone', fake_run)
    uploaded = drive_service.upload_file_in_memory(
        FakeDrive(),
        io.BytesIO(b'image-content'),
        'imagem.jpg',
        'image/jpeg',
        'patient-folder-1',
    )

    assert uploaded['id'] == 'oauth-file-1'
    assert uploaded['rclone_parent_id'] == 'patient-folder-1'
    assert uploaded['rclone_filename'].endswith('_imagem.jpg')
    assert calls[0][0] == 'copyto'
    assert '--drive-root-folder-id' in calls[0]
    assert calls[0][calls[0].index('--drive-root-folder-id') + 1] == 'patient-folder-1'


def test_rclone_upload_uses_deterministic_name_for_async_retry(monkeypatch):
    calls = []

    def fake_run(arguments, **kwargs):
        calls.append(arguments)
        if arguments[0] == 'lsjson':
            return json.dumps({
                'ID': 'oauth-file-async',
                'Name': 'gso-laudo-301-hemograma.pdf',
                'MimeType': 'application/pdf',
            })
        return ''

    monkeypatch.setenv('GDRIVE_UPLOAD_MODE', 'rclone')
    monkeypatch.setattr(drive_service, '_run_rclone', fake_run)

    uploaded = drive_service.upload_file_in_memory(
        FakeDrive(),
        io.BytesIO(b'%PDF-1.7'),
        'hemograma.pdf',
        'application/pdf',
        'patient-folder-1',
        remote_filename='gso-laudo-301-hemograma.pdf',
    )

    assert uploaded['id'] == 'oauth-file-async'
    assert uploaded['rclone_filename'] == 'gso-laudo-301-hemograma.pdf'
    assert calls[0][2] == 'sorriso.drive:gso-laudo-301-hemograma.pdf'


def test_service_account_retry_updates_deterministic_existing_file(monkeypatch):
    fake_drive = FakeDrive()
    fake_drive._files.list_results = [{
        'id': 'existing-drive-file',
        'name': 'gso-laudo-301-hemograma.pdf',
        'mimeType': 'application/pdf',
    }]
    monkeypatch.setenv('GDRIVE_UPLOAD_MODE', 'service_account')
    monkeypatch.setattr(
        drive_service,
        'MediaIoBaseUpload',
        lambda stream, mimetype, resumable: {
            'stream': stream,
            'mimetype': mimetype,
            'resumable': resumable,
        },
    )

    uploaded = drive_service.upload_file_in_memory(
        fake_drive,
        io.BytesIO(b'%PDF-1.7'),
        'hemograma.pdf',
        'application/pdf',
        'patient-folder-1',
        remote_filename='gso-laudo-301-hemograma.pdf',
    )

    assert uploaded['id'] == 'existing-drive-file'
    assert fake_drive._files.created == []
    assert fake_drive._files.updated[0]['fileId'] == 'existing-drive-file'


def test_rclone_delete_uses_original_uploaded_path(monkeypatch):
    calls = []
    monkeypatch.setenv('GDRIVE_UPLOAD_MODE', 'rclone')
    monkeypatch.setattr(
        drive_service,
        '_run_rclone',
        lambda arguments, **kwargs: calls.append(arguments) or '',
    )

    drive_service.delete_file(
        FakeDrive(),
        'oauth-file-1',
        parent_id='patient-folder-1',
        filename='unique_imagem.jpg',
    )

    assert calls == [[
        'deletefile',
        'sorriso.drive:unique_imagem.jpg',
        '--drive-root-folder-id',
        'patient-folder-1',
    ]]


def test_patient_folder_is_created_by_oauth_owner(monkeypatch):
    fake_drive = FakeDrive()
    persisted = []
    folder_calls = []
    monkeypatch.setenv('GDRIVE_UPLOAD_MODE', 'rclone')
    monkeypatch.setenv('GDRIVE_ROOT_FOLDER_ID', 'root-prontuarios')
    monkeypatch.setattr(
        drive_service,
        'query',
        lambda *args, **kwargs: {
            'id': 42,
            'cpf': '000.111.222-33',
            'nome': 'Maria Souza',
            'gdrive_folder_id': None,
        },
    )
    monkeypatch.setattr(
        drive_service,
        'execute',
        lambda sql, params=(): persisted.append((sql, params)),
    )
    monkeypatch.setattr(
        drive_service,
        'ensure_rclone_folder',
        lambda name, parent_id: folder_calls.append((name, parent_id)) or {
            'id': 'oauth-folder-1',
            'name': name,
            'created': True,
            'webViewLink': 'https://drive.test/oauth-folder-1',
        },
    )

    folder = drive_service.ensure_patient_drive_folder(42, service=fake_drive)

    assert folder['id'] == 'oauth-folder-1'
    assert folder['created'] is True
    assert folder_calls == [
        ('000.111.222-33 - Maria Souza', 'root-prontuarios')
    ]
    assert persisted[0][1] == ('oauth-folder-1', 42)
    assert fake_drive._files.created == []
