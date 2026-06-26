import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
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
DEFAULT_RCLONE_REMOTE = 'sorriso.drive'


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


def get_google_drive_auth_mode():
    return os.getenv('GDRIVE_UPLOAD_MODE', 'service_account').strip().lower()


def _rclone_config_path():
    path = os.getenv('GDRIVE_RCLONE_CONFIG', '').strip()
    if not path:
        raise GoogleDriveConfigError(
            'GDRIVE_RCLONE_CONFIG não está definido para o upload OAuth.'
        )
    if not Path(path).is_file():
        raise GoogleDriveConfigError(
            f'Configuração OAuth do rclone não encontrada: {path}'
        )
    return path


def _rclone_remote():
    return (
        os.getenv('GDRIVE_RCLONE_REMOTE', DEFAULT_RCLONE_REMOTE)
        .strip()
        .rstrip(':')
        or DEFAULT_RCLONE_REMOTE
    )


def _run_rclone(arguments, *, timeout=None):
    executable = shutil.which('rclone')
    if not executable:
        raise GoogleDriveConfigError(
            'rclone não está instalado no container da aplicação.'
        )
    command = [
        executable,
        '--config',
        _rclone_config_path(),
        *arguments,
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout or int(os.getenv('GDRIVE_RCLONE_TIMEOUT', '300')),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GoogleDriveOperationError(
            f'Falha ao executar upload OAuth do Google Drive: {exc}'
        ) from exc
    if result.returncode:
        detail = (result.stderr or result.stdout or 'erro não informado').strip()
        raise GoogleDriveOperationError(
            'Falha no upload OAuth do Google Drive via rclone: '
            + detail[-1200:]
        )
    return result.stdout


def _find_rclone_folder(name, parent_id):
    remote_root = f'{_rclone_remote()}:'
    folders = json.loads(
        _run_rclone([
            'lsjson',
            remote_root,
            '--dirs-only',
            '--no-modtime',
            '--no-mimetype',
            '--drive-root-folder-id',
            str(parent_id),
        ])
    )
    safe_name = _drive_name(name)
    for folder in folders:
        if folder.get('Name') == safe_name:
            return {
                'id': folder.get('ID'),
                'name': folder.get('Name'),
                'webViewLink': (
                    f'https://drive.google.com/drive/folders/{folder.get("ID")}'
                    if folder.get('ID')
                    else None
                ),
            }
    return None


def ensure_rclone_folder(name, parent_id):
    """Cria/reutiliza pasta usando o usuário OAuth proprietário do Drive."""
    existing = _find_rclone_folder(name, parent_id)
    if existing:
        return {**existing, 'created': False}

    safe_name = _drive_name(name)
    _run_rclone([
        'mkdir',
        f'{_rclone_remote()}:{safe_name}',
        '--drive-root-folder-id',
        str(parent_id),
    ])
    created = _find_rclone_folder(safe_name, parent_id)
    if not created or not created.get('id'):
        raise GoogleDriveOperationError(
            'Pasta criada, mas o Google Drive não retornou seu identificador.'
        )
    return {**created, 'created': True}


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


def find_file(service, name, parent_id):
    query_text = (
        f"name = '{_escape_query_value(_drive_name(name))}' "
        f"and '{_escape_query_value(parent_id)}' in parents "
        f"and mimeType != '{DRIVE_FOLDER_MIME_TYPE}' "
        "and trashed = false"
    )
    try:
        response = service.files().list(
            q=query_text,
            spaces='drive',
            fields='files(id, name, webViewLink, mimeType)',
            pageSize=1,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
    except HttpError as exc:
        raise GoogleDriveOperationError(
            f'Falha ao consultar arquivo no Google Drive: {exc}'
        ) from exc
    files = response.get('files', [])
    return files[0] if files else None


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


DEFAULT_INVENTORY_INVOICES_FOLDER_NAME = 'Notas Fiscais de Estoque'


def get_inventory_invoices_root_folder(service=None):
    service = service or get_drive_service()
    folder_name = os.getenv(
        'GDRIVE_INVENTORY_FOLDER_NAME', DEFAULT_INVENTORY_INVOICES_FOLDER_NAME
    ).strip() or DEFAULT_INVENTORY_INVOICES_FOLDER_NAME
    return ensure_folder(service, folder_name)


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
    if get_google_drive_auth_mode() == 'rclone':
        folder = ensure_rclone_folder(folder_name, root_folder['id'])
        created = folder['created']
    else:
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


def upload_file_in_memory(
    service,
    file_stream,
    filename,
    mime_type,
    parent_id,
    remote_filename=None,
):
    """
    Faz o upload de um arquivo para o Google Drive diretamente da memória.
    remote_filename torna o envio idempotente para tarefas assíncronas.
    """
    if get_google_drive_auth_mode() == 'rclone':
        safe_filename = _drive_name(filename)
        remote_filename = (
            _drive_name(remote_filename)
            if remote_filename
            else f'{uuid.uuid4().hex}_{safe_filename}'
        )
        suffix = Path(safe_filename).suffix
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
                temporary_path = temporary.name
                file_stream.seek(0)
                shutil.copyfileobj(file_stream, temporary)

            remote_path = f'{_rclone_remote()}:{remote_filename}'
            common_flags = [
                '--drive-root-folder-id',
                str(parent_id),
                '--retries',
                '5',
                '--low-level-retries',
                '10',
                '--stats',
                '0',
            ]
            _run_rclone(['copyto', temporary_path, remote_path, *common_flags])
            uploaded = json.loads(
                _run_rclone([
                    'lsjson',
                    remote_path,
                    '--stat',
                    '--drive-root-folder-id',
                    str(parent_id),
                ])
            )
            file_id = uploaded.get('ID')
            if not file_id:
                raise GoogleDriveOperationError(
                    'Upload concluído, mas o Google Drive não retornou o ID do arquivo.'
                )
            return {
                'id': file_id,
                'name': uploaded.get('Name') or safe_filename,
                'webViewLink': f'https://drive.google.com/file/d/{file_id}/view',
                'mimeType': uploaded.get('MimeType') or mime_type,
                'rclone_parent_id': str(parent_id),
                'rclone_filename': remote_filename,
            }
        finally:
            if temporary_path and os.path.exists(temporary_path):
                os.remove(temporary_path)

    drive_filename = _drive_name(remote_filename or filename)
    media = MediaIoBaseUpload(file_stream, mimetype=mime_type, resumable=True)
    metadata = {
        'name': drive_filename,
        'parents': [parent_id]
    }
    
    try:
        existing = (
            find_file(service, drive_filename, parent_id)
            if remote_filename
            else None
        )
        if existing:
            file_stream.seek(0)
            media = MediaIoBaseUpload(file_stream, mimetype=mime_type, resumable=True)
            return service.files().update(
                fileId=existing['id'],
                media_body=media,
                fields='id, name, webViewLink, webContentLink',
                supportsAllDrives=True,
            ).execute()
        file = service.files().create(
            body=metadata,
            media_body=media,
            fields='id, name, webViewLink, webContentLink',
            supportsAllDrives=True
        ).execute()
        return file
    except HttpError as exc:
        raise GoogleDriveOperationError(f'Falha ao fazer upload do arquivo para o Google Drive: {exc}') from exc


def delete_file(service, file_id, *, parent_id=None, filename=None):
    """Remove arquivo de teste/rollback usando o mesmo proprietário do upload."""
    if (
        get_google_drive_auth_mode() == 'rclone'
        and parent_id
        and filename
    ):
        remote_path = f'{_rclone_remote()}:{_drive_name(filename)}'
        _run_rclone([
            'deletefile',
            remote_path,
            '--drive-root-folder-id',
            str(parent_id),
        ])
        return
    try:
        service.files().delete(
            fileId=file_id,
            supportsAllDrives=True,
        ).execute()
    except HttpError as exc:
        raise GoogleDriveOperationError(
            f'Falha ao remover arquivo do Google Drive: {exc}'
        ) from exc


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


def download_file_to_path(service, file_id, destination_path):
    """Transfere o arquivo do Drive diretamente para disco, sem mantê-lo em RAM."""
    request = service.files().get_media(fileId=file_id)
    try:
        with open(destination_path, 'wb') as output:
            downloader = MediaIoBaseDownload(output, request)
            done = False
            while not done:
                _status, done = downloader.next_chunk()
            output.flush()
            os.fsync(output.fileno())
    except HttpError as exc:
        raise GoogleDriveOperationError(
            f'Falha ao baixar arquivo do Google Drive: {exc}'
        ) from exc
    return str(destination_path)
