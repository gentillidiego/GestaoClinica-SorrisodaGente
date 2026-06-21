#!/usr/bin/env python3
"""Verifica renovação persistente do OAuth do rclone sem exibir credenciais."""

import argparse
import configparser
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def token_expiry(config_path, remote):
    config = configparser.RawConfigParser()
    if not config.read(config_path) or not config.has_section(remote):
        raise RuntimeError(f'Remote não encontrado no arquivo: {remote}')
    raw_token = config.get(remote, 'token', fallback='')
    if not raw_token:
        return None
    try:
        return json.loads(raw_token).get('expiry')
    except json.JSONDecodeError as exc:
        raise RuntimeError('Token OAuth do rclone possui JSON inválido.') from exc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--config',
        default=os.getenv(
            'GDRIVE_RCLONE_CONFIG',
            '/run/secrets/rclone/rclone.conf',
        ),
    )
    parser.add_argument(
        '--remote',
        default=os.getenv('GDRIVE_RCLONE_REMOTE', 'sorriso.drive'),
    )
    parser.add_argument(
        '--require-refresh',
        action='store_true',
        help='Exige alteração do inode ou da expiração após o comando.',
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    remote = args.remote.rstrip(':')
    executable = shutil.which('rclone')
    if not executable:
        print('ERRO: rclone não encontrado.', file=sys.stderr)
        return 1
    if not config_path.is_file():
        print(f'ERRO: configuração não encontrada: {config_path}', file=sys.stderr)
        return 1
    if not os.access(config_path.parent, os.W_OK):
        print(
            f'ERRO: diretório da configuração não é gravável: {config_path.parent}',
            file=sys.stderr,
        )
        return 1

    before_stat = config_path.stat()
    before_expiry = token_expiry(config_path, remote)
    result = subprocess.run(
        [
            executable,
            '--config',
            str(config_path),
            'about',
            f'{remote}:',
            '--json',
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout or '').strip()
        print(f'ERRO: rclone about falhou: {detail[-800:]}', file=sys.stderr)
        return result.returncode
    if 'device or resource busy' in result.stderr.lower():
        print(
            'ERRO: renovação continua bloqueada por bind mount de arquivo.',
            file=sys.stderr,
        )
        return 1

    after_stat = config_path.stat()
    after_expiry = token_expiry(config_path, remote)
    refreshed = (
        before_stat.st_ino != after_stat.st_ino
        or before_expiry != after_expiry
    )
    if args.require_refresh and not refreshed:
        print(
            'ERRO: o comando funcionou, mas nenhuma renovação persistente foi observada.',
            file=sys.stderr,
        )
        return 1

    print(f'Configuração: {config_path}')
    print('Diretório gravável: sim')
    print(f'Expiração anterior: {before_expiry or "não informada"}')
    print(f'Expiração atual: {after_expiry or "não informada"}')
    print(f'Renovação persistida: {"sim" if refreshed else "não necessária"}')
    print('rclone about: OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
