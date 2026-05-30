#!/usr/bin/env python3
import argparse
import datetime as dt
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import render_template
from weasyprint import HTML

from app import app
from database import execute
from services.institutional_report_service import (
    REPORT_PROFILES,
    get_institutional_report,
    previous_month_period,
    register_generated_report,
)


def parse_month(month_value):
    if not month_value:
        return previous_month_period()

    first_day = dt.datetime.strptime(month_value, '%Y-%m').date().replace(day=1)
    if first_day.month == 12:
        next_month = first_day.replace(year=first_day.year + 1, month=1)
    else:
        next_month = first_day.replace(month=first_day.month + 1)
    return first_day, next_month - dt.timedelta(days=1)


def generate_report(report_type, start, end, output_dir):
    profile = REPORT_PROFILES[report_type]
    report = get_institutional_report(
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        report_type=report_type,
    )
    html = render_template(
        'pdfs/relatorio_institucional_pdf.html',
        report=report,
        generated_by='Sistema',
    )

    os.makedirs(output_dir, exist_ok=True)
    filename = f"{profile['filename_prefix']}_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}_auto.pdf"
    output_path = os.path.join(output_dir, filename)

    report_id = register_generated_report(
        report,
        filename=filename,
        file_path=output_path,
        generated_by=None,
        status='running',
    )
    try:
        HTML(string=html).write_pdf(output_path)
        execute(
            """
            UPDATE generated_reports
            SET status = 'success', completed_at = NOW()
            WHERE id = %s
            """,
            (report_id,)
        )
    except Exception:
        execute(
            """
            UPDATE generated_reports
            SET status = 'failed', completed_at = NOW()
            WHERE id = %s
            """,
            (report_id,)
        )
        raise

    return output_path


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
    args = parser.parse_args()

    start, end = parse_month(args.month)
    report_types = REPORT_PROFILES.keys() if args.type == 'all' else [args.type]

    with app.app_context():
        for report_type in report_types:
            output_path = generate_report(report_type, start, end, args.output_dir)
            print(f'Relatório gerado: {output_path}')


if __name__ == '__main__':
    main()
