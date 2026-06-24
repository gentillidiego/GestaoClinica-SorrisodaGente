import datetime as dt

from constants import Role, role_has_permission
import services.command_center_service as command_center_service
from services.command_center_service import (
    build_daily_summary_csv_rows,
    build_operational_alerts,
    build_operational_goals,
    calculate_age,
    calculate_priority_score,
    get_daily_operational_summary,
    get_pending_exam_alert_summary,
    get_demand_forecast_snapshot,
    get_command_center_data,
    get_patient_clinical_alert_summary,
    get_priority_queue,
    get_queue_operational_metrics,
    get_risk_level,
    get_specialty_bottlenecks,
    get_unsigned_document_alert_summary,
    normalize_command_center_filters,
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


def test_priority_score_includes_phase28_clinical_and_social_criteria():
    patient = {
        'data_nascimento': '1990-01-01',
        'queixa_principal': 'Dor espontanea no elemento 36, piora durante a noite.',
        'dor_dentes_gengiva': 'Sim',
        'sofre_doenca_explica': 'Diabetes tipo 2',
        'profissao': 'Desempregado',
        'waiting_days': 75,
        'especialidade_nome': 'Endodontia',
    }

    result = calculate_priority_score(patient, today=dt.date(2026, 6, 5))

    assert result['score'] == 75
    assert result['risk_level'] == 'high'
    assert 'Dor aguda' in result['reasons']
    assert 'Diabetes' in result['reasons']
    assert 'Vulnerabilidade socioeconômica' in result['reasons']
    assert 'Espera prolongada' in result['reasons']
    assert any(reason['points'] == 20 for reason in result['reason_details'] if reason['label'] == 'Espera prolongada')


def test_risk_level_boundaries():
    assert get_risk_level(100) == 'critical'
    assert get_risk_level(50) == 'high'
    assert get_risk_level(25) == 'medium'
    assert get_risk_level(24) == 'routine'


def test_command_center_filters_normalize_ids_and_date_range():
    filters = normalize_command_center_filters({
        'municipio_id': '3',
        'especialidade_id': '5',
        'professional_id': '9',
        'execution_unit': 'unidade_apoio',
        'start_date': '2026-06-30',
        'end_date': '2026-06-01',
    })

    assert filters['municipio_id'] == 3
    assert filters['especialidade_id'] == 5
    assert filters['professional_id'] == 9
    assert filters['execution_unit'] == 'unidade_apoio'
    assert filters['start_date'] == dt.date(2026, 6, 1)
    assert filters['end_date'] == dt.date(2026, 6, 30)
    assert filters['active'] is True

    invalid_unit = normalize_command_center_filters({'execution_unit': 'unidade_inexistente'})
    assert invalid_unit['execution_unit'] is None
    assert invalid_unit['active'] is False


def test_operational_goals_calculate_automatic_targets_and_statuses():
    goals = build_operational_goals(
        production_count=8,
        agenda={
            'pending': 1,
            'confirmed': 1,
            'done': 8,
            'canceled': 0,
            'no_show': 1,
            'total': 11,
        },
        pending_treatments=2,
        queue_metrics={
            'wait_time': {
                'active_count': 20,
                'over_30_days': 3,
            },
        },
    )
    by_id = {goal['id']: goal for goal in goals}

    assert by_id['clinical_production']['target'] == 10
    assert by_id['clinical_production']['progress'] == 80
    assert by_id['clinical_production']['status'] == 'attention'
    assert by_id['attendance']['current'] == 90.9
    assert by_id['attendance']['status'] == 'achieved'
    assert by_id['treatment_completion']['current'] == 80
    assert by_id['treatment_completion']['status'] == 'achieved'
    assert by_id['queue_reduction']['target'] == 5
    assert by_id['queue_reduction']['status'] == 'achieved'


def test_daily_operational_summary_builds_filtered_kpis_and_recommendations(monkeypatch):
    fake_data = {
        'today': dt.date(2026, 6, 5),
        'patients_today': [{'patient_nome': 'Paciente A'}],
        'production': {'today': 7, 'month': 7},
        'agenda': {
            'pending': 2,
            'confirmed': 3,
            'done': 4,
            'canceled': 1,
            'no_show': 2,
            'total': 12,
        },
        'red_alert_count': 1,
        'pending_treatments': 5,
        'priority_queue': [{
            'nome': 'Prioritário',
            'score': 120,
            'reasons': ['Suspeita de neoplasia'],
        }],
        'priority_queue_total': 11,
        'specialty_bottlenecks': [{
            'especialidade': 'Estomatologia',
            'total': 4,
            'critical': 1,
            'high': 2,
            'max_waiting_days': 95,
        }],
        'clinical_pending': {
            'pending_exams': {'total': 0, 'patient_count': 0, 'items': []},
            'unsigned_documents': {'total': 4, 'patient_count': 3, 'items': []},
            'total': 4,
        },
        'queue_metrics': {
            'without_return': {
                'total_over_30': 2,
                'over_60_days': 1,
                'over_90_days': 0,
                'items': [],
            },
            'wait_time': {
                'current_avg_days': 10,
                'active_avg_days': 22,
                'max_active_wait_days': 90,
                'over_30_days': 2,
                'over_60_days': 1,
                'over_90_days': 0,
            },
            'agenda_bottlenecks': {'total_open': 5, 'items': []},
        },
        'alerts': [{
            'title': 'Alerta vermelho oncológico',
            'severity': 'critical',
            'message': '1 paciente em alerta vermelho.',
        }],
        'operational_goals': [
            {
                'id': 'clinical_production',
                'label': 'Produção clínica',
                'value_label': '7 / 10',
                'status': 'critical',
                'status_label': 'Crítica',
                'detail': 'Meta de produção abaixo do esperado.',
            },
            {
                'id': 'attendance',
                'label': 'Comparecimento',
                'value_label': '90% / 85%',
                'status': 'achieved',
                'status_label': 'Meta atingida',
                'detail': 'Comparecimento adequado.',
            },
        ],
        'critical_alert_count': 1,
        'filters': {
            'municipio_id': 3,
            'especialidade_id': 5,
            'professional_id': 9,
            'start_date': dt.date(2026, 6, 1),
            'end_date': dt.date(2026, 6, 5),
            'active': True,
        },
        'filter_options': {
            'municipalities': [{'id': 3, 'nome': 'Arapiraca'}],
            'specialties': [{'id': 5, 'nome': 'Estomatologia'}],
            'professionals': [{'id': 9, 'name': 'Dra. Teste'}],
        },
    }

    monkeypatch.setattr(command_center_service, 'get_command_center_data', lambda filters=None: fake_data)

    summary = get_daily_operational_summary(
        filters={'municipio_id': '3'},
        generated_by='Coordenação',
        generated_at=dt.datetime(2026, 6, 5, 8, 30),
    )

    assert summary['period_label'] == '01/06/2026 a 05/06/2026'
    assert {'label': 'Município', 'value': 'Arapiraca'} in summary['applied_filters']
    assert {'label': 'Especialidade', 'value': 'Estomatologia'} in summary['applied_filters']
    assert {'label': 'Profissional', 'value': 'Dra. Teste'} in summary['applied_filters']
    assert summary['kpis'][0]['value'] == 1
    assert summary['kpis'][3]['value'] == 11
    assert summary['kpis'][-1]['value'] == '1/2'
    assert any('alertas críticos' in item for item in summary['recommendations'])
    assert any('documentos sem assinatura' in item for item in summary['recommendations'])
    assert any('metas críticas' in item for item in summary['recommendations'])


def test_daily_operational_summary_csv_rows_include_core_sections():
    summary = {
        'period_label': '05/06/2026',
        'generated_by': 'Coordenação',
        'generated_at': dt.datetime(2026, 6, 5, 8, 30),
        'applied_filters': [{'label': 'Período', 'value': '05/06/2026'}],
        'kpis': [{'label': 'Alertas críticos', 'value': 2, 'detail': '2 alertas ativos'}],
        'recommendations': ['Priorizar alertas críticos.'],
        'source': {
            'operational_goals': [{
                'label': 'Produção clínica',
                'value_label': '8 / 10',
                'status_label': 'Atenção',
                'detail': 'Alvo automático de produção.',
            }],
            'alerts': [{
                'title': 'Fila crítica',
                'severity': 'critical',
                'message': 'Fila de prioridade clínica com 10 ou mais pacientes ativos.',
            }],
            'priority_queue': [{
                'nome': 'Paciente Prioritário',
                'score': 110,
                'reasons': ['Suspeita de neoplasia'],
            }],
            'specialty_bottlenecks': [{
                'especialidade': 'Endodontia',
                'total': 3,
                'max_waiting_days': 80,
            }],
        },
    }

    rows = build_daily_summary_csv_rows(summary)

    assert ['Resumo', 'Período', '05/06/2026', ''] in rows
    assert ['Indicador', 'Alertas críticos', 2, '2 alertas ativos'] in rows
    assert ['Meta operacional', 'Produção clínica', '8 / 10', 'Atenção - Alvo automático de produção.'] in rows
    assert ['Alerta', 'Fila crítica', 'critical', 'Fila de prioridade clínica com 10 ou mais pacientes ativos.'] in rows
    assert ['Fila prioritária', 'Paciente Prioritário', 110, 'Suspeita de neoplasia'] in rows
    assert ['Recomendação', 'Priorizar alertas críticos.', '', ''] in rows


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
    assert 'latest_anamnesis' in sql
    assert 'waiting_days' in sql
    assert 'esp.nome as especialidade_nome' in sql
    assert 'COUNT(DISTINCT c.id)' in sql
    assert 'COUNT(DISTINCT tp.id)' in sql
    assert 'c.data_consulta >= e.data_registro' in sql


def test_priority_queue_query_applies_phase291_filters(monkeypatch):
    captured = {}

    def fake_query(sql, params=(), one=False):
        captured['sql'] = sql
        captured['params'] = params
        return []

    monkeypatch.setattr(command_center_service, 'query', fake_query)

    result = get_priority_queue(
        limit=None,
        filters={
            'municipio_id': '3',
            'especialidade_id': '5',
            'professional_id': '9',
            'execution_unit': 'unidade_apoio',
            'start_date': '2026-06-01',
            'end_date': '2026-06-30',
        },
    )

    sql = captured['sql']
    assert result == []
    assert 's.municipio_id = %s' in sql
    assert 's.especialidade_id = %s' in sql
    assert 'ta.execution_unit = %s' not in sql
    assert 'c_filter.dentista_id = %s' in sql
    assert 'c_filter.execution_unit = %s' in sql
    assert 'DATE(COALESCE(s.vinculada_em' in sql
    assert captured['params'] == (3, 5, 9, '2026-06-01', '2026-06-30', 'unidade_apoio', '2026-06-01', '2026-06-30')


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
            'especialidade_nome': 'Dentística',
            'waiting_days': None,
        },
        {
            'id': 1,
            'nome': 'Prioridade',
            'data_nascimento': '1950-01-01',
            'suspeita_neoplasia': True,
            'no_show_count': 2,
            'pending_treatments': 3,
            'lesion_days_without_return': 20,
            'especialidade_nome': 'Estomatologia',
            'waiting_days': 95,
        },
    ]

    monkeypatch.setattr(command_center_service, 'query', lambda *args, **kwargs: rows)

    full_queue = get_priority_queue(limit=None)

    assert [patient['nome'] for patient in full_queue] == ['Prioridade', 'Rotina']
    assert [patient['nome'] for patient in get_priority_queue(limit=1)] == ['Prioridade']


