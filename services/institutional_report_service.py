import datetime as dt
import json

from database import execute, query
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


def _safe_get(mapping, *keys, default=0):
    value = mapping
    for key in keys:
        if not isinstance(value, dict):
            return default
        value = value.get(key)
    return value if value is not None else default


def get_report_profile(report_type=None):
    return REPORT_PROFILES.get(report_type or 'institucional', REPORT_PROFILES['institucional'])


def get_report_type_choices():
    return [
        {'value': key, 'label': profile['label']}
        for key, profile in REPORT_PROFILES.items()
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


def register_generated_report(report, filename, file_path, generated_by=None, task_id=None, status='queued'):
    return execute(
        """
        INSERT INTO generated_reports (
            report_type, title, period_start, period_end, filename, file_path,
            task_id, generated_by, status, details
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
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
                'audience': report['meta']['audience'],
                'focus': report['meta']['focus'],
                'highlights': report['highlights'],
                'recommendations': report['recommendations'],
            }, ensure_ascii=False, default=str),
        )
    )


def update_generated_report_task(report_id, task_id):
    execute(
        "UPDATE generated_reports SET task_id = %s WHERE id = %s",
        (task_id, report_id)
    )


def list_generated_reports(limit=20):
    return query(
        """
        SELECT gr.*, u.username, u.full_name
        FROM generated_reports gr
        LEFT JOIN users u ON u.id = gr.generated_by
        ORDER BY gr.created_at DESC
        LIMIT %s
        """,
        (limit,)
    )
