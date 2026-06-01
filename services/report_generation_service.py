import datetime as dt
import os

from flask import render_template
from weasyprint import HTML

from services.institutional_report_service import (
    REPORT_PROFILES,
    finalize_generated_report,
    find_completed_generated_report,
    get_institutional_report,
    previous_month_period,
    register_generated_report,
    mark_generated_report_failed,
)


def parse_month_period(month_value=None):
    if not month_value:
        return previous_month_period()

    first_day = dt.datetime.strptime(month_value, '%Y-%m').date().replace(day=1)
    if first_day.month == 12:
        next_month = first_day.replace(year=first_day.year + 1, month=1)
    else:
        next_month = first_day.replace(month=first_day.month + 1)
    return first_day, next_month - dt.timedelta(days=1)


def resolve_report_types(report_type='all'):
    if report_type == 'all':
        return list(REPORT_PROFILES.keys())
    if report_type not in REPORT_PROFILES:
        raise ValueError(f'Tipo de relatório inválido: {report_type}')
    return [report_type]


def build_scheduled_key(report_type, start, end, source='scheduler'):
    return f'{source}:{report_type}:{start.strftime("%Y%m%d")}:{end.strftime("%Y%m%d")}'


def generate_institutional_pdf(
    report_type,
    start,
    end,
    output_dir=None,
    generated_by=None,
    generated_by_label='Sistema',
    source='scheduler',
    task_id=None,
    skip_existing=False,
):
    if skip_existing:
        existing = find_completed_generated_report(report_type, start, end, source=source)
        if existing:
            return {
                'report_type': report_type,
                'report_id': existing['id'],
                'filename': existing['filename'],
                'output_path': existing['file_path'],
                'status': 'skipped',
                'signature_hash': existing.get('signature_hash'),
            }

    profile = REPORT_PROFILES[report_type]
    report = get_institutional_report(
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        report_type=report_type,
    )
    html = render_template(
        'pdfs/relatorio_institucional_pdf.html',
        report=report,
        generated_by=generated_by_label,
    )

    output_dir = output_dir or os.getenv('REPORTS_OUTPUT_DIR', 'pdf_temp')
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{profile['filename_prefix']}_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}_auto.pdf"
    output_path = os.path.join(output_dir, filename)
    scheduled_key = build_scheduled_key(report_type, start, end, source=source)

    report_id = register_generated_report(
        report,
        filename=filename,
        file_path=output_path,
        generated_by=generated_by,
        task_id=task_id,
        status='running',
        source=source,
        scheduled_key=scheduled_key,
        delivery_channel='painel_seguro',
    )

    try:
        HTML(string=html).write_pdf(output_path)
        signature_hash = finalize_generated_report(
            report_id,
            output_path,
            signed_by=generated_by,
            signer_name=generated_by_label,
            signer_role='system' if generated_by is None else 'user',
        )
    except Exception as exc:
        mark_generated_report_failed(report_id, exc)
        raise

    return {
        'report_type': report_type,
        'report_id': report_id,
        'filename': filename,
        'output_path': output_path,
        'status': 'success',
        'signature_hash': signature_hash,
    }


def generate_monthly_reports(
    report_type='all',
    month=None,
    output_dir=None,
    generated_by=None,
    generated_by_label='Sistema',
    source='scheduler',
    task_id=None,
    skip_existing=True,
):
    start, end = parse_month_period(month)
    results = []
    for item in resolve_report_types(report_type):
        results.append(
            generate_institutional_pdf(
                item,
                start,
                end,
                output_dir=output_dir,
                generated_by=generated_by,
                generated_by_label=generated_by_label,
                source=source,
                task_id=task_id,
                skip_existing=skip_existing,
            )
        )
    return results