def test_specialty_bottlenecks_rank_critical_waiting_specialties():
    queue = [
        {
            'nome': 'Paciente A',
            'score': 130,
            'risk_level': 'critical',
            'especialidade_nome': 'Endodontia',
            'waiting_days': 92,
            'municipio_nome': 'Arapiraca',
            'atendido_em': 'Centro - Arapiraca',
        },
        {
            'nome': 'Paciente B',
            'score': 70,
            'risk_level': 'high',
            'especialidade_nome': 'Endodontia',
            'waiting_days': 45,
            'municipio_nome': 'Penedo',
            'atendido_em': 'Centro - Penedo',
        },
        {
            'nome': 'Paciente C',
            'score': 60,
            'risk_level': 'high',
            'especialidade_nome': 'Prótese Dentária',
            'waiting_days': 120,
            'municipio_nome': 'Penedo',
            'atendido_em': 'Centro - Penedo',
        },
    ]

    bottlenecks = get_specialty_bottlenecks(queue)

    assert bottlenecks[0]['especialidade'] == 'Endodontia'
    assert bottlenecks[0]['total'] == 2
    assert bottlenecks[0]['critical'] == 1
    assert bottlenecks[0]['max_waiting_days'] == 92
    assert bottlenecks[0]['oldest_patient'] == 'Paciente A'
    assert bottlenecks[0]['municipality_count'] == 2


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
    monkeypatch.setattr(command_center_service, 'get_priority_queue', lambda limit=None, filters=None: priority_queue)
    monkeypatch.setattr(command_center_service, 'get_demand_forecast_snapshot', lambda today=None, filters=None: {'window_days': 90, 'specialties': []})
    monkeypatch.setattr(command_center_service, 'get_queue_operational_metrics', lambda filters=None, today=None: {
        'without_return': {'total_over_30': 0, 'items': []},
        'agenda_bottlenecks': {'total_open': 0, 'items': []},
    })
    monkeypatch.setattr(command_center_service, 'get_inventory_alerts', lambda limit=20: [])

    data = get_command_center_data()
    alert_types = {alert['type'] for alert in data['alerts']}

    assert len(data['priority_queue']) == 12
    assert 'two_no_shows' in alert_types


