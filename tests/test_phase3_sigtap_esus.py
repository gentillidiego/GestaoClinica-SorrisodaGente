import datetime as dt
from pathlib import Path

import pytest
from lxml import etree

import services.esus_export_service as esus_export_service
import services.esus_xml_service as esus_xml_service
import services.mail_service as mail_service
import services.sigtap_service as sigtap_service
from constants import (
    Role,
    role_has_permission,
    role_requires_dental_license,
    role_requires_professional_data,
)
from services.esus_export_service import (
    EsusDuplicateRemessaError,
    build_esus_readiness,
    build_quinzenal_periods,
    classify_esus_missing_fields,
    gerar_remessa_xml,
    month_period,
    settings_validation_errors,
    update_treatment_sigtap,
)
from services.esus_xml_service import (
    EsusXmlValidationError,
    build_num_lote,
    build_xml_ficha_odontologica,
    derive_sexo,
    normalize_boolean,
    validate_xml_against_xsd,
)
from services.sigtap_service import (
    SIGTAP_PROCEDURE_INDEX,
    SIGTAP_SPECIALTY_GROUPS,
    build_sigtap_specialty_groups,
    format_sigtap_code,
    is_sigtap_code_allowed_for_specialty,
    normalize_sigtap_code,
    parse_tb_procedimento_line,
    split_sigtap_code,
    upsert_sigtap_procedure,
)


FIXTURE_DIR = Path(__file__).parent / 'fixtures' / 'esus'


@pytest.fixture
def complete_settings():
    return {
        'cnes': '0000001',
        'ine': '1010020002',
        'cod_ibge': '4205407',
        'contra_chave': 'TREINAMENTO',
        'uuid_instalacao': 'TREINAMENTO',
        'cpf_cnpj': '01234567890',
        'nome_razao_social': 'ADMINISTRADOR INSTALAÇÃO',
        'fone': '8216756527',
        'email_institucional': 'prof@esus.br',
        'versao_sistema': '5.4.8',
        'nome_banco_dados': 'PostgreSQL',
        'versao_major': 7,
        'versao_minor': 2,
        'versao_revision': 1,
        'email_destino_remessa': 'ti@example.gov.br',
        'remessa_ativa': True,
    }


@pytest.fixture
def ready_rows():
    base = {
        'patient_id': 123,
        'cpf': '05888644714',
        'cns': None,
        'patient_name': 'Paciente Teste',
        'data_nascimento': '1990-01-01',
        'genero': 'Fem',
        'gestante': 'Não',
        'necessidades_especiais': None,
        'quantidade': 1,
        'service_datetime': dt.datetime(2026, 6, 2, 9, 30),
        'validator_id': 7,
        'professional_cns': '972733454440007',
        'professional_cbo': '223293',
        'cro': '1234',
        'cro_uf': 'SC',
        'professional_name': 'Dra. Teste',
        'sigtap_competence': '202605',
    }
    return [
        {**base, 'id': 1, 'sigtap_code': '0101050046'},
        {**base, 'id': 2, 'sigtap_code': '0307030040'},
    ]


def canonical(xml_bytes):
    return etree.tostring(etree.fromstring(xml_bytes), method='c14n')


def test_sigtap_code_normalization_and_split():
    assert normalize_sigtap_code('03.070.300-40') == '0307030040'
    assert format_sigtap_code('0307030040') == '03.07.03.004-0'
    assert normalize_sigtap_code('123') == ''
    parts = split_sigtap_code('0307030040')
    assert parts['group_code'] == '03'
    assert parts['subgroup_code'] == '07'
    assert parts['form_code'] == '03'


def test_parse_tb_procedimento_fixed_width_line():
    name = 'PROFILAXIA / REMOÇÃO DA PLACA BACTERIANA'
    line = '0307030040' + name.ljust(250) + 'M'
    assert parse_tb_procedimento_line(line) == ('0307030040', name)


