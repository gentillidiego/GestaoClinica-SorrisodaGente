import datetime as dt

from constants import Role, role_has_permission
import services.epidemiology_service as epidemiology_service
from services.epidemiology_service import (
    build_geo_payload,
    get_demographic_profile,
    get_epidemiology_dashboard,
    get_tooth_loss_metrics,
    normalize_period,
    percentage,
    _missing_teeth_from_odontogram,
)


def test_epidemiology_permission_is_available_to_management_roles():
    assert role_has_permission(Role.ADMIN, 'epidemiologia:view')
    assert role_has_permission(Role.COORDENACAO, 'epidemiologia:view')
    assert role_has_permission(Role.SSA_SMS, 'epidemiologia:view')
    assert role_has_permission(Role.EPIDEMIOLOGIA, 'epidemiologia:view')
    assert role_has_permission(Role.BI, 'epidemiologia:view')
    assert role_has_permission(Role.AUDITORIA, 'epidemiologia:view') is False


def test_normalize_period_defaults_and_swaps_inverted_dates():
    today = dt.date(2026, 5, 30)

    start, end = normalize_period(today=today)
    assert start == dt.date(2026, 5, 1)
    assert end == today

    start, end = normalize_period('2026-05-30', '2026-05-01', today=today)
    assert start == dt.date(2026, 5, 1)
    assert end == dt.date(2026, 5, 30)


def test_percentage_handles_zero_total():
    assert percentage(2, 4) == 50.0
    assert percentage(1, 3) == 33.3
    assert percentage(3, 0) == 0


def test_demographic_profile_groups_age_gender_and_occupation(monkeypatch):
    rows = [
        {'data_nascimento': '1960-05-30', 'genero': 'Fem', 'profissao': 'Agricultora'},
        {'data_nascimento': '2010-01-10', 'genero': 'Masc', 'profissao': ''},
        {'data_nascimento': '', 'genero': '', 'profissao': None},
    ]

    monkeypatch.setattr(epidemiology_service, 'query', lambda *args, **kwargs: rows)

    profile = get_demographic_profile(
        dt.date(2026, 5, 1),
        dt.date(2026, 5, 30),
        today=dt.date(2026, 5, 30),
    )

    age_groups = {item['label']: item['total'] for item in profile['age_groups']}
    occupations = {item['label']: item['total'] for item in profile['occupations']}

    assert profile['total'] == 3
    assert age_groups['60+'] == 1
    assert age_groups['13-17'] == 1
    assert age_groups['Não informado'] == 1
    assert occupations['Não informada'] == 2


def test_tooth_loss_metrics_parse_demo_and_odontogram_colors(monkeypatch):
    rows = [
        {'patient_id': 1, 'bairro': 'Centro', 'dentes_data': '{"ausentes": ["36", "46"]}'},
        {'patient_id': 2, 'bairro': 'Centro', 'dentes_data': '{"11": {"vestibular": "#2563eb"}}'},
        {'patient_id': 2, 'bairro': 'Centro', 'dentes_data': '{"11": {"palatina": "#2563eb"}, "12": {"oclusal": "#dc2626"}}'},
    ]

    monkeypatch.setattr(epidemiology_service, 'query', lambda *args, **kwargs: rows)

    assert _missing_teeth_from_odontogram('{"ausentes": ["36"], "11": {"vestibular": "#2563eb"}}') == {'36', '11'}

    metrics = get_tooth_loss_metrics(
        dt.date(2026, 5, 1),
        dt.date(2026, 5, 30),
        filters={'neighborhood': 'Centro'},
        today=dt.date(2026, 5, 30),
    )

    assert metrics == {
        'patients_with_tooth_loss': 2,
        'missing_teeth': 3,
        'avg_missing_teeth': 1.5,
    }