def test_operational_alert_builder_includes_specialty_bottleneck():
    alerts = build_operational_alerts(
        red_alert_count=0,
        pending_treatments=0,
        agenda_by_status={},
        priority_queue=[],
        specialty_bottlenecks=[{
            'especialidade': 'Endodontia',
            'total': 4,
            'critical': 1,
            'high': 2,
            'max_waiting_days': 95,
        }],
    )

    assert alerts[0]['type'] == 'critical_specialty_bottleneck'
    assert alerts[0]['severity'] == 'critical'
    assert 'Endodontia' in alerts[0]['message']


def test_operational_alert_builder_includes_phase29_pending_clinical_alerts():
    alerts = build_operational_alerts(
        red_alert_count=0,
        pending_treatments=0,
        agenda_by_status={},
        priority_queue=[],
        clinical_pending={
            'pending_exams': {'total': 3, 'patient_count': 2, 'items': []},
            'unsigned_documents': {'total': 4, 'patient_count': 3, 'items': []},
        },
    )
    alert_types = {alert['type'] for alert in alerts}

    assert 'pending_exams' not in alert_types
    assert 'unsigned_documents' in alert_types
    assert all(alert['severity'] == 'warning' for alert in alerts)


def test_operational_alert_builder_includes_phase292_queue_metrics():
    alerts = build_operational_alerts(
        red_alert_count=0,
        pending_treatments=0,
        agenda_by_status={},
        priority_queue=[],
        queue_metrics={
            'without_return': {'total_over_30': 2},
            'agenda_bottlenecks': {'total_open': 5},
        },
    )
    alert_types = {alert['type'] for alert in alerts}

    assert 'queue_without_return' in alert_types
    assert 'agenda_bottleneck' in alert_types


