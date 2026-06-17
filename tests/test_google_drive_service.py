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


class FakeDrive:
    def __init__(self):
        self._files = FakeFiles()

    def files(self):
        return self._files


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