def test_geo_payload_projects_exact_and_fallback_coordinates(monkeypatch):
    locations = {
        'municipio': {
            1: {
                'latitude': -9.66599,
                'longitude': -35.735,
                'source': 'seed',
                'accuracy': 'centroide municipal',
            }
        },
        'bairro': {},
        'bairro_any': {},
        'unidade': {},
        'triagem_acao': {},
    }
    municipality_row = {
        'municipio_id': 1,
        'municipio': 'Maceió',
        'municipio_codigo': 'MCZ',
        'total_patients': 12,
        'lesion_records': 2,
        'cancer_suspicions': 1,
        'cancer_confirmed': 1,
        'no_shows': 2,
        'appointments': 8,
        'prosthetic_need': 3,
        'repressed_demand': 4,
        'patients_with_tooth_loss': 5,
        'missing_teeth': 8,
    }
    action_row = {
        'triagem_acao_id': 77,
        'local': 'UBS Centro',
        'data_acao': dt.date(2026, 5, 10),
        'municipio_id': 1,
        'municipio': 'Maceió',
        'total_patients': 5,
        'lesion_records': 1,
        'cancer_suspicions': 0,
        'cancer_confirmed': 0,
        'no_shows': 1,
        'appointments': 4,
        'prosthetic_need': 1,
        'repressed_demand': 2,
        'patients_with_tooth_loss': 1,
        'missing_teeth': 2,
    }

    monkeypatch.setattr(epidemiology_service, 'get_territorial_locations', lambda: locations)
    monkeypatch.setattr(epidemiology_service, 'get_municipality_indicators', lambda *args, **kwargs: [municipality_row])
    monkeypatch.setattr(epidemiology_service, 'get_triage_action_indicators', lambda *args, **kwargs: [action_row])
    monkeypatch.setattr(epidemiology_service, '_neighborhood_municipality_lookup', lambda *args, **kwargs: {
        'Centro': {'municipio_id': 1, 'municipio': 'Maceió'}
    })

    payload = build_geo_payload(
        dt.date(2026, 5, 1),
        dt.date(2026, 5, 30),
        neighborhoods=[{
            'bairro': 'Centro',
            'total_patients': 6,
            'lesion_records': 1,
            'cancer_suspicions': 0,
            'cancer_confirmed': 0,
            'no_shows': 1,
            'appointments': 5,
            'prosthetic_need': 1,
            'repressed_demand': 2,
            'patients_with_tooth_loss': 2,
            'missing_teeth': 3,
        }],
        today=dt.date(2026, 5, 30),
    )

    assert payload['coverage']['total'] == 3
    assert payload['coverage']['exact_coordinates'] == 1
    assert payload['coverage']['fallback_coordinates'] == 2
    assert payload['features'][0]['scope'] == 'municipio'
    assert payload['features'][0]['has_coordinates'] is True
    assert payload['features'][0]['x'] == 80.51
    assert payload['features'][0]['y'] == 52.07
    assert payload['bounds']['projection'] == 'alagoas_static_map'
    assert payload['features'][1]['map_ready'] is True
    assert payload['missing_coordinates'][0]['scope'] in {'acao', 'bairro'}


def test_epidemiology_dashboard_builds_summary_and_lists(monkeypatch):
    def fake_query(sql, params=(), one=False):
        if 'SELECT DISTINCT COALESCE' in sql:
            return [{'bairro': 'Centro'}, {'bairro': 'Tabuleiro'}]
        if 'FROM exam_odontograma' in sql:
            return [{'patient_id': 1, 'bairro': 'Centro', 'dentes_data': '{"ausentes": ["36", "46"]}'}]
        if 'FROM patients p' in sql and 'p.criado_em::date' in sql and one:
            return {'total': 4}
        if 'FROM estomatologia e' in sql and 'lesion_records' in sql and one:
            return {
                'lesion_records': 5,
                'lesion_patients': 3,
                'cancer_suspicions': 2,
                'cancer_confirmed': 1,
                'biopsy_referrals': 1,
            }
        if 'FROM consultas c' in sql and one:
            return {'total': 10, 'no_shows': 3, 'done': 6}
        if 'WITH prosthetic_need' in sql and one:
            return {'total': 2}
        if 'FROM triagem_senhas s' in sql and one:
            return {'total': 7}
        if 'WITH prosthetic_need' in sql:
            return [{
                'bairro': 'Centro',
                'total_patients': 10,
                'lesion_records': 4,
                'cancer_suspicions': 2,
                'cancer_confirmed': 1,
                'no_shows': 3,
                'appointments': 12,
                'prosthetic_need': 2,
                'repressed_demand': 5,
            }]
        if 'GROUP BY esp.nome' in sql:
            return [{'especialidade': 'Prótese Dentária', 'linked_patients': 8, 'repressed_demand': 6}]
        if 'GROUP BY localizacao' in sql:
            return [{'localizacao': 'Língua', 'lesion_records': 3, 'cancer_suspicions': 1, 'cancer_confirmed': 1, 'biopsy_referrals': 1}]
        if 'SELECT data_nascimento, genero, profissao' in sql:
            return [{'data_nascimento': '1970-01-01', 'genero': 'Fem', 'profissao': 'Autônoma'}]
        return []

    monkeypatch.setattr(epidemiology_service, 'query', fake_query)

    dashboard = get_epidemiology_dashboard(
        start_date='2026-05-01',
        end_date='2026-05-30',
        neighborhood='Centro',
        municipality='Maceió',
        specialty='P',
        professional_id='7',
        gender='Fem',
        age_group='40-59',
        treatment_status='Concluído',
        today=dt.date(2026, 5, 30),
    )

    assert dashboard['period']['start'] == dt.date(2026, 5, 1)
    assert dashboard['filters']['neighborhood'] == 'Centro'
    assert dashboard['filters']['municipality'] == 'Maceió'
    assert dashboard['filters']['gender'] == 'Fem'
    assert dashboard['summary']['no_show_rate'] == 30.0
    assert dashboard['summary']['cancer_suspicion_rate'] == 40.0
    assert dashboard['summary']['cancer_confirmed'] == 1
    assert dashboard['summary']['missing_teeth'] == 2
    assert dashboard['neighborhoods'][0]['no_show_rate'] == 25.0
    assert dashboard['neighborhoods'][0]['risk_label'] == 'Crítico'
    assert dashboard['critical_areas'][0]['bairro'] == 'Centro'
    assert dashboard['specialties'][0]['especialidade'] == 'Prótese Dentária'
    assert dashboard['lesion_locations'][0]['localizacao'] == 'Língua'