def test_pending_exam_alert_summary_is_disabled():
    summary = get_pending_exam_alert_summary(patient_id=7)

    assert summary == {'total': 0, 'patient_count': 0, 'items': []}


def test_pending_exam_alert_summary_ignores_filters_without_querying(monkeypatch):
    monkeypatch.setattr(
        command_center_service,
        'query',
        lambda *args, **kwargs: pytest.fail('não deve consultar validação de exames'),
    )
    summary = get_pending_exam_alert_summary(filters={
        'municipio_id': '3',
        'especialidade_id': '5',
        'professional_id': '9',
        'start_date': '2026-06-01',
        'end_date': '2026-06-30',
    })

    assert summary['total'] == 0


def test_unsigned_document_alert_summary_uses_clinical_document_sources(monkeypatch):
    captured = {}

    def fake_query(sql, params=(), one=False):
        captured.setdefault('sql', []).append(sql)
        if one:
            return {'total': 3, 'patient_count': 2}
        return [{
            'patient_id': 9,
            'patient_name': 'Paciente Assinatura',
            'document_type': 'atendimento',
            'document_label': 'Evolução clínica',
            'missing_signatures': 'executor',
        }]

    monkeypatch.setattr(command_center_service, 'query', fake_query)

    summary = get_unsigned_document_alert_summary(limit=4)

    sql = '\n'.join(captured['sql'])
    assert 'FROM atendimentos' in sql
    assert 'FROM prosthesis_etapas' in sql
    assert 'FROM endodontia_followup' in sql
    assert 'UNION ALL' in sql
    assert "a.executor_id IS NULL" in sql
    assert 'a.assinatura_paciente_base64' not in sql
    assert 'a.validator_id' not in sql
    assert summary['total'] == 3
    assert summary['patient_count'] == 2
    assert summary['items'][0]['missing_signatures'] == 'executor'


