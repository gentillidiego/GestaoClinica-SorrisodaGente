import datetime as dt

import services.traceability_service as traceability_service
from services.traceability_service import TraceabilityService, _as_datetime, _sort_events


def test_as_datetime_accepts_supported_formats():
    assert _as_datetime('2026-05-30').date() == dt.date(2026, 5, 30)
    assert _as_datetime('2026-05-30T12:34:56') == dt.datetime(2026, 5, 30, 12, 34, 56)
    assert _as_datetime('30/05/2026').date() == dt.date(2026, 5, 30)
    assert _as_datetime(dt.date(2026, 5, 30)) == dt.datetime(2026, 5, 30)
    assert _as_datetime('sem data') is None


def test_sort_events_discards_undated_and_orders_descending():
    events = [
        {'occurred_at': dt.datetime(2026, 5, 28), 'title': 'antigo'},
        {'occurred_at': None, 'title': 'sem data'},
        {'occurred_at': dt.datetime(2026, 5, 30), 'title': 'novo'},
    ]

    sorted_events = _sort_events(events)

    assert [event['title'] for event in sorted_events] == ['novo', 'antigo']


def test_patient_traceability_summary_groups_categories(monkeypatch):
    def fake_timeline(patient_id):
        assert patient_id == 42
        return [
            {'occurred_at': dt.datetime(2026, 5, 30), 'category': 'Agenda'},
            {'occurred_at': dt.datetime(2026, 5, 29), 'category': 'Agenda'},
            {'occurred_at': dt.datetime(2026, 5, 28), 'category': 'Exame'},
        ]

    monkeypatch.setattr(TraceabilityService, 'get_patient_timeline', fake_timeline)

    summary = TraceabilityService.get_patient_traceability_summary(42)

    assert summary['total_events'] == 3
    assert summary['categories'] == {'Agenda': 2, 'Exame': 1}
    assert summary['last_event']['occurred_at'] == dt.datetime(2026, 5, 30)
    assert summary['first_event']['occurred_at'] == dt.datetime(2026, 5, 28)


def test_patient_timeline_includes_cadastro_and_triage(monkeypatch):
    calls = []

    def fake_query(sql, params=(), one=False):
        calls.append(sql)
        if 'FROM patients' in sql and one:
            return {'id': 7, 'nome': 'Paciente Teste', 'criado_em': dt.datetime(2026, 5, 1, 8, 0)}
        if 'FROM triagem_senhas' in sql:
            return [{
                'codigo': 'ARA-P-001',
                'status': 'Vinculada',
                'vinculada_em': dt.datetime(2026, 5, 2, 9, 0),
                'entregue_em': None,
                'criado_em': None,
                'especialidade_nome': 'Prótese Dentária',
                'municipio_nome': 'Arapiraca',
                'data_acao': dt.date(2026, 5, 2),
                'triagem_local': 'UBS Central',
            }]
        return []

    monkeypatch.setattr(traceability_service, 'query', fake_query)

    timeline = TraceabilityService.get_patient_timeline(7)

    assert timeline[0]['category'] == 'Triagem'
    assert timeline[0]['status'] == 'Vinculada'
    assert timeline[1]['category'] == 'Cadastro'
    assert any('FROM patient_tcle' in sql for sql in calls)
