import datetime as dt
import hashlib
import json
import os

from database import execute, query
from constants import Role
from services.epidemiology_service import get_epidemiology_dashboard, normalize_period
from services.executive_bi_service import get_executive_bi_dashboard


REPORT_PROFILES = {
    'institucional': {
        'label': 'Institucional',
        'title': 'Relatório Institucional Mensal',
        'subtitle': 'Síntese executiva, epidemiológica e operacional do Programa Sorriso da Gente',
        'filename_prefix': 'relatorio_institucional',
        'audience': 'Gestão geral',
        'focus': [
            'prestação de contas executiva',
            'impacto social',
            'produção clínica',
            'alertas epidemiológicos',
        ],
    },
    'ssa': {
        'label': 'SSA',
        'title': 'Relatório Mensal para SSA',
        'subtitle': 'Síntese epidemiológica e assistencial para acompanhamento estadual',
        'filename_prefix': 'relatorio_ssa',
        'audience': 'Secretaria de Estado da Saúde',
        'focus': [
            'suspeitas oncológicas',
            'demanda reprimida por especialidade',
            'bairros e municípios alcançados',
            'capacidade assistencial',
        ],
    },
    'sms': {
        'label': 'SMS',
        'title': 'Relatório Mensal para SMS',
        'subtitle': 'Síntese territorial e operacional para acompanhamento municipal',
        'filename_prefix': 'relatorio_sms',
        'audience': 'Secretaria Municipal de Saúde',
        'focus': [
            'bairros atendidos',
            'absenteísmo',
            'busca ativa',
            'demanda reprimida local',
        ],
    },
}

REPORT_ACCESS_BY_ROLE = {
    Role.ADMIN: {'institucional', 'ssa', 'sms'},
    Role.BI: {'institucional', 'ssa', 'sms'},
    Role.AUDITORIA: {'institucional', 'ssa', 'sms'},
    Role.EPIDEMIOLOGIA: {'institucional', 'ssa', 'sms'},
    Role.PREFEITURA: {'institucional'},
    Role.SSA: {'ssa'},
    Role.SMS: {'sms'},
    Role.FINANCEIRO: {'institucional'},
    Role.COMUNICACAO: {'institucional'},
}


def _safe_get(mapping, *keys, default=0):
    value = mapping
    for key in keys:
        if not isinstance(value, dict):
            return default
        value = value.get(key)
    return value if value is not None else default