def test_patient_clinical_alert_summary_ignores_exam_validation(monkeypatch):
    monkeypatch.setattr(
        command_center_service,
        'get_pending_exam_alert_summary',
        lambda limit=5, patient_id=None: {'total': 1, 'patient_count': 1, 'items': [{'id': 1}]},
    )
    monkeypatch.setattr(
        command_center_service,
        'get_unsigned_document_alert_summary',
        lambda limit=5, patient_id=None: {'total': 2, 'patient_count': 1, 'items': [{'id': 2}]},
    )
    monkeypatch.setattr(
        command_center_service,
        'get_overdue_endodontia_return_summary',
        lambda limit=5, patient_id=None: {'total': 1, 'patient_count': 1, 'items': [{'id': 3}]},
    )
    monkeypatch.setattr(
        command_center_service,
        'get_unrestored_endodontia_summary',
        lambda limit=5, patient_id=None: {'total': 1, 'patient_count': 1, 'items': [{'id': 4}]},
    )
    monkeypatch.setattr(
        command_center_service,
        'get_overdue_endodontia_proservation_summary',
        lambda limit=5, patient_id=None: {'total': 1, 'patient_count': 1, 'items': [{'id': 5}]},
    )

    summary = get_patient_clinical_alert_summary(42)

    assert summary['total'] == 5
    assert summary['has_alerts'] is True
    assert summary['pending_exams']['total'] == 1
    assert summary['unsigned_documents']['total'] == 2
    assert summary['overdue_endodontia_returns']['total'] == 1
    assert summary['unrestored_endodontia']['total'] == 1
    assert summary['overdue_endodontia_proservations']['total'] == 1


def test_overdue_endodontia_return_summary_filters_open_cases(monkeypatch):
    captured = []

    def fake_query(sql, params=(), one=False):
        captured.append((sql, params, one))
        if one:
            return {'total': 1, 'patient_count': 1}
        return [{
            'id': 7,
            'patient_id': 9,
            'patient_name': 'Paciente Endo',
            'elemento_dentario': '36',
            'status_tratamento': 'aguardando_retorno',
        }]

    monkeypatch.setattr(command_center_service, 'query', fake_query)

    summary = command_center_service.get_overdue_endodontia_return_summary(limit=3)

    sql = '\n'.join(item[0] for item in captured)
    assert "e.proxima_sessao_prevista < CURRENT_DATE" in sql
    assert "COALESCE(e.status_tratamento, 'aguardando_inicio') IN ('em_andamento', 'aguardando_retorno')" in sql
    assert "COALESCE(e.status, 'Ativo') != 'Cancelado'" in sql
    assert summary['total'] == 1
    assert summary['items'][0]['elemento_dentario'] == '36'


