import datetime as dt

from constants import Role, role_has_permission
import services.executive_bi_service as executive_bi_service
from services.executive_bi_service import (
    _growth_rate,
    get_executive_bi_dashboard,
    get_summary,
    get_targets,
)


def test_bi_permission_is_available_to_bi_roles():
    assert role_has_permission(Role.ADMIN, 'bi:view')
    assert role_has_permission(Role.BI, 'bi:view')
    assert role_has_permission(Role.EPIDEMIOLOGIA, 'bi:view') is False
    assert role_has_permission(Role.RECEPCAO, 'bi:view') is False


def test_growth_rate_handles_empty_previous_period():
    assert _growth_rate(10, 5) == 100.0
    assert _growth_rate(10, 0) == 0


def test_get_summary_builds_executive_metrics(monkeypatch):
    def fake_query(sql, params=(), one=False):
        if 'FROM tratamento_procedimentos' in sql and 'treated_patients' in sql:
            return {'completed': 20, 'pending': 4, 'treated_patients': 12}
        if 'FROM consultas' in sql and 'patients_seen' in sql:
            return {'total': 25, 'done': 18, 'no_shows': 5, 'canceled': 2, 'patients_seen': 16}
        if 'FROM triagem_senhas s' in sql and 'scheduled_or_seen' in sql:
            return {'total': 30, 'scheduled_or_seen': 21, 'repressed': 9}
        if 'reached_patients' in sql:
            return {'reached_patients': 22, 'neighborhoods': 7, 'municipalities': 3}
        if 'FROM planos_tratamento' in sql:
            return {'total': 10000.0, 'approved': 4000.0}
        return {}

    monkeypatch.setattr(executive_bi_service, 'query', fake_query)

    summary = get_summary(dt.date(2026, 5, 1), dt.date(2026, 5, 30))

    assert summary['completed_procedures'] == 20
    assert summary['pending_procedures'] == 4
    assert summary['attendance_rate'] == 72.0
    assert summary['no_show_rate'] == 20.0
    assert summary['queue_resolution_rate'] == 70.0
    assert summary['plan_conversion_rate'] == 40.0


def test_targets_use_previous_month_as_dynamic_baseline():
    summary = {
        'completed_procedures': 15,
        'attendance_rate': 90,
        'queue_scheduled_or_seen': 8,
    }
    previous = {
        'completed_procedures': 10,
        'queue_scheduled_or_seen': 4,
    }

    targets = get_targets(summary, previous)
    by_label = {target['label']: target for target in targets}

    assert by_label['Produção Clínica']['target'] == 10
    assert by_label['Produção Clínica']['rate'] == 100
    assert by_label['Comparecimento']['target'] == 85
    assert by_label['Fila Encaminhada']['target'] == 4


def test_executive_bi_dashboard_composes_sections(monkeypatch):
    summary = {
        'completed_procedures': 20,
        'patients_seen': 16,
        'queue_scheduled_or_seen': 12,
        'no_show_rate': 10,
        'attendance_rate': 80,
    }
    previous = {
        'completed_procedures': 10,
        'patients_seen': 8,
        'queue_scheduled_or_seen': 6,
        'no_show_rate': 12,
    }

    monkeypatch.setattr(executive_bi_service, 'get_summary', lambda start, end: summary)
    monkeypatch.setattr(executive_bi_service, 'get_previous_summary', lambda start: previous)
    monkeypatch.setattr(executive_bi_service, 'get_monthly_comparison', lambda end: [{'label': '05/2026'}])
    monkeypatch.setattr(executive_bi_service, 'get_professional_ranking', lambda start, end: [{'professional': 'Dra. Ana'}])
    monkeypatch.setattr(executive_bi_service, 'get_neighborhood_ranking', lambda start, end: [{'bairro': 'Centro'}])
    monkeypatch.setattr(executive_bi_service, 'get_specialty_ranking', lambda start, end: [{'especialidade': 'Prótese'}])

    data = get_executive_bi_dashboard(
        start_date='2026-05-01',
        end_date='2026-05-30',
        today=dt.date(2026, 5, 30),
    )

    assert data['period']['start'] == dt.date(2026, 5, 1)
    assert data['growth']['production'] == 100.0
    assert data['growth']['no_show_rate'] == -2
    assert data['monthly_comparison'][0]['label'] == '05/2026'
    assert data['professional_ranking'][0]['professional'] == 'Dra. Ana'
