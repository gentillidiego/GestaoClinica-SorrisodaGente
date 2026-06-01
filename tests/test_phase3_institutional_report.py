import datetime as dt

from constants import Role, role_has_permission
import services.institutional_report_service as institutional_report_service
from services.institutional_report_service import (
    build_highlights,
    build_recommendations,
    build_report_charts,
    calculate_file_sha256,
    finalize_generated_report,
    get_institutional_report,
    get_report_profile,
    get_report_types_for_role,
    register_generated_report,
    role_can_access_report_type,
)
from services.report_generation_service import (
    build_scheduled_key,
    parse_month_period,
    resolve_report_types,
)


def _executive_fixture():
    return {
        'summary': {
            'completed_procedures': 40,
            'patients_seen': 22,
            'queue_scheduled_or_seen': 12,
            'queue_resolution_rate': 60.0,
            'queue_repressed': 8,
            'no_show_rate': 18.0,
            'no_shows': 9,
            'neighborhoods': 6,
            'reached_patients': 30,
        },
        'monthly_comparison': [{'label': '05/2026'}],
        'neighborhood_ranking': [{'bairro': 'Centro', 'reached_patients': 12}],
        'specialty_ranking': [{'especialidade': 'Prótese', 'repressed': 5}],
    }


def _epidemiology_fixture():
    return {
        'summary': {
            'cancer_suspicions': 3,
            'biopsy_referrals': 2,
            'prosthetic_need': 11,
        },
        'lesion_locations': [{'localizacao': 'Língua', 'lesion_records': 2}],
    }


def test_reports_permission_allows_management_roles():
    assert role_has_permission(Role.ADMIN, 'reports:view')
    assert role_has_permission(Role.BI, 'reports:view')
    assert role_has_permission(Role.EPIDEMIOLOGIA, 'reports:view')
    assert role_has_permission(Role.PREFEITURA, 'reports:view')
    assert role_has_permission(Role.SSA, 'reports:view')
    assert role_has_permission(Role.SMS, 'reports:view')
    assert role_has_permission(Role.RECEPCAO, 'reports:view') is False


def test_report_type_access_is_limited_by_government_role():
    assert get_report_types_for_role(Role.PREFEITURA) == ['institucional']
    assert get_report_types_for_role(Role.SSA) == ['ssa']
    assert get_report_types_for_role(Role.SMS) == ['sms']
    assert set(get_report_types_for_role(Role.BI)) == {'institucional', 'ssa', 'sms'}
    assert role_can_access_report_type(Role.SSA, 'ssa')
    assert role_can_access_report_type(Role.SSA, 'sms') is False


def test_institutional_highlights_use_executive_and_epidemiology_data():
    highlights = build_highlights(_executive_fixture(), _epidemiology_fixture())
    by_label = {item['label']: item for item in highlights}

    assert by_label['Produção clínica']['value'] == 40
    assert by_label['Pacientes atendidos']['value'] == 22
    assert by_label['Fila encaminhada']['detail'] == '60.0% da demanda triada'
    assert by_label['Suspeitas oncológicas']['value'] == 3
    assert by_label['Absenteísmo']['value'] == '18.0%'


def test_institutional_recommendations_include_actionable_alerts():
    recommendations = build_recommendations(_executive_fixture(), _epidemiology_fixture())

    assert any('demanda reprimida' in item for item in recommendations)
    assert any('absenteísmo' in item for item in recommendations)
    assert any('fila oncológica' in item for item in recommendations)
    assert any('capacidade protética' in item for item in recommendations)


def test_report_profiles_support_ssa_and_sms_recortes():
    assert get_report_profile('ssa')['title'] == 'Relatório Mensal para SSA'
    assert get_report_profile('sms')['title'] == 'Relatório Mensal para SMS'
    assert get_report_profile('tipo_invalido')['title'] == 'Relatório Institucional Mensal'

    ssa_recommendations = build_recommendations(_executive_fixture(), _epidemiology_fixture(), 'ssa')
    sms_recommendations = build_recommendations(_executive_fixture(), _epidemiology_fixture(), 'sms')

    assert any('biópsia' in item for item in ssa_recommendations)
    assert any('busca ativa municipal' in item for item in sms_recommendations)


