import datetime as dt

from constants import Role, role_has_permission
import services.epidemiology_service as epidemiology_service
from services.epidemiology_service import (
    get_demographic_profile,
    get_epidemiology_dashboard,
    normalize_period,
    percentage,
)


def test_epidemiology_permission_is_available_to_management_roles():
    assert role_has_permission(Role.ADMIN, 'epidemiologia:view')
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


def test_epidemiology_dashboard_builds_summary_and_lists(monkeypatch):
    def fake_query(sql, params=(), one=False):
        if 'SELECT DISTINCT COALESCE' in sql:
            return [{'bairro': 'Centro'}, {'bairro': 'Tabuleiro'}]
        if 'FROM patients p' in sql and 'p.criado_em::date' in sql and one:
            return {'total': 4}
        if 'FROM estomatologia e' in sql and 'lesion_records' in sql and one:
            return {
                'lesion_records': 5,
                'lesion_patients': 3,
                'cancer_suspicions': 2,
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
                'no_shows': 3,
                'appointments': 12,
                'prosthetic_need': 2,
                'repressed_demand': 5,
            }]
        if 'GROUP BY esp.nome' in sql:
            return [{'especialidade': 'Prótese Dentária', 'linked_patients': 8, 'repressed_demand': 6}]
        if 'GROUP BY localizacao' in sql:
            return [{'localizacao': 'Língua', 'lesion_records': 3, 'cancer_suspicions': 1, 'biopsy_referrals': 1}]
        if 'SELECT data_nascimento, genero, profissao' in sql:
            return [{'data_nascimento': '1970-01-01', 'genero': 'Fem', 'profissao': 'Autônoma'}]
        return []

    monkeypatch.setattr(epidemiology_service, 'query', fake_query)

    dashboard = get_epidemiology_dashboard(
        start_date='2026-05-01',
        end_date='2026-05-30',
        neighborhood='Centro',
        today=dt.date(2026, 5, 30),
    )

    assert dashboard['period']['start'] == dt.date(2026, 5, 1)
    assert dashboard['filters']['neighborhood'] == 'Centro'
    assert dashboard['summary']['no_show_rate'] == 30.0
    assert dashboard['summary']['cancer_suspicion_rate'] == 40.0
    assert dashboard['neighborhoods'][0]['no_show_rate'] == 25.0
    assert dashboard['specialties'][0]['especialidade'] == 'Prótese Dentária'
    assert dashboard['lesion_locations'][0]['localizacao'] == 'Língua'
