#!/usr/bin/env python3
import argparse
import io
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / '.env')

from services.google_drive_service import (  # noqa: E402
    GoogleDriveConfigError,
    GoogleDriveOperationError,
    ensure_patient_drive_folder,
    delete_file,
    get_drive_service,
    get_google_drive_auth_mode,
    get_patients_root_folder,
    get_service_account_email,
    upload_file_in_memory,
)


def main():
    parser = argparse.ArgumentParser(description='Valida conexão do Google Drive e pastas de prontuário.')
    parser.add_argument('--patient-id', type=int, help='ID do paciente para criar/obter a pasta no Drive.')
    parser.add_argument(
        '--read-only',
        action='store_true',
        help='Valida somente leitura. Por padrão também testa upload, download e remoção.',
    )
    args = parser.parse_args()

    try:
        email = get_service_account_email()
        service = get_drive_service()
        root_folder = get_patients_root_folder(service)
        root_metadata = service.files().get(
            fileId=root_folder['id'],
            fields='id,name,owners(emailAddress)',
            supportsAllDrives=True,
        ).execute()
        print(f'Service Account: {email}')
        print(f'Modo de upload: {get_google_drive_auth_mode()}')
        print(f'Conta OAuth: {os.getenv("GDRIVE_OAUTH_EMAIL") or "não informada"}')
        owners = ', '.join(
            owner.get('emailAddress', '')
            for owner in root_metadata.get('owners', [])
            if owner.get('emailAddress')
        )
        print(f'Proprietária da pasta raiz: {owners or "não identificada"}')
        print(f'Pasta raiz de prontuários: {root_folder["name"]} ({root_folder["id"]})')

        target_folder = root_folder
        if args.patient_id:
            patient_folder = ensure_patient_drive_folder(args.patient_id, service=service)
            action = 'criada' if patient_folder.get('created') else 'encontrada'
            print(f'Pasta do paciente {action}: {patient_folder["name"]} ({patient_folder["id"]})')
            if patient_folder.get('webViewLink'):
                print(f'Link: {patient_folder["webViewLink"]}')
            target_folder = patient_folder

        if not args.read_only:
            test_filename = f'.gso-write-test-{uuid.uuid4().hex[:8]}.txt'
            uploaded = upload_file_in_memory(
                service,
                io.BytesIO(b'GestaoSaudeOral Google Drive write test'),
                test_filename,
                'text/plain',
                target_folder['id'],
            )
            downloaded = service.files().get_media(fileId=uploaded['id']).execute()
            if downloaded != b'GestaoSaudeOral Google Drive write test':
                raise GoogleDriveOperationError(
                    'O arquivo de teste foi enviado, mas o conteúdo lido divergiu.'
                )
            delete_file(
                service,
                uploaded['id'],
                parent_id=target_folder['id'],
                filename=uploaded.get('rclone_filename') or test_filename,
            )
            print(f'Escrita/leitura/remoção: OK ({uploaded["id"]})')
    except (GoogleDriveConfigError, GoogleDriveOperationError) as exc:
        print(f'ERRO: {exc}', file=sys.stderr)
        return 1

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
