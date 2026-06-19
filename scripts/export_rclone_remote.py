#!/usr/bin/env python3
"""Exporta somente um remote rclone para um arquivo de segredo dedicado."""

import argparse
import configparser
import os
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--section', required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--target-section', default='sorriso.drive')
    args = parser.parse_args()

    source = Path(args.source).expanduser()
    target = Path(args.target).expanduser()
    source_config = configparser.RawConfigParser()
    if not source_config.read(source) or not source_config.has_section(args.section):
        raise SystemExit(f'Remote rclone não encontrado: {args.section}')

    target_config = configparser.RawConfigParser()
    target_config.add_section(args.target_section)
    for key, value in source_config.items(args.section):
        target_config.set(args.target_section, key, value)

    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f'.{target.name}.',
        dir=target.parent,
        text=True,
    )
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as file_obj:
            target_config.write(file_obj)
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, target)
    finally:
        if os.path.exists(temporary_name):
            os.remove(temporary_name)

    print(f'Remote {args.section} exportado como {args.target_section} em {target}.')


if __name__ == '__main__':
    main()