def test_sigtap_specialty_groups_filter_treatment_codes(monkeypatch):
    monkeypatch.setattr(sigtap_service, 'get_latest_sigtap_competence', lambda: '202606')
    monkeypatch.setattr(sigtap_service, 'get_sigtap_procedure', lambda code, competence=None: None)
    groups = build_sigtap_specialty_groups()
    endodontia = next(group for group in groups if group['value'] == 'endodontia')
    assert any(item['code'] == '0307020061' for item in endodontia['procedures'])
    assert any(
        item['label'] == '03.07.02.006-1 — Tratamento Endodôntico de Dente Permanente Unirradicular'
        for item in endodontia['procedures']
    )
    assert is_sigtap_code_allowed_for_specialty('endodontia', '0307020061')
    assert not is_sigtap_code_allowed_for_specialty('endodontia', '0414020138')


def test_sigtap_specialty_catalog_matches_the_approved_table():
    assert [group['label'] for group in SIGTAP_SPECIALTY_GROUPS] == [
        'Atenção Primária / Clínico Geral',
        'Endodontia',
        'Periodontia',
        'Cirurgia Bucomaxilofacial',
        'Prótese Dentária',
        'Alta Complexidade / Hospitalar / Implantodontia',
        'Diagnóstico / Estomatologia / Radiologia',
        'Urgências Odontológicas',
        'Apoio Diagnóstico / Exames Laboratoriais',
    ]
    assert len(SIGTAP_PROCEDURE_INDEX) == 138
    assert sum(len(group['procedures']) for group in SIGTAP_SPECIALTY_GROUPS) == 138
    assert SIGTAP_PROCEDURE_INDEX['0414020421']['name'] == 'Implante Dentário Osteointegrado'
    assert SIGTAP_PROCEDURE_INDEX['0301060061']['specialty'] == 'urgencias_odontologicas'
    assert SIGTAP_PROCEDURE_INDEX['0202010503']['specialty'] == 'apoio_diagnostico_laboratorial'


def test_upsert_sigtap_procedure_persists_group_fields(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        sigtap_service,
        'execute',
        lambda sql, params=(): captured.update(sql=sql, params=params),
    )
    code = upsert_sigtap_procedure('0307030040', 'Profilaxia', competence='202605')
    assert code == '0307030040'
    assert 'INSERT INTO sigtap_procedures' in captured['sql']
    assert captured['params'][3:6] == ('03', '07', '03')


def test_integrations_permissions_are_restricted():
    assert role_has_permission(Role.ADMIN, 'integrations:write')
    assert role_has_permission(Role.COORDENACAO, 'integrations:write')
    assert role_has_permission(Role.AUDITORIA, 'integrations:view')
    assert not role_has_permission(Role.AUDITORIA, 'integrations:write')
    assert role_requires_professional_data(Role.CLINICOS)
    assert role_requires_dental_license(Role.CLINICOS)


def test_month_and_quinzenal_periods():
    assert month_period('2026-05') == (dt.date(2026, 5, 1), dt.date(2026, 5, 31))
    p1, p2 = build_quinzenal_periods(dt.date(2026, 6, 15))
    assert p1['periodo_inicio'] == dt.date(2026, 6, 1)
    assert p1['periodo_fim'] == dt.date(2026, 6, 14)
    assert p1['is_due_today']
    assert p2['periodo_inicio'] == dt.date(2026, 5, 15)
    assert p2['periodo_fim'] == dt.date(2026, 5, 31)


def test_clinical_normalization_maps_real_database_values():
    assert derive_sexo('Masc') == 0
    assert derive_sexo('Fem') == 1
    assert derive_sexo('') is None
    assert normalize_boolean('Sim') is True
    assert normalize_boolean('Não') is False
    assert normalize_boolean('Não Sei') is None


def test_settings_validation_requires_complete_transport_envelope(complete_settings):
    assert settings_validation_errors(complete_settings) == []
    incomplete = {**complete_settings, 'cod_ibge': '', 'contra_chave': '', 'cpf_cnpj': '1'}
    errors = settings_validation_errors(incomplete)
    assert 'Código IBGE municipal deve conter 7 dígitos' in errors
    assert 'Contra-chave da instalação não informada' in errors
    assert 'CPF/CNPJ da instalação deve conter 11 ou 14 dígitos' in errors


