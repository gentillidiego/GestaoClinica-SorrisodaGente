import datetime as dt

from constants import Role, role_has_permission
import services.command_center_service as command_center_service
from services.command_center_service import (
    build_operational_alerts,
    calculate_age,
    calculate_priority_score,
    get_command_center_data,
    get_priority_queue,
    get_risk_level,
)


def test_command_center_permission_is_available_to_operational_roles():
    assert role_has_permission(Role.ADMIN, 'command_center:view')
    assert role_has_permission(Role.RECEPCAO, 'command_center:view')
    assert role_has_permission(Role.TRIAGEM, 'command_center:view')
    assert role_has_permission(Role.DENTISTA, 'command_center:view')
    assert role_has_permission(Role.AUDITORIA, 'command_center:view')


def test_calculate_age_accepts_iso_and_brazilian_dates():
    today = dt.date(2026, 5, 29)

    assert calculate_age('1960-05-28', today=today) == 66
    assert calculate_age('29/05/1966', today=today) == 60
    assert calculate_age('data inválida', today=today) is None


def test_priority_score_marks_oncology_case_as_critical():
    patient = {
        'suspeita_neoplasia': True,
        'data_nascimento': '1958-01-10',
        'no_show_count': 2,
        'pending_treatments': 3,
        'lesion_days_without_return': 20,
    }

    result = calculate_priority_score(patient, today=dt.date(2026, 5, 29))

    assert result['score'] == 190
    assert result['risk_level'] == 'critical'
    assert 'Suspeita de neoplasia' in result['reasons']
    assert 'Idoso' in result['reasons']
    assert 'Duas faltas ou mais' in result['reasons']
    assert 'Lesão suspeita sem retorno' in result['reasons']


def test_priority_score_limits_pending_treatment_points():
    result = calculate_priority_score(
        {'pending_treatments': 10},
        today=dt.date(2026, 5, 29),
    )

    assert result['score'] == 20
    assert result['risk_level'] == 'routine'


def test_risk_level_boundaries():
    assert get_risk_level(100) == 'critical'
    assert get_risk_level(50) == 'high'
    assert get_risk_level(25) == 'medium'
    assert get_risk_level(24) == 'routine'


def test_operational_alert_builder_includes_core_phase2_alerts():
    priority_queue = [
        {'no_show_count': 2, 'lesion_days_without_return': 15},
        {'no_show_count': 0, 'lesion_days_without_return': None},
    ]

    alerts = build_operational_alerts(
        red_alert_count=1,
        pending_treatments=5,
        agenda_by_status={'Faltou': 3},
        priority_queue=priority_queue,
    )
    alert_types = {alert['type'] for alert in alerts}

    assert 'red_alert' in alert_types
    assert 'lesion_without_return' in alert_types
    assert 'two_no_shows' in alert_types
    assert 'pending_treatments' in alert_types
    assert 'no_show' in alert_types


def test_priority_queue_query_avoids_join_duplication_and_uses_latest_lesion(monkeypatch):
    captured = {}

    def fake_query(sql, params=(), one=False):
        captured['sql'] = sql
        return []

    monkeypatch.setattr(command_center_service, 'query', fake_query)

    assert get_priority_queue(limit=None) == []

    sql = captured['sql']
    assert 'latest_estomatologia' in sql
    assert 'COUNT(DISTINCT c.id)' in sql
    assert 'COUNT(DISTINCT tp.id)' in sql
    assert 'c.data_consulta >= e.data_registro' in sql


def test_priority_queue_sorts_and_respects_optional_limit(monkeypatch):
    rows = [
        {
            'id': 2,
            'nome': 'Rotina',
            'data_nascimento': '1990-01-01',
            'suspeita_neoplasia': False,
            'no_show_count': 1,
            'pending_treatments': 1,
            'lesion_days_without_return': None,
        },
        {
            'id': 1,
            'nome': 'Prioridade',
            'data_nascimento': '1950-01-01',
            'suspeita_neoplasia': True,
            'no_show_count': 2,
            'pending_treatments': 3,
            'lesion_days_without_return': 20,
        },
    ]

    monkeypatch.setattr(command_center_service, 'query', lambda *args, **kwargs: rows)

    full_queue = get_priority_queue(limit=None)

    assert [patient['nome'] for patient in full_queue] == ['Prioridade', 'Rotina']
    assert [patient['nome'] for patient in get_priority_queue(limit=1)] == ['Prioridade']


def test_command_center_alerts_use_full_priority_queue_not_only_display_limit(monkeypatch):
    def fake_query(sql, params=(), one=False):
        if 'COUNT(*) FILTER' in sql:
            return {'today': 0, 'month': 0}
        if one:
            return {'count': 0}
        return []

    priority_queue = [
        {
            'nome': f'Paciente {index:02d}',
            'score': 10,
            'no_show_count': 0,
            'lesion_days_without_return': None,
        }
        for index in range(12)
    ]
    priority_queue.append({
        'nome': 'Paciente fora do top 12',
        'score': 9,
        'no_show_count': 2,
        'lesion_days_without_return': None,
    })

    monkeypatch.setattr(command_center_service, 'query', fake_query)
    monkeypatch.setattr(command_center_service, 'get_priority_queue', lambda limit=None: priority_queue)
    monkeypatch.setattr(command_center_service, 'get_inventory_alerts', lambda limit=20: [])

    data = get_command_center_data()
    alert_types = {alert['type'] for alert in data['alerts']}

    assert len(data['priority_queue']) == 12
    assert 'two_no_shows' in alert_types