def _coerce_number(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0


def _bar_chart_rows(rows, label_key, value_key, limit=6):
    selected = list(rows or [])[:limit]
    values = [_coerce_number(row.get(value_key)) for row in selected]
    max_value = max(values) if values else 0
    chart_rows = []

    for row, value in zip(selected, values):
        chart_rows.append({
            'label': row.get(label_key) or 'Não informado',
            'value': int(value) if value.is_integer() else round(value, 1),
            'percent': round((value / max_value) * 100, 1) if max_value else 0,
        })

    return chart_rows


def get_report_profile(report_type=None):
    return REPORT_PROFILES.get(report_type or 'institucional', REPORT_PROFILES['institucional'])


def get_report_types_for_role(role):
    return sorted(
        REPORT_ACCESS_BY_ROLE.get(role, set()),
        key=lambda item: list(REPORT_PROFILES.keys()).index(item)
    )


def role_can_access_report_type(role, report_type):
    return report_type in get_report_types_for_role(role)


def get_report_type_choices(allowed_types=None):
    allowed = set(REPORT_PROFILES.keys() if allowed_types is None else allowed_types)
    return [
        {'value': key, 'label': profile['label']}
        for key, profile in REPORT_PROFILES.items()
        if key in allowed
    ]


def previous_month_period(today=None):
    today = today or dt.date.today()
    first_day_current_month = today.replace(day=1)
    last_day_previous_month = first_day_current_month - dt.timedelta(days=1)
    return last_day_previous_month.replace(day=1), last_day_previous_month


def build_highlights(executive, epidemiology):
    summary = executive['summary']
    epi_summary = epidemiology['summary']

    return [
        {
            'label': 'Produção clínica',
            'value': summary['completed_procedures'],
            'detail': 'procedimentos concluídos no período',
        },
        {
            'label': 'Pacientes atendidos',
            'value': summary['patients_seen'],
            'detail': 'pacientes com consulta realizada',
        },
        {
            'label': 'Fila encaminhada',
            'value': summary['queue_scheduled_or_seen'],
            'detail': f"{summary['queue_resolution_rate']}% da demanda triada",
        },
        {
            'label': 'Suspeitas oncológicas',
            'value': epi_summary['cancer_suspicions'],
            'detail': 'casos sinalizados para vigilância clínica',
        },
        {
            'label': 'Absenteísmo',
            'value': f"{summary['no_show_rate']}%",
            'detail': f"{summary['no_shows']} falta(s) registradas",
        },
        {
            'label': 'Bairros alcançados',
            'value': summary['neighborhoods'],
            'detail': 'territórios com atendimento/produção registrada',
        },
    ]


def build_recommendations(executive, epidemiology, report_type='institucional'):
    recommendations = []
    summary = executive['summary']
    epi_summary = epidemiology['summary']

    if summary['queue_repressed'] > 0:
        recommendations.append(
            f"Priorizar a demanda reprimida: {summary['queue_repressed']} paciente(s) triado(s) ainda sem consulta confirmada ou realizada."
        )
    if summary['no_show_rate'] >= 15:
        recommendations.append(
            f"Acionar busca ativa para absenteísmo: taxa atual de {summary['no_show_rate']}%."
        )
    if epi_summary['cancer_suspicions'] > 0:
        recommendations.append(
            f"Monitorar fila oncológica: {epi_summary['cancer_suspicions']} suspeita(s) de câncer de boca no período."
        )
    if epi_summary['prosthetic_need'] > 0:
        recommendations.append(
            f"Planejar capacidade protética: {epi_summary['prosthetic_need']} paciente(s) com necessidade protética identificada."
        )
    if report_type == 'ssa' and epi_summary['biopsy_referrals'] > 0:
        recommendations.append(
            f"Acompanhar referência estadual para biópsia: {epi_summary['biopsy_referrals']} encaminhamento(s) registrado(s)."
        )
    if report_type == 'sms' and summary['neighborhoods'] > 0:
        recommendations.append(
            f"Orientar ações territoriais nos bairros com maior alcance e faltas para reforçar busca ativa municipal."
        )

    if not recommendations:
        recommendations.append('Manter acompanhamento mensal dos indicadores e atualizar metas conforme evolução da produção.')

    return recommendations


def build_report_charts(executive, epidemiology):
    return {
        'monthly_production': _bar_chart_rows(
            executive.get('monthly_comparison', []),
            'label',
            'completed_procedures',
            limit=6,
        ),
        'neighborhoods': _bar_chart_rows(
            executive.get('neighborhood_ranking', []),
            'bairro',
            'reached_patients',
            limit=6,
        ),
        'specialties': _bar_chart_rows(
            executive.get('specialty_ranking', []),
            'especialidade',
            'repressed',
            limit=6,
        ),
        'lesions': _bar_chart_rows(
            epidemiology.get('lesion_locations', []),
            'localizacao',
            'lesion_records',
            limit=6,
        ),
    }


def get_institutional_report(start_date=None, end_date=None, today=None, report_type='institucional'):
    today = today or dt.date.today()
    start, end = normalize_period(start_date, end_date, today=today)
    start_str = start.isoformat()
    end_str = end.isoformat()
    profile = get_report_profile(report_type)
    normalized_type = report_type if report_type in REPORT_PROFILES else 'institucional'

    executive = get_executive_bi_dashboard(start_str, end_str, today=today)
    epidemiology = get_epidemiology_dashboard(start_str, end_str, today=today)

    return {
        'generated_at': dt.datetime.now(),
        'period': {
            'start': start,
            'end': end,
        },
        'executive': executive,
        'epidemiology': epidemiology,
        'report_type': normalized_type,
        'profile': profile,
        'highlights': build_highlights(executive, epidemiology),
        'recommendations': build_recommendations(executive, epidemiology, normalized_type),
        'top_neighborhoods': executive.get('neighborhood_ranking', [])[:8],
        'top_specialties': executive.get('specialty_ranking', [])[:8],
        'top_lesions': epidemiology.get('lesion_locations', [])[:8],
        'monthly_comparison': executive.get('monthly_comparison', []),
        'charts': build_report_charts(executive, epidemiology),
        'meta': {
            'title': profile['title'],
            'subtitle': profile['subtitle'],
            'audience': profile['audience'],
            'focus': profile['focus'],
            'data_sources': [
                'patients',
                'consultas',
                'tratamento_procedimentos',
                'triagem_senhas',
                'estomatologia',
                'prosthesis',
                'planos_tratamento',
            ],
            'notes': [
                'Indicadores financeiros são operacionais e não representam economia pública formal validada.',
                'Suspeitas oncológicas representam sinalização clínica, não diagnóstico confirmado.',
                'Mapa epidemiológico v1 usa bairro informado no cadastro, sem georreferenciamento cartográfico.',
            ],
            'reached_patients': _safe_get(executive, 'summary', 'reached_patients'),
        },
    }


def register_generated_report(
    report,
    filename,
    file_path,
    generated_by=None,
    task_id=None,
    status='queued',
    source='manual',
    scheduled_key=None,
    delivery_channel='painel_seguro',
):
    return execute(
        """
        INSERT INTO generated_reports (
            report_type, title, period_start, period_end, filename, file_path,
            task_id, generated_by, status, details, scheduled_key, delivery_channel,
            signature_status
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
        RETURNING id
        """,
        (
            report['report_type'],
            report['meta']['title'],
            report['period']['start'],
            report['period']['end'],
            filename,
            file_path,
            task_id,
            generated_by,
            status,
            json.dumps({
                'source': source,
                'audience': report['meta']['audience'],
                'delivery_channel': delivery_channel,
                'focus': report['meta']['focus'],
                'highlights': report['highlights'],
                'recommendations': report['recommendations'],
            }, ensure_ascii=False, default=str),
            scheduled_key,
            delivery_channel,
            'pending',
        )
    )


def update_generated_report_task(report_id, task_id):
    execute(
        "UPDATE generated_reports SET task_id = %s, status = 'running' WHERE id = %s",
        (task_id, report_id)
    )


def calculate_file_sha256(file_path):
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as pdf_file:
        for chunk in iter(lambda: pdf_file.read(1024 * 1024), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def finalize_generated_report(
    report_id,
    file_path,
    signed_by=None,
    signer_name='Sistema',
    signer_role='system',
    signature_provider='sha256-internal',
):
    signature_hash = calculate_file_sha256(file_path)
    filename = os.path.basename(file_path)
    execute(
        """
        UPDATE generated_reports
        SET status = 'success',
            completed_at = NOW(),
            signature_hash = %s,
            signature_status = 'hash_internal',
            signed_at = NOW(),
            details = COALESCE(details, '{}'::jsonb) || %s::jsonb
        WHERE id = %s
        """,
        (
            signature_hash,
            json.dumps({'signature_hash': signature_hash}, ensure_ascii=False),
            report_id,
        )
    )
    execute(
        """
        INSERT INTO digital_signatures (
            document_type, document_id, signed_by, signer_name, signer_role,
            signature_provider, signature_hash, metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        """,
        (
            'generated_report',
            str(report_id),
            signed_by,
            signer_name,
            signer_role,
            signature_provider,
            signature_hash,
            json.dumps({'file_path': file_path, 'filename': filename}, ensure_ascii=False),
        )
    )
    return signature_hash


def mark_generated_report_failed(report_id, error_message=None):
    details = {}
    if error_message:
        details['error'] = str(error_message)
    execute(
        """
        UPDATE generated_reports
        SET status = 'failed',
            completed_at = NOW(),
            details = COALESCE(details, '{}'::jsonb) || %s::jsonb
        WHERE id = %s
        """,
        (json.dumps(details, ensure_ascii=False), report_id)
    )


def find_completed_generated_report(report_type, start, end, source='scheduler'):
    return query(
        """
        SELECT *
        FROM generated_reports
        WHERE report_type = %s
          AND period_start = %s
          AND period_end = %s
          AND status = 'success'
          AND COALESCE(details ->> 'source', '') = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (report_type, start, end, source),
        one=True,
    )


def list_generated_reports(limit=20, report_types=None):
    params = []
    where = ''
    if report_types is not None:
        allowed_types = list(report_types)
        if not allowed_types:
            return []
        placeholders = ', '.join(['%s'] * len(allowed_types))
        where = f"WHERE gr.report_type IN ({placeholders})"
        params.extend(allowed_types)

    params.append(limit)
    return query(
        f"""
        SELECT gr.*, u.username, u.full_name
        FROM generated_reports gr
        LEFT JOIN users u ON u.id = gr.generated_by
        {where}
        ORDER BY gr.created_at DESC
        LIMIT %s
        """,
        tuple(params)
    )