def test_all_xsd_dependencies_are_present_and_parseable():
    required = {
        'dadotransporte.xsd',
        'dadoinstalacao.xsd',
        'versao.xsd',
        'resultadoexame.xsd',
        'fichaatendimentoodontologicomaster.xsd',
        'fichaatendimentoodontologicochild.xsd',
    }
    assert required.issubset({path.name for path in Path(esus_xml_service.XSD_DIR).glob('*.xsd')})
    etree.XMLSchema(etree.parse(str(Path(esus_xml_service.XSD_DIR) / 'dadotransporte.xsd')))


def test_generated_xml_matches_golden_and_official_structure(complete_settings, ready_rows):
    xml_bytes, metadata = build_xml_ficha_odontologica(
        ready_rows,
        complete_settings,
        data_inicio=dt.date(2026, 6, 1),
        data_fim=dt.date(2026, 6, 14),
        professional_id=7,
        uuid_dado_serializado='0000001-dado-golden',
        uuid_ficha='0000001-ficha-golden',
        num_lote=123,
    )
    golden = (FIXTURE_DIR / 'atendimento_odontologico_golden.xml').read_bytes()
    assert canonical(xml_bytes) == canonical(golden)
    assert metadata['attendance_count'] == 1
    assert xml_bytes.count(b'<procedimentosRealizados>') == 2
    assert b'<coMsProcedimento>' in xml_bytes
    assert b'<lotacaoFormPrincipal>' in xml_bytes


def test_generated_xml_validates_against_complete_official_xsd(complete_settings, ready_rows):
    xml_bytes, _ = build_xml_ficha_odontologica(
        ready_rows,
        complete_settings,
        data_inicio=dt.date(2026, 6, 1),
        data_fim=dt.date(2026, 6, 14),
        professional_id=7,
    )
    assert validate_xml_against_xsd(xml_bytes) == (True, [])


def test_invalid_xml_is_rejected_by_xsd(complete_settings, ready_rows):
    xml_bytes, _ = build_xml_ficha_odontologica(
        ready_rows,
        complete_settings,
        data_inicio=dt.date(2026, 6, 1),
        data_fim=dt.date(2026, 6, 14),
        professional_id=7,
    )
    invalid = xml_bytes.replace(
        b'<coMsProcedimento>0101050046</coMsProcedimento>',
        b'<codigoProcedimento>0101050046</codigoProcedimento>',
        1,
    )
    valid, errors = validate_xml_against_xsd(invalid)
    assert not valid
    assert errors
    assert any('ficha:' in error for error in errors)


def test_alphanumeric_clinical_procedure_code_is_preserved(complete_settings, ready_rows):
    rows = [{**ready_rows[0], 'sigtap_code': 'ABPO015'}]
    xml_bytes, _ = build_xml_ficha_odontologica(
        rows,
        complete_settings,
        data_inicio=dt.date(2026, 6, 1),
        data_fim=dt.date(2026, 6, 14),
        professional_id=7,
    )
    assert b'<coMsProcedimento>ABPO015</coMsProcedimento>' in xml_bytes
    assert validate_xml_against_xsd(xml_bytes) == (True, [])


def test_num_lote_is_stable_per_period_and_professional():
    first = build_num_lote(dt.date(2026, 6, 1), dt.date(2026, 6, 14), 7)
    second = build_num_lote(dt.date(2026, 6, 1), dt.date(2026, 6, 14), 7)
    other = build_num_lote(dt.date(2026, 6, 1), dt.date(2026, 6, 14), 8)
    assert first == second
    assert first != other


def test_query_uses_real_patient_columns_and_clinical_date(monkeypatch):
    captured = {}

    def fake_query(sql, params=(), one=False):
        captured['sql'] = sql
        captured['params'] = params
        return []

    monkeypatch.setattr(esus_export_service, 'query', fake_query)
    esus_export_service.list_atendimentos_para_remessa(
        dt.date(2026, 6, 1),
        dt.date(2026, 6, 14),
    )
    assert 'p.genero' in captured['sql']
    assert 'p.sexo' not in captured['sql']
    assert 'p.necessidade_especial' not in captured['sql']
    assert 'tp.data_sessao' in captured['sql']


