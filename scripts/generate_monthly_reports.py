#!/usr/bin/env python3
import argparse
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app
from services.institutional_report_service import REPORT_PROFILES
from services.report_generation_service import generate_monthly_reports


def main():
    parser = argparse.ArgumentParser(description='Gera relatórios institucionais mensais.')
    parser.add_argument(
        '--type',
        choices=[*REPORT_PROFILES.keys(), 'all'],
        default='all',
        help='Tipo do relatório a gerar.'
    )
    parser.add_argument(
        '--month',
        help='Mês de referência no formato YYYY-MM. Padrão: mês anterior.'
    )
    parser.add_argument(
        '--output-dir',
        default=os.getenv('REPORTS_OUTPUT_DIR', 'pdf_temp'),
        help='Diretório de saída dos PDFs.'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Gera novamente mesmo quando já existir relatório mensal automático com sucesso.'
    )
    args = parser.parse_args()

    with app.app_context():
        results = generate_monthly_reports(
            report_type=args.type,
            month=args.month,
            output_dir=args.output_dir,
            source='scheduler',
            skip_existing=not args.force,
        )

    for result in results:
        if result['status'] == 'skipped':
            print(f"Relatório já existente: {result['output_path']}")
        else:
            print(f"Relatório gerado: {result['output_path']} | hash={result['signature_hash']}")


if __name__ == '__main__':
    main()