def test_unrestored_endodontia_summary_filters_obturated_cases(monkeypatch):
    captured = []

    def fake_query(sql, params=(), one=False):
        captured.append((sql, params, one))
        if one:
            return {'total': 1, 'patient_count': 1}
        return [{
            'id': 8,
            'patient_id': 9,
            'patient_name': 'Paciente Endo',
            'elemento_dentario': '36',
            'status_tratamento': 'obturado_aguardando_restauracao',
        }]

    monkeypatch.setattr(command_center_service, 'query', fake_query)

    summary = command_center_service.get_unrestored_endodontia_summary(limit=3)

    sql = '\n'.join(item[0] for item in captured)
    assert "COALESCE(e.status_tratamento, 'aguardando_inicio') = 'obturado_aguardando_restauracao'" in sql
    assert "COALESCE(e.restauracao_definitiva_registrada, FALSE) = FALSE" in sql
    assert "COALESCE(e.status, 'Ativo') != 'Cancelado'" in sql
    assert summary['total'] == 1
    assert summary['items'][0]['elemento_dentario'] == '36'


def test_overdue_endodontia_proservation_summary_filters_planned_returns(monkeypatch):
    captured = []

    def fake_query(sql, params=(), one=False):
        captured.append((sql, params, one))
        if one:
            return {'total': 1, 'patient_count': 1}
        return [{
            'id': 4,
            'patient_id': 9,
            'patient_name': 'Paciente Endo',
            'elemento_dentario': '36',
            'tipo_retorno': 'proservacao_6m',
            'data_prevista': dt.date(2026, 12, 12),
            'status': 'planejado',
        }]

    monkeypatch.setattr(command_center_service, 'query', fake_query)

    summary = command_center_service.get_overdue_endodontia_proservation_summary(limit=3)

    sql = '\n'.join(item[0] for item in captured)
    assert 'FROM endodontia_proservacao pr' in sql
    assert 'pr.data_prevista < CURRENT_DATE' in sql
    assert "COALESCE(pr.status, 'planejado') IN ('planejado', 'reagendado')" in sql
    assert "COALESCE(e.status, 'Ativo') != 'Cancelado'" in sql
    assert summary['total'] == 1
    assert summary['items'][0]['tipo_retorno'] == 'proservacao_6m'


def test_operational_alert_builder_includes_unrestored_endodontia():
    alerts = build_operational_alerts(
        red_alert_count=0,
        pending_treatments=0,
        agenda_by_status={},
        priority_queue=[],
        clinical_pending={
            'unrestored_endodontia': {'total': 2, 'patient_count': 2, 'items': []},
        },
    )

    assert alerts[0]['type'] == 'unrestored_endodontia'
    assert alerts[0]['severity'] == 'warning'
    assert 'restauração definitiva' in alerts[0]['message']


def test_operational_alert_builder_includes_overdue_proservation():
    alerts = build_operational_alerts(
        red_alert_count=0,
        pending_treatments=0,
        agenda_by_status={},
        priority_queue=[],
        clinical_pending={
            'overdue_endodontia_proservations': {'total': 3, 'patient_count': 2, 'items': []},
        },
    )

    assert alerts[0]['type'] == 'overdue_endodontia_proservations'
    assert alerts[0]['severity'] == 'warning'
    assert 'proservação' in alerts[0]['title'].lower()