def test_readiness_does_not_hide_missing_sigtap(monkeypatch, ready_rows):
    missing = {**ready_rows[0], 'id': 3, 'sigtap_code': None, 'sigtap_competence': None}
    monkeypatch.setattr(
        esus_export_service,
        'list_atendimentos_para_remessa',
        lambda start, end: [ready_rows[0], missing],
    )
    readiness = build_esus_readiness(
        data_inicio=dt.date(2026, 6, 1),
        data_fim=dt.date(2026, 6, 14),
    )
    assert readiness['total'] == 2
    assert readiness['ready'] == 1
    assert readiness['missing_sigtap'] == 1


def test_classify_esus_missing_fields_flags_invalid_clinical_record():
    missing = classify_esus_missing_fields({
        'sigtap_code': None,
        'sigtap_competence': None,
        'cns': '123',
        'cpf': '',
        'validator_id': None,
        'professional_cns': '700',
        'professional_cbo': '223',
        'cro': None,
        'service_datetime': None,
    })
    assert 'SIGTAP' in missing
    assert 'CNS/CPF inválido' in missing
    assert 'profissional' in missing
    assert 'data do atendimento' in missing


def test_generation_is_idempotent_per_period_and_professional(monkeypatch, complete_settings):
    existing = {
        'id': 91,
        'periodo_inicio': dt.date(2026, 6, 1),
        'periodo_fim': dt.date(2026, 6, 14),
        'professional_id': 7,
    }
    monkeypatch.setattr(esus_export_service, 'get_esus_settings', lambda: complete_settings)
    monkeypatch.setattr(esus_export_service, 'find_existing_remessa', lambda *args: existing)
    with pytest.raises(EsusDuplicateRemessaError) as exc:
        gerar_remessa_xml('2026-06-01', '2026-06-14', professional_id=7)
    assert exc.value.remessa['id'] == 91


def test_invalid_xml_is_never_saved_or_registered(
    monkeypatch,
    tmp_path,
    complete_settings,
    ready_rows,
):
    readiness = {
        'total': 2,
        'ready': 2,
        'missing_sigtap': 0,
        'incomplete': 0,
        'ready_records': ready_rows,
        'missing_sigtap_records': [],
        'incomplete_records': [],
    }
    calls = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(esus_export_service, 'get_esus_settings', lambda: complete_settings)
    monkeypatch.setattr(esus_export_service, 'build_esus_readiness', lambda **kwargs: readiness)
    monkeypatch.setattr(esus_export_service, 'find_existing_remessa', lambda *args: None)
    monkeypatch.setattr(
        esus_export_service,
        'assert_valid_xml',
        lambda xml: (_ for _ in ()).throw(EsusXmlValidationError(['falha XSD'])),
    )
    monkeypatch.setattr(
        esus_export_service,
        '_persist_remessa_and_link_procedures',
        lambda *args, **kwargs: calls.append(args),
    )
    with pytest.raises(EsusXmlValidationError):
        gerar_remessa_xml('2026-06-01', '2026-06-14', professional_id=7)
    assert calls == []
    assert not list(tmp_path.rglob('*.xml'))


def test_valid_generation_registers_hash_and_links_procedures(
    monkeypatch,
    tmp_path,
    complete_settings,
    ready_rows,
):
    readiness = {
        'total': 2,
        'ready': 2,
        'missing_sigtap': 0,
        'incomplete': 0,
        'ready_records': ready_rows,
        'missing_sigtap_records': [],
        'incomplete_records': [],
    }
    persisted = {}

    def fake_persist(params, procedure_ids):
        persisted['params'] = params
        persisted['procedure_ids'] = procedure_ids
        return 42

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(esus_export_service, 'get_esus_settings', lambda: complete_settings)
    monkeypatch.setattr(esus_export_service, 'build_esus_readiness', lambda **kwargs: readiness)
    monkeypatch.setattr(esus_export_service, 'find_existing_remessa', lambda *args: None)
    monkeypatch.setattr(
        esus_export_service,
        '_persist_remessa_and_link_procedures',
        fake_persist,
    )
    result = gerar_remessa_xml(
        '2026-06-01',
        '2026-06-14',
        periodo_label='2026-06 P1',
        generated_by=3,
        professional_id=7,
    )
    assert result['remessa_id'] == 42
    assert result['xsd_valid']
    assert Path(result['xml_path']).exists()
    assert validate_xml_against_xsd(Path(result['xml_path']).read_bytes()) == (True, [])
    assert persisted['procedure_ids'] == [1, 2]
    assert persisted['params'][6] == result['xml_hash']
    assert persisted['params'][7] == result['uuid_dado_serializado']
    assert persisted['params'][8] == result['uuid_ficha']


