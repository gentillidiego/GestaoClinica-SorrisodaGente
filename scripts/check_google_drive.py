#!/usr/bin/env python3
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / '.env')

from services.google_drive_service import (  # noqa: E402
    GoogleDriveConfigError,
    GoogleDriveOperationError,
    ensure_patient_drive_folder,
    get_drive_service,
    get_patients_root_folder,
    get_service_account_email,
)


def main():
    parser = argparse.ArgumentParser(description='Valida conexão do Google Drive e pastas de prontuário.')
    parser.add_argument('--patient-id', type=int, help='ID do paciente para criar/obter a pasta no Drive.')
    args = parser.parse_args()

    try:
        email = get_service_account_email()
        service = get_drive_service()
        root_folder = get_patients_root_folder(service)
        print(f'Service Account: {email}')
        print(f'Pasta raiz de prontuários: {root_folder["name"]} ({root_folder["id"]})')

        if args.patient_id:
            patient_folder = ensure_patient_drive_folder(args.patient_id, service=service)
            action = 'criada' if patient_folder.get('created') else 'encontrada'
            print(f'Pasta do paciente {action}: {patient_folder["name"]} ({patient_folder["id"]})')
            if patient_folder.get('webViewLink'):
                print(f'Link: {patient_folder["webViewLink"]}')
    except (GoogleDriveConfigError, GoogleDriveOperationError) as exc:
        print(f'ERRO: {exc}', file=sys.stderr)
        return 1

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
