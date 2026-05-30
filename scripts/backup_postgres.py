#!/usr/bin/env python3
import argparse
import datetime as dt
import os
import shutil
import subprocess
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


def run(command):
    subprocess.run(command, check=True)


def create_backup(output_dir):
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise RuntimeError('DATABASE_URL não está definida.')

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    dump_file = output_path / f'gestao_saude_oral_{timestamp}.dump'

    run([
        'pg_dump',
        '--format=custom',
        '--no-owner',
        '--no-privileges',
        '--file',
        str(dump_file),
        database_url,
    ])

    uploads_dir = Path('uploads')
    if uploads_dir.exists():
        shutil.make_archive(str(output_path / f'uploads_{timestamp}'), 'gztar', uploads_dir)

    return dump_file


def prune_old_backups(output_dir, retention_days):
    cutoff = dt.datetime.now() - dt.timedelta(days=retention_days)
    for item in Path(output_dir).glob('*'):
        if not item.is_file():
            continue
        modified = dt.datetime.fromtimestamp(item.stat().st_mtime)
        if modified < cutoff:
            item.unlink()


def main():
    parser = argparse.ArgumentParser(description='Backup operacional do Gestão Saúde Oral.')
    parser.add_argument(
        '--output-dir',
        default=os.getenv('BACKUP_DIR', 'backups'),
        help='Diretório local para armazenar os backups.'
    )
    parser.add_argument(
        '--retention-days',
        type=int,
        default=int(os.getenv('BACKUP_RETENTION_DAYS', '30')),
        help='Quantidade de dias para manter backups locais.'
    )
    args = parser.parse_args()

    dump_file = create_backup(args.output_dir)
    prune_old_backups(args.output_dir, args.retention_days)
    print(f'Backup criado com sucesso: {dump_file}')


if __name__ == '__main__':
    main()
