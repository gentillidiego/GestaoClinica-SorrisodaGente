import datetime as dt

import services.bi_report_service as bi_report_service
from services.bi_report_service import (
    BI_REPORT_TYPE,
    build_bi_recommendations,
    get_bi_report,
    register_bi_government_report,
)


def _bi_dashboard_fixture():
    return {
        'period': {
            'start': dt.date(2026, 6, 1),
            'end': dt.date(2026, 6, 30),
        },
        'filters': {
            'view': 'prefeitura',
        },
        'summary': {
            'completed_procedures': 50,
            'patients_seen': 30,
            'attendance_rate': 82.0,
            'queue_total': 40,
            'queue_scheduled_or_seen': 25,
            'queue_resolution_rate': 62.5,
            'queue_repressed': 15,
            'reached_patients': 35,
            'neighborhoods': 7,
            'municipalities': 3,
            'no_show_rate': 17.0,
            'completed_without_sigtap': 4,
            'sigtap_coverage_rate': 92.0,
            'lesion_records': 5,
            'cancer_suspicions': 2,
            'cancer_confirmed': 1,
            'biopsy_referrals': 1,
        },
        'economy': {
            'estimated_savings': 3200.0,
            'public_value': 800.0,
            'reference_value': 4000.0,
            'missing_reference': 3,
            'reference_coverage_rate': 88.0,
            'methodology_status': 'estimativa operacional aguardando validação pública',
            'methodology_note': 'Nota metodológica',
            'items': [
                {
                    'sigtap_code': '0307040070',
                    'procedure_name': 'Moldagem',
                    'completed_procedures': 5,
                    'estimated_savings': 1200.0,
                }
            ],
        },
        'government_view': {
            'label': 'Prefeitura',
            'description': 'Impacto social',
            'cards': [
                {'label': 'Impacto social', 'value': 35, 'note': 'pacientes alcançados'},
            ],
            'focus': [
                {'label': 'Demanda reprimida', 'value': 15, 'detail': 'pacientes'},
            ],
        },
        'neighborhood_ranking': [{'bairro': 'Centro', 'reached_patients': 12}],
        'specialty_ranking': [{'especialidade': 'Prótese', 'repressed': 6}],
    }


def test_bi_government_report_composes_pdf_context(monkeypatch):
    monkeypatch.setattr(
        bi_report_service,
        'get_executive_bi_dashboard',
        lambda start_date=None, end_date=None, today=None, view=None: _bi_dashboard_fixture(),
    )

    report = get_bi_report(
        start_date='2026-06-01',
        end_date='2026-06-30',
        view='prefeitura',
        today=dt.date(2026, 6, 30),
    )

    assert report['report_type'] == BI_REPORT_TYPE
    assert report['view'] == 'prefeitura'
    assert report['meta']['title'] == 'Relatório Governamental do BI - Prefeitura'
    assert report['highlights'][0]['label'] == 'Produção clínica'
    assert any('Homologar metodologia' in item for item in report['recommendations'])


def test_bi_recommendations_are_actionable():
    recommendations = build_bi_recommendations(_bi_dashboard_fixture())

    assert any('Priorizar fila SUS' in item for item in recommendations)
    assert any('absenteísmo' in item for item in recommendations)
    assert any('oncologia bucal' in item for item in recommendations)
    assert any('sem SIGTAP' in item for item in recommendations)
    assert any('referências de custo' in item for item in recommendations)


def test_register_bi_government_report_persists_metadata(monkeypatch):
    captured = {}
    report = {
        'report_type': BI_REPORT_TYPE,
        'view': 'prefeitura',
        'period': {
            'start': dt.date(2026, 6, 1),
            'end': dt.date(2026, 6, 30),
        },
        'highlights': [{'label': 'Economia estimada', 'value': 'R$ 3.200,00', 'detail': 'draft'}],
        'recommendations': ['Homologar metodologia.'],
        'dashboard': {
            'economy': {
                'methodology_status': 'estimativa operacional aguardando validação pública',
            }
        },
        'meta': {
            'title': 'Relatório Governamental do BI - Prefeitura',
            'audience': 'Prefeitura',
            'focus': ['impacto social'],
        },
    }

    def fake_execute(sql, params=()):
        captured['sql'] = sql
        captured['params'] = params
        return 77

    monkeypatch.setattr(bi_report_service, 'execute', fake_execute)

    report_id = register_bi_government_report(
        report,
        filename='relatorio_bi.pdf',
        file_path='/tmp/relatorio_bi.pdf',
        generated_by=7,
    )

    assert report_id == 77
    assert 'INSERT INTO generated_reports' in captured['sql']
    assert captured['params'][0] == BI_REPORT_TYPE
    assert captured['params'][4] == 'relatorio_bi.pdf'
    assert captured['params'][7] == 7
    assert captured['params'][8] == 'queued'
    assert '"view": "prefeitura"' in captured['params'][9]