def test_queue_operational_metrics_compare_wait_time_and_no_return(monkeypatch):
    queue_rows = [
        {
            'ticket_id': 1,
            'patient_id': 10,
            'patient_name': 'Atual A',
            'especialidade': 'Endodontia',
            'municipio': 'Arapiraca',
            'entry_at': dt.date(2026, 5, 20),
            'first_attended_at': dt.date(2026, 6, 1),
        },
        {
            'ticket_id': 2,
            'patient_id': 11,
            'patient_name': 'Atual B',
            'especialidade': 'Prótese Dentária',
            'municipio': 'Penedo',
            'entry_at': dt.date(2026, 5, 25),
            'first_attended_at': dt.date(2026, 6, 3),
        },
        {
            'ticket_id': 3,
            'patient_id': 12,
            'patient_name': 'Anterior',
            'especialidade': 'Cirurgia Oral',
            'municipio': 'Maceió',
            'entry_at': dt.date(2026, 4, 10),
            'first_attended_at': dt.date(2026, 4, 30),
        },
        {
            'ticket_id': 4,
            'patient_id': 13,
            'patient_name': 'Sem Retorno',
            'especialidade': 'Estomatologia',
            'municipio': 'Arapiraca',
            'entry_at': dt.date(2026, 4, 1),
            'first_attended_at': None,
        },
    ]
    agenda_rows = [{
        'professional_id': 7,
        'professional_name': 'Dra. Agenda',
        'total': 10,
        'pending': 3,
        'confirmed': 2,
        'done': 4,
        'no_show': 1,
        'canceled': 0,
    }]

    def fake_query(sql, params=(), one=False):
        if 'WITH queue_entries' in sql:
            return queue_rows
        if 'FROM consultas c' in sql and 'COUNT(*) FILTER' in sql:
            return agenda_rows
        return []

    monkeypatch.setattr(command_center_service, 'query', fake_query)

    metrics = get_queue_operational_metrics(today=dt.date(2026, 6, 5))

    assert metrics['wait_time']['current_avg_days'] == 10.5
    assert metrics['wait_time']['previous_avg_days'] == 20
    assert metrics['wait_time']['reduction_days'] == 9.5
    assert metrics['wait_time']['trend_label'] == 'redução'
    assert metrics['wait_time']['over_60_days'] == 1
    assert metrics['without_return']['total_over_30'] == 1
    assert metrics['without_return']['items'][0]['patient_name'] == 'Sem Retorno'
    assert metrics['agenda_bottlenecks']['items'][0]['open_count'] == 5
    assert metrics['agenda_bottlenecks']['items'][0]['completion_rate'] == 40


def test_queue_operational_metrics_applies_phase292_filters(monkeypatch):
    captured = {}

    def fake_query(sql, params=(), one=False):
        if 'WITH queue_entries' in sql:
            captured['queue_sql'] = sql
            captured['queue_params'] = params
        return []

    monkeypatch.setattr(command_center_service, 'query', fake_query)

    metrics = get_queue_operational_metrics(
        filters={
            'municipio_id': '3',
            'especialidade_id': '5',
            'professional_id': '9',
            'start_date': '2026-06-01',
            'end_date': '2026-06-30',
        },
        today=dt.date(2026, 6, 5),
    )

    assert 's.municipio_id = %s' in captured['queue_sql']
    assert 's.especialidade_id = %s' in captured['queue_sql']
    assert 'c_filter.dentista_id = %s' in captured['queue_sql']
    assert captured['queue_params'] == (3, 5, 9, '2026-06-01', '2026-06-30')
    assert metrics['period_start'] == dt.date(2026, 6, 1)
    assert metrics['period_end'] == dt.date(2026, 6, 30)


def test_demand_forecast_groups_by_specialty_territory_period_and_action(monkeypatch):
    rows = [
        {
            'especialidade': 'Endodontia',
            'bairro': 'Centro - Arapiraca',
            'municipio': 'Arapiraca',
            'triagem_acao_id': 7,
            'triagem_local': 'Ginásio Municipal',
            'entry_date': dt.date(2026, 6, 1),
        },
        {
            'especialidade': 'Endodontia',
            'bairro': 'Centro - Arapiraca',
            'municipio': 'Arapiraca',
            'triagem_acao_id': 7,
            'triagem_local': 'Ginásio Municipal',
            'entry_date': dt.date(2026, 5, 20),
        },
        {
            'especialidade': 'Prótese Dentária',
            'bairro': 'Baixa renda - Penedo',
            'municipio': 'Penedo',
            'triagem_acao_id': 8,
            'triagem_local': 'UBS Centro',
            'entry_date': dt.date(2026, 4, 20),
        },
    ]

    monkeypatch.setattr(command_center_service, 'query', lambda *args, **kwargs: rows)

    forecast = get_demand_forecast_snapshot(today=dt.date(2026, 6, 5))

    assert forecast['specialties'][0]['especialidade'] == 'Endodontia'
    assert forecast['specialties'][0]['projected_next_30'] == 4
    assert forecast['municipalities'][0]['municipio'] == 'Arapiraca'
    assert forecast['neighborhoods'][0]['bairro'] == 'Centro'
    assert forecast['triage_actions'][0]['acao'] == 'Ação #7 - Ginásio Municipal'
    assert {row['periodo'] for row in forecast['periods']} >= {'2026-04', '2026-05', '2026-06'}
