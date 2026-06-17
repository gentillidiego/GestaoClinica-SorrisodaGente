import services.google_drive_service as drive_service


class FakeRequest:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class FakeFiles:
    def __init__(self):
        self.created = []
        self.list_payloads = []

    def list(self, **kwargs):
        self.list_payloads.append(kwargs)
        return FakeRequest({'files': []})

    def create(self, body=None, **kwargs):
        self.created.append({'body': body, 'kwargs': kwargs})
        return FakeRequest({
            'id': f"folder-{len(self.created)}",
            'name': body['name'],
            'webViewLink': f"https://drive.test/{len(self.created)}",
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
