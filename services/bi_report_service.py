import datetime as dt
import json

from database import execute, query
from services.executive_bi_service import get_executive_bi_dashboard, normalize_bi_view


BI_REPORT_TYPE = 'bi_governamental'


def _money(value):
    amount = float(value or 0)
    return f"R$ {amount:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def _percent(value):
    return f"{float(value or 0):.1f}%".replace('.', ',')


def _view_report_title(view_label):
    return f'Relatório Governamental do BI - {view_label}'


def get_bi_report(start_date=None, end_date=None, view=None, today=None):
    today = today or dt.date.today()
    selected_view = normalize_bi_view(view)
    dashboard = get_executive_bi_dashboard(
        start_date=start_date,
        end_date=end_date,
        today=today,
        view=selected_view,
    )
    summary = dashboard['summary']
    economy = dashboard['economy']
    government_view = dashboard['government_view']
    title = _view_report_title(government_view['label'])

    highlights = [
        {
            'label': 'Produção clínica',
            'value': summary['completed_procedures'],
            'detail': 'procedimentos concluídos no período',
        },
        {
            'label': 'Pacientes atendidos',
            'value': summary['patients_seen'],
            'detail': f"{_percent(summary['attendance_rate'])} de comparecimento",
        },
        {
            'label': 'Fila encaminhada',
            'value': summary['queue_scheduled_or_seen'],
            'detail': f"{_percent(summary['queue_resolution_rate'])} da demanda triada",
        },
        {
            'label': 'Economia estimada',
            'value': _money(economy['estimated_savings']),
            'detail': economy['methodology_status'],
        },
        {
            'label': 'Suspeitas oncológicas',
            'value': summary['cancer_suspicions'],
            'detail': f"{summary['cancer_confirmed']} câncer confirmado",
        },
        {
            'label': 'Cobertura SIGTAP',
            'value': _percent(summary['sigtap_coverage_rate']),
            'detail': f"{summary['completed_without_sigtap']} procedimento(s) sem SIGTAP",
        },
    ]

    recommendations = build_bi_recommendations(dashboard)

    return {
        'generated_at': dt.datetime.now(),
        'report_type': BI_REPORT_TYPE,
        'period': dashboard['period'],
        'view': selected_view,
        'dashboard': dashboard,
        'highlights': highlights,
        'recommendations': recommendations,
        'meta': {
            'title': title,
            'subtitle': 'Síntese executiva do BI por visão governamental',
            'audience': government_view['label'],
            'focus': [
                'produção e fila SUS',
                'impacto social e territorial',
                'oncologia bucal',
                'economia gerada estimada',
                'conformidade SIGTAP/e-SUS',
            ],
            'notes': [
                'Economia gerada é estimada enquanto metodologia e valores não forem homologados pela gestão pública.',
                'Indicadores oncológicos combinam suspeitas clínicas, encaminhamentos e confirmações registradas em estomatologia.',
                'Cobertura SIGTAP influencia prontidão para e-SUS APS e qualidade dos relatórios governamentais.',
            ],
        },
    }


def build_bi_recommendations(dashboard):
    summary = dashboard['summary']
    economy = dashboard['economy']
    recommendations = []

    if summary['queue_repressed'] > 0:
        recommendations.append(
            f"Priorizar fila SUS: {summary['queue_repressed']} paciente(s) ainda aparecem como demanda reprimida."
        )
    if summary['no_show_rate'] >= 15:
        recommendations.append(
            f"Acionar busca ativa para absenteísmo de {_percent(summary['no_show_rate'])} no período."
        )
    if summary['cancer_suspicions'] > 0:
        recommendations.append(
            f"Monitorar oncologia bucal: {summary['cancer_suspicions']} suspeita(s), {summary['biopsy_referrals']} encaminhamento(s) para biópsia e {summary['cancer_confirmed']} confirmação(ões)."
        )
    if summary['completed_without_sigtap'] > 0:
        recommendations.append(
            f"Corrigir produção sem SIGTAP: {summary['completed_without_sigtap']} procedimento(s) concluído(s) ainda sem código."
        )
    if economy['missing_reference'] > 0:
        recommendations.append(
            f"Completar referências de custo: {economy['missing_reference']} procedimento(s) sem referência configurada."
        )
    if economy['methodology_status'] != 'metodologia validada':
        recommendations.append(
            'Homologar metodologia e valores de custo antes de usar economia estimada como indicador público formal.'
        )

    if not recommendations:
        recommendations.append('Manter acompanhamento mensal do BI e registrar validações formais da gestão pública.')
    return recommendations


def register_bi_government_report(report, filename, file_path, generated_by=None, task_id=None, status='queued'):
    details = {
        'source': 'manual',
        'audience': report['meta']['audience'],
        'view': report['view'],
        'delivery_channel': 'painel_seguro',
        'focus': report['meta']['focus'],
        'highlights': report['highlights'],
        'recommendations': report['recommendations'],
        'economy_methodology_status': report['dashboard']['economy']['methodology_status'],
    }
    return execute(
        """
        INSERT INTO generated_reports (
            report_type, title, period_start, period_end, filename, file_path,
            task_id, generated_by, status, details, delivery_channel, signature_status
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
        RETURNING id
        """,
        (
            BI_REPORT_TYPE,
            report['meta']['title'],
            report['period']['start'],
            report['period']['end'],
            filename,
            file_path,
            task_id,
            generated_by,
            status,
            json.dumps(details, ensure_ascii=False, default=str),
            'painel_seguro',
            'pending',
        ),
    )


def list_bi_government_reports(limit=8):
    return query(
        """
        SELECT gr.*, u.username, u.full_name
        FROM generated_reports gr
        LEFT JOIN users u ON u.id = gr.generated_by
        WHERE gr.report_type = %s
        ORDER BY gr.created_at DESC
        LIMIT %s
        """,
        (BI_REPORT_TYPE, limit),
    )
