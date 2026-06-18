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
    from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
except ImportError:  # pragma: no cover - exercised only when dependency is absent
    service_account = None
    build = None
    MediaIoBaseUpload = None
    MediaIoBaseDownload = None
    HttpError = Exception
    
import io


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


def ensure_user_permission(service, file_id, email, role='writer'):
    email = str(email or '').strip().lower()
    if not email:
        raise GoogleDriveOperationError('E-mail para compartilhamento do Google Drive não informado.')

    try:
        response = service.permissions().list(
            fileId=file_id,
            fields='permissions(id, type, role, emailAddress)',
            supportsAllDrives=True,
        ).execute()
    except HttpError as exc:
        raise GoogleDriveOperationError(f'Falha ao consultar permissões no Google Drive: {exc}') from exc

    for permission in response.get('permissions', []):
        if permission.get('type') == 'user' and str(permission.get('emailAddress', '')).lower() == email:
            if permission.get('role') == role:
                return {**permission, 'created': False, 'updated': False}
            try:
                updated = service.permissions().update(
                    fileId=file_id,
                    permissionId=permission['id'],
                    body={'role': role},
                    fields='id, type, role, emailAddress',
                    supportsAllDrives=True,
                ).execute()
                return {**updated, 'created': False, 'updated': True}
            except HttpError as exc:
                raise GoogleDriveOperationError(f'Falha ao atualizar permissão no Google Drive: {exc}') from exc

    try:
        created = service.permissions().create(
            fileId=file_id,
            body={'type': 'user', 'role': role, 'emailAddress': email},
            fields='id, type, role, emailAddress',
            sendNotificationEmail=False,
            supportsAllDrives=True,
        ).execute()
        return {**created, 'created': True, 'updated': False}
    except HttpError as exc:
        raise GoogleDriveOperationError(f'Falha ao compartilhar pasta no Google Drive: {exc}') from exc


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


def upload_file_in_memory(service, file_stream, filename, mime_type, parent_id):
    """
    Faz o upload de um arquivo para o Google Drive diretamente da memória.
    """
    media = MediaIoBaseUpload(file_stream, mimetype=mime_type, resumable=True)
    metadata = {
        'name': filename,
        'parents': [parent_id]
    }
    
    try:
        file = service.files().create(
            body=metadata,
            media_body=media,
            fields='id, name, webViewLink, webContentLink',
            supportsAllDrives=True
        ).execute()
        return file
    except HttpError as exc:
        raise GoogleDriveOperationError(f'Falha ao fazer upload do arquivo para o Google Drive: {exc}') from exc


def download_file_in_memory(service, file_id):
    """
    Faz o download de um arquivo do Google Drive para a memória usando cache local.
    Retorna os bytes do arquivo.
    """
    import os
    import time
    
    cache_dir = os.path.join('uploads', 'cache', 'gdrive')
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, file_id)

    # Verifica se existe no cache local
    if os.path.exists(cache_path):
        # Atualiza o timestamp de acesso para o TTL estender a vida útil do arquivo
        os.utime(cache_path, None)
        with open(cache_path, 'rb') as f:
            return f.read()

    # Se não tiver no cache, busca no Drive
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    try:
        while done is False:
            status, done = downloader.next_chunk()
        file_bytes = fh.getvalue()
        
        # Salva no cache para acessos futuros
        with open(cache_path, 'wb') as f:
            f.write(file_bytes)
            
        return file_bytes
    except HttpError as exc:
        raise GoogleDriveOperationError(f'Falha ao fazer download do arquivo do Google Drive: {exc}') from exc

