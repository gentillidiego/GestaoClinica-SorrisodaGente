#!/usr/bin/env python3
"""Gera uma remessa XML e-SUS APS validada para um período/profissional."""

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app
from services.esus_export_service import gerar_remessa_xml


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', required=True, help='Data inicial YYYY-MM-DD.')
    parser.add_argument('--end', required=True, help='Data final YYYY-MM-DD.')
    parser.add_argument('--professional-id', required=True, type=int)
    parser.add_argument('--label', help='Rótulo da remessa, por exemplo 2026-06 P1.')
    parser.add_argument('--output', help='Caminho opcional para copiar o XML validado.')
    args = parser.parse_args()

    with app.app_context():
        result = gerar_remessa_xml(
            args.start,
            args.end,
            periodo_label=args.label,
            professional_id=args.professional_id,
        )

    source = Path(result['xml_path'])
    if args.output:
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        output_path = destination
    else:
        output_path = source

    print(f"Remessa #{result['remessa_id']} validada: {output_path}")
    print(f"Profissional: {result['professional_name']}")
    print(f"Procedimentos: {result['records_ready']}")
    print(f"SHA-256: {result['xml_hash']}")


if __name__ == '__main__':
    main()