def test_remessa_and_procedure_links_are_atomic(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.rowcount = 0
            self.closed = False
            self.calls = []

        def execute(self, sql, params):
            self.calls.append((sql, params))
            if 'UPDATE tratamento_procedimentos' in sql:
                self.rowcount = 1

        def fetchone(self):
            return {'id': 42}

        def close(self):
            self.closed = True

    class FakeConnection:
        def __init__(self):
            self.cursor_instance = FakeCursor()
            self.committed = False
            self.rolled_back = False

        def cursor(self):
            return self.cursor_instance

        def commit(self):
            self.committed = True

        def rollback(self):
            self.rolled_back = True

    connection = FakeConnection()
    returned = []
    monkeypatch.setattr(esus_export_service, 'get_db_connection', lambda: connection)
    monkeypatch.setattr(
        esus_export_service,
        'put_db_connection',
        lambda conn: returned.append(conn),
    )

    with pytest.raises(RuntimeError, match='Nem todos os procedimentos'):
        esus_export_service._persist_remessa_and_link_procedures(
            tuple(range(15)),
            [1, 2],
        )

    assert connection.rolled_back
    assert not connection.committed
    assert connection.cursor_instance.closed
    assert returned == [connection]


def test_email_revalidates_xml_and_hash_before_sending(
    monkeypatch,
    tmp_path,
    complete_settings,
    ready_rows,
):
    xml_bytes, _ = build_xml_ficha_odontologica(
        ready_rows,
        complete_settings,
        data_inicio=dt.date(2026, 6, 1),
        data_fim=dt.date(2026, 6, 14),
        professional_id=7,
    )
    xml_path = tmp_path / 'remessa.xml'
    xml_path.write_bytes(xml_bytes)
    sent = []
    updates = []
    monkeypatch.setattr(
        esus_export_service,
        'get_esus_remessa',
        lambda remessa_id: {
            'id': remessa_id,
            'xml_hash': esus_xml_service.xml_sha256(xml_bytes),
            'professional_name': 'Dra. Teste',
        },
    )
    monkeypatch.setattr(mail_service, 'send_email', lambda **kwargs: sent.append(kwargs))
    monkeypatch.setattr(
        esus_export_service,
        'marcar_remessa_enviada',
        lambda remessa_id, email: updates.append((remessa_id, email)),
    )
    ok, error = esus_export_service.enviar_remessa_por_email(
        42,
        str(xml_path),
        '2026-06 P1',
        'ti@example.gov.br',
    )
    assert ok and error is None
    assert sent[0]['attachments'][0][2] == 'application/xml'
    assert updates == [(42, 'ti@example.gov.br')]


def test_update_treatment_sigtap_blocks_procedure_already_in_remessa(monkeypatch):
    monkeypatch.setattr(esus_export_service, 'query', lambda *args, **kwargs: {'id': 5})
    with pytest.raises(ValueError, match='remessa e-SUS #5'):
        update_treatment_sigtap(88, '0307030040', '202605')


def test_update_treatment_sigtap_uses_loaded_catalog(monkeypatch):
    captured = {}
    sigtap = {'code': '0307030040', 'competence': '202605', 'name': 'PROFILAXIA'}

    def fake_query(sql, params=(), one=False):
        return None

    monkeypatch.setattr(esus_export_service, 'query', fake_query)
    monkeypatch.setattr(esus_export_service, 'get_sigtap_procedure', lambda *args: sigtap)
    monkeypatch.setattr(
        esus_export_service,
        'execute',
        lambda sql, params=(): captured.update(sql=sql, params=params),
    )
    assert update_treatment_sigtap(88, '0307030040', '202605') == sigtap
    assert captured['params'] == ('0307030040', '202605', 'PROFILAXIA', 88)