def test_get_institutional_report_composes_pdf_context(monkeypatch):
    monkeypatch.setattr(
        institutional_report_service,
        'get_executive_bi_dashboard',
        lambda start, end, today=None: _executive_fixture(),
    )
    monkeypatch.setattr(
        institutional_report_service,
        'get_epidemiology_dashboard',
        lambda start, end, today=None: _epidemiology_fixture(),
    )

    report = get_institutional_report(
        start_date='2026-05-01',
        end_date='2026-05-30',
        today=dt.date(2026, 5, 30),
    )

    assert report['period']['start'] == dt.date(2026, 5, 1)
    assert report['period']['end'] == dt.date(2026, 5, 30)
    assert report['meta']['title'] == 'Relatório Institucional Mensal'
    assert report['top_neighborhoods'][0]['bairro'] == 'Centro'
    assert report['top_specialties'][0]['especialidade'] == 'Prótese'
    assert report['top_lesions'][0]['localizacao'] == 'Língua'
    assert report['charts']['neighborhoods'][0]['percent'] == 100.0


def test_build_report_charts_normalizes_percentages():
    executive = _executive_fixture()
    executive['monthly_comparison'] = [
        {'label': '04/2026', 'completed_procedures': 20},
        {'label': '05/2026', 'completed_procedures': 40},
    ]
    executive['neighborhood_ranking'] = [
        {'bairro': 'Centro', 'reached_patients': 10},
        {'bairro': 'Farol', 'reached_patients': 5},
    ]

    charts = build_report_charts(executive, _epidemiology_fixture())

    assert charts['monthly_production'][0]['percent'] == 50.0
    assert charts['monthly_production'][1]['percent'] == 100.0
    assert charts['neighborhoods'][1]['percent'] == 50.0


def test_register_generated_report_persists_metadata(monkeypatch):
    captured = {}
    report = {
        'report_type': 'institucional',
        'period': {
            'start': dt.date(2026, 5, 1),
            'end': dt.date(2026, 5, 30),
        },
        'highlights': [{'label': 'Produção clínica', 'value': 40, 'detail': 'procedimentos'}],
        'recommendations': ['Acompanhar indicadores.'],
        'meta': {
            'title': 'Relatório Institucional Mensal',
            'audience': 'Gestão geral',
            'focus': ['prestação de contas'],
        },
    }

    def fake_execute(sql, params=()):
        captured['sql'] = sql
        captured['params'] = params
        return 99

    monkeypatch.setattr(institutional_report_service, 'execute', fake_execute)

    report_id = register_generated_report(
        report,
        filename='relatorio.pdf',
        file_path='/tmp/relatorio.pdf',
        generated_by=7,
        task_id='task-1',
    )

    assert report_id == 99
    assert 'INSERT INTO generated_reports' in captured['sql']
    assert captured['params'][0] == 'institucional'
    assert captured['params'][4] == 'relatorio.pdf'
    assert captured['params'][7] == 7
    assert captured['params'][8] == 'queued'
    assert captured['params'][10] is None
    assert captured['params'][11] == 'painel_seguro'


def test_finalize_generated_report_hashes_file_and_registers_signature(monkeypatch, tmp_path):
    calls = []
    pdf = tmp_path / 'relatorio.pdf'
    pdf.write_bytes(b'conteudo-pdf')

    def fake_execute(sql, params=()):
        calls.append((sql, params))

    monkeypatch.setattr(institutional_report_service, 'execute', fake_execute)

    signature_hash = finalize_generated_report(42, str(pdf), signed_by=7, signer_name='Gestor')

    assert signature_hash == calculate_file_sha256(str(pdf))
    assert len(calls) == 2
    assert 'UPDATE generated_reports' in calls[0][0]
    assert calls[0][1][0] == signature_hash
    assert 'INSERT INTO digital_signatures' in calls[1][0]
    assert calls[1][1][1] == '42'
    assert calls[1][1][6] == signature_hash


def test_monthly_report_generation_helpers():
    start, end = parse_month_period('2026-05')

    assert start == dt.date(2026, 5, 1)
    assert end == dt.date(2026, 5, 31)
    assert resolve_report_types('all') == ['institucional', 'ssa', 'sms']
    assert resolve_report_types('ssa') == ['ssa']
    assert build_scheduled_key('ssa', start, end) == 'scheduler:ssa:20260501:20260531'
