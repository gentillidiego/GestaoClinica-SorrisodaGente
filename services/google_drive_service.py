import json
import os
import re
from functools import lru_cache
from pathlib import Path

from database import execute, query

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:  # pragma: no cover - exercised only when dependency is absent
    service_account = None
    build = None
    HttpError = Exception


DRIVE_FOLDER_MIME_TYPE = 'application/vnd.google-apps.folder'
DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive']
DEFAULT_PATIENTS_FOLDER_NAME = 'Prontuários'


class GoogleDriveConfigError(RuntimeError):
    pass


class GoogleDriveOperationError(RuntimeError):
    pass


def _require_google_dependencies():
    if service_account is None or build is None:
        raise GoogleDriveConfigError(
            'Dependências do Google Drive não instaladas. '
            'Execute pip install -r requirements.txt e reconstrua o Docker.'
        )


def _key_path():
    path = os.getenv('GDRIVE_KEY_PATH', '').strip()
    if not path:
        raise GoogleDriveConfigError('GDRIVE_KEY_PATH não está definido.')
    if not Path(path).is_file():
        raise GoogleDriveConfigError(f'Arquivo de credenciais Google Drive não encontrado: {path}')
    return path


def get_service_account_email(key_path=None):
    path = key_path or _key_path()
    with open(path, 'r', encoding='utf-8') as file_obj:
        payload = json.load(file_obj)
    return payload.get('client_email')


@lru_cache(maxsize=1)
def get_drive_service():
    _require_google_dependencies()
    credentials = service_account.Credentials.from_service_account_file(
        _key_path(),
        scopes=DRIVE_SCOPES,
    )
    return build('drive', 'v3', credentials=credentials, cache_discovery=False)


def _drive_name(value):
    cleaned = re.sub(r'[\x00-\x1f/\\]+', ' ', str(value or '')).strip()
    return re.sub(r'\s+', ' ', cleaned)[:180] or 'Sem nome'


def _escape_query_value(value):
    return str(value or '').replace('\\', '\\\\').replace("'", "\\'")


def build_patient_folder_name(patient):
    cpf = _drive_name(patient.get('cpf') or f"SEM-CPF-{patient.get('id')}")
    name = _drive_name(patient.get('nome'))
    return f"{cpf} - {name}"


def _folder_query(name, parent_id=None):
    clauses = [
        f"name = '{_escape_query_value(name)}'",
        f"mimeType = '{DRIVE_FOLDER_MIME_TYPE}'",
        'trashed = false',
    ]
    if parent_id:
        clauses.append(f"'{_escape_query_value(parent_id)}' in parents")
    return ' and '.join(clauses)


def find_folder(service, name, parent_id=None):
    try:
        response = service.files().list(
            q=_folder_query(name, parent_id),
            spaces='drive',
            fields='files(id, name, webViewLink)',
            pageSize=1,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
    except HttpError as exc:
        raise GoogleDriveOperationError(f'Falha ao consultar pasta no Google Drive: {exc}') from exc

    folders = response.get('files', [])
    return folders[0] if folders else None


def create_folder(service, name, parent_id=None):
    metadata = {
        'name': _drive_name(name),
        'mimeType': DRIVE_FOLDER_MIME_TYPE,
    }
    if parent_id:
        metadata['parents'] = [parent_id]

    try:
        return service.files().create(
            body=metadata,
            fields='id, name, webViewLink',
            supportsAllDrives=True,
        ).execute()
    except HttpError as exc:
        raise GoogleDriveOperationError(f'Falha ao criar pasta no Google Drive: {exc}') from exc


def ensure_folder(service, name, parent_id=None):
    existing = find_folder(service, name, parent_id=parent_id)
    if existing:
        return existing
    return create_folder(service, name, parent_id=parent_id)


def get_patients_root_folder(service=None):
    service = service or get_drive_service()
    configured_folder_id = os.getenv('GDRIVE_ROOT_FOLDER_ID', '').strip()
    if configured_folder_id:
        return {'id': configured_folder_id, 'name': os.getenv('GDRIVE_PATIENTS_FOLDER_NAME', DEFAULT_PATIENTS_FOLDER_NAME)}

    folder_name = os.getenv('GDRIVE_PATIENTS_FOLDER_NAME', DEFAULT_PATIENTS_FOLDER_NAME).strip() or DEFAULT_PATIENTS_FOLDER_NAME
    return ensure_folder(service, folder_name)


def ensure_patient_drive_folder(patient_id, service=None):
    patient = query(
        """
        SELECT id, nome, cpf, gdrive_folder_id
        FROM patients
        WHERE id = %s
        """,
        (patient_id,),
        one=True,
    )
    if not patient:
        raise GoogleDriveOperationError('Paciente não encontrado.')

    if patient.get('gdrive_folder_id'):
        return {
            'id': patient['gdrive_folder_id'],
            'name': build_patient_folder_name(patient),
            'created': False,
            'stored': True,
        }

    service = service or get_drive_service()
    root_folder = get_patients_root_folder(service)
    folder_name = build_patient_folder_name(patient)
    existing = find_folder(service, folder_name, parent_id=root_folder['id'])

    created = False
    folder = existing
    if not folder:
        folder = create_folder(service, folder_name, parent_id=root_folder['id'])
        created = True

    execute(
        """
        UPDATE patients
        SET gdrive_folder_id = %s
        WHERE id = %s
        """,
        (folder['id'], patient_id),
    )
    return {
        'id': folder['id'],
        'name': folder.get('name') or folder_name,
        'webViewLink': folder.get('webViewLink'),
        'created': created,
        'stored': False,
        'root_folder_id': root_folder['id'],
    }
