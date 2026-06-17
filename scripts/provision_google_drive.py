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
    DEFAULT_PATIENTS_FOLDER_NAME,
    GoogleDriveConfigError,
    GoogleDriveOperationError,
    ensure_folder,
    ensure_user_permission,
    get_drive_service,
    get_service_account_email,
)


def main():
    parser = argparse.ArgumentParser(
        description='Provisiona a pasta raiz de prontuários no Google Drive usando Service Account.'
    )
    parser.add_argument('--folder-name', default=DEFAULT_PATIENTS_FOLDER_NAME)
    parser.add_argument('--share-email', required=True)
    parser.add_argument('--share-role', default='writer', choices=['reader', 'commenter', 'writer'])
    args = parser.parse_args()

    try:
        service_account_email = get_service_account_email()
        service = get_drive_service()
        root_folder = ensure_folder(service, args.folder_name)
        permission = ensure_user_permission(
            service,
            root_folder['id'],
            args.share_email,
            role=args.share_role,
        )
    except (GoogleDriveConfigError, GoogleDriveOperationError) as exc:
        print(f'ERRO: {exc}', file=sys.stderr)
        return 1

    print(f'SERVICE_ACCOUNT_EMAIL={service_account_email}')
    print(f'GDRIVE_ROOT_FOLDER_ID={root_folder["id"]}')
    print(f'GDRIVE_ROOT_FOLDER_NAME={root_folder.get("name", args.folder_name)}')
    print(f'GDRIVE_SHARED_WITH={args.share_email}')
    print(f'GDRIVE_PERMISSION_ROLE={permission.get("role", args.share_role)}')
    print(f'GDRIVE_PERMISSION_CREATED={str(permission.get("created", False)).lower()}')
    print(f'GDRIVE_PERMISSION_UPDATED={str(permission.get("updated", False)).lower()}')
    if root_folder.get('webViewLink'):
        print(f'GDRIVE_ROOT_LINK={root_folder["webViewLink"]}')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
