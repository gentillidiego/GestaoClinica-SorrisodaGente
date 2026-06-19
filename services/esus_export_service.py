"""Exportação e-SUS APS por XML LEDI da Ficha de Atendimento Odontológico."""

import datetime as dt
import json
import os
import re
import tempfile
import uuid

from database import execute, get_db_connection, put_db_connection, query
from services.esus_xml_service import (
    assert_valid_xml,
    build_xml_ficha_odontologica,
    only_digits,
    parse_date,
    xml_sha256,
)
from services.sigtap_service import get_sigtap_procedure, get_sigtap_summary


class EsusDuplicateRemessaError(ValueError):
    def __init__(self, remessa):
        self.remessa = remessa
        super().__init__(
            f"Já existe a remessa #{remessa['id']} para este período e profissional."
        )


def month_period(month_value=None, today=None):
    if month_value:
        start = dt.datetime.strptime(month_value, '%Y-%m').date().replace(day=1)
    else:
        start = (today or dt.date.today()).replace(day=1)
    next_month = (
        start.replace(year=start.year + 1, month=1)
        if start.month == 12
        else start.replace(month=start.month + 1)
    )
    return start, next_month - dt.timedelta(days=1)


def current_month_value(today=None):
    return (today or dt.date.today()).strftime('%Y-%m')


def has_digits_length(value, length):
    return len(only_digits(value)) == length


def has_valid_patient_identifier(row):
    return has_digits_length(row.get('cns'), 15) or has_digits_length(row.get('cpf'), 11)


def has_valid_uf(value):
    text = str(value or '').strip()
    return len(text) == 2 and text.isalpha()


def build_quinzenal_periods(today=None):
    today = today or dt.date.today()
    p1_day = int(os.getenv('ESUS_REMESSA_DIA_P1', '15'))
    p2_day = int(os.getenv('ESUS_REMESSA_DIA_P2', '5'))
    current_month = today.replace(day=1)
    previous_month = (
        current_month.replace(year=current_month.year - 1, month=12)
        if current_month.month == 1
        else current_month.replace(month=current_month.month - 1)
    )
    previous_month_end = current_month - dt.timedelta(days=1)
    return [
        {
            'periodo_inicio': current_month,
            'periodo_fim': current_month.replace(day=14),
            'periodo_label': f"{current_month:%Y-%m} P1",
            'is_due_today': today == current_month.replace(day=p1_day),
        },
        {
            'periodo_inicio': previous_month.replace(day=15),
            'periodo_fim': previous_month_end,
            'periodo_label': f"{previous_month:%Y-%m} P2",
            'is_due_today': today == current_month.replace(day=p2_day),
        },
    ]


ENV_SETTING_MAP = {
    'cnes': 'ESUS_CNES',
    'ine': 'ESUS_INE',
    'cod_ibge': 'ESUS_COD_IBGE',
    'contra_chave': 'ESUS_CONTRA_CHAVE',
    'uuid_instalacao': 'ESUS_UUID_INSTALACAO',
    'cpf_cnpj': 'ESUS_CPF_CNPJ',
    'nome_razao_social': 'ESUS_NOME_RAZAO_SOCIAL',
    'fone': 'ESUS_FONE',
    'email_institucional': 'ESUS_EMAIL_INSTITUCIONAL',
    'versao_sistema': 'ESUS_VERSAO_SISTEMA',
    'nome_banco_dados': 'ESUS_NOME_BANCO_DADOS',
    'email_destino_remessa': 'ESUS_EMAIL_DESTINO',
}


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'sim', 'on'}


def _settings_defaults():
    settings = {key: os.getenv(env_name, '') for key, env_name in ENV_SETTING_MAP.items()}
    settings.update({
        'remessa_ativa': _env_bool('ESUS_REMESSA_ATIVA', False),
        'versao_major': int(os.getenv('ESUS_VERSAO_MAJOR', '7')),
        'versao_minor': int(os.getenv('ESUS_VERSAO_MINOR', '2')),
        'versao_revision': int(os.getenv('ESUS_VERSAO_REVISION', '1')),
        'nome_banco_dados': settings.get('nome_banco_dados') or 'PostgreSQL',
        'versao_sistema': settings.get('versao_sistema') or 'GestaoSaudeOral 2.8',
        'notes': '',
    })
    return settings


def get_esus_settings():
    defaults = _settings_defaults()
    stored = query(
        """
        SELECT *
        FROM esus_integration_settings
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """,
        one=True,
    )
    if not stored:
        return defaults
    merged = defaults
    for key, value in dict(stored).items():
        if value not in (None, ''):
            merged[key] = value
    return merged


def update_esus_settings(data):
    existing = query(
        "SELECT id FROM esus_integration_settings ORDER BY updated_at DESC, id DESC LIMIT 1",
        one=True,
    )
    fields = (
        data.get('cnes') or None,
        data.get('ine') or None,
        data.get('cod_ibge') or None,
        data.get('contra_chave') or None,
        data.get('uuid_instalacao') or None,
        data.get('cpf_cnpj') or None,
        data.get('nome_razao_social') or None,
        data.get('fone') or None,
        data.get('email_institucional') or None,
        data.get('versao_sistema') or None,
        data.get('nome_banco_dados') or 'PostgreSQL',
        int(data.get('versao_major') or 7),
        int(data.get('versao_minor') or 2),
        int(data.get('versao_revision') or 1),
        data.get('email_destino_remessa') or None,
        bool(data.get('remessa_ativa')),
        data.get('notes') or None,
    )
    columns = """
        cnes, ine, cod_ibge, contra_chave, uuid_instalacao,
        cpf_cnpj, nome_razao_social, fone, email_institucional,
        versao_sistema, nome_banco_dados, versao_major, versao_minor,
        versao_revision, email_destino_remessa, remessa_ativa, notes
    """
    if existing:
        execute(
            """
            UPDATE esus_integration_settings
            SET cnes = %s, ine = %s, cod_ibge = %s, contra_chave = %s,
                uuid_instalacao = %s, cpf_cnpj = %s, nome_razao_social = %s,
                fone = %s, email_institucional = %s, versao_sistema = %s,
                nome_banco_dados = %s, versao_major = %s, versao_minor = %s,
                versao_revision = %s, email_destino_remessa = %s,
                remessa_ativa = %s, notes = %s, updated_at = NOW()
            WHERE id = %s
            """,
            (*fields, existing['id']),
        )
        return existing['id']
    return execute(
        f"""
        INSERT INTO esus_integration_settings ({columns})
        VALUES ({', '.join(['%s'] * len(fields))})
        RETURNING id
        """,
        fields,
    )


def settings_validation_errors(settings=None):
    settings = settings or get_esus_settings()
    errors = []
    if not has_digits_length(settings.get('cnes'), 7):
        errors.append('CNES deve conter 7 dígitos')
    if not has_digits_length(settings.get('ine'), 10):
        errors.append('INE deve conter 10 dígitos')
    if not has_digits_length(settings.get('cod_ibge'), 7):
        errors.append('Código IBGE municipal deve conter 7 dígitos')
    if not str(settings.get('contra_chave') or '').strip():
        errors.append('Contra-chave da instalação não informada')
    cpf_cnpj = only_digits(settings.get('cpf_cnpj'))
    if len(cpf_cnpj) not in {11, 14}:
        errors.append('CPF/CNPJ da instalação deve conter 11 ou 14 dígitos')
    if not str(settings.get('nome_razao_social') or '').strip():
        errors.append('Nome/razão social da instalação não informado')
    return errors


def is_settings_complete(settings=None):
    return not settings_validation_errors(settings)


def list_atendimentos_para_remessa(data_inicio, data_fim):
    """Lista toda a produção concluída; a prontidão decide o que pode ser exportado."""
    return query(
        """
        SELECT
            tp.id,
            tp.patient_id,
            tp.dente,
            tp.descricao,
            tp.sigtap_code,
            tp.sigtap_competence,
            tp.sigtap_name,
            tp.criado_em,
            tp.professor_id,
            CASE
                WHEN COALESCE(tp.data_sessao, '') ~ '^\\d{4}-\\d{2}-\\d{2}'
                    THEN SUBSTRING(tp.data_sessao FROM 1 FOR 10)::date::timestamp
                ELSE tp.criado_em
            END AS service_datetime,
            1 AS quantidade,
            p.cns,
            p.cpf,
            p.nome AS patient_name,
            p.data_nascimento,
            p.genero,
            NULL::boolean AS necessidades_especiais,
            u.cns AS professional_cns,
            u.cbo AS professional_cbo,
            u.cnes AS professional_cnes,
            u.ine AS professional_ine,
            u.cro,
            u.cro_uf,
            u.full_name AS professional_name,
            an.gestante
        FROM tratamento_procedimentos tp
        JOIN patients p ON p.id = tp.patient_id
        LEFT JOIN users u ON u.id = tp.professor_id
        LEFT JOIN anamnesis an ON an.id = (
            SELECT MAX(a2.id) FROM anamnesis a2 WHERE a2.patient_id = p.id
        )
        WHERE tp.status = 'Concluído'
          AND (
              CASE
                  WHEN COALESCE(tp.data_sessao, '') ~ '^\\d{4}-\\d{2}-\\d{2}'
                      THEN SUBSTRING(tp.data_sessao FROM 1 FOR 10)::date
                  ELSE tp.criado_em::date
              END
          ) BETWEEN %s AND %s
        ORDER BY service_datetime ASC, tp.patient_id ASC, tp.id ASC
        """,
        (data_inicio, data_fim),
    )


def list_completed_procedures_for_esus(month_value=None):
    start, end = month_period(month_value)
    return list_atendimentos_para_remessa(start, end)


def _missing_professional_fields(row):
    missing = []
    if not row.get('cns'):
        missing.append('CNS profissional')
    elif not has_digits_length(row.get('cns'), 15):
        missing.append('CNS profissional inválido')
    if not row.get('cbo'):
        missing.append('CBO')
    elif not has_digits_length(row.get('cbo'), 6):
        missing.append('CBO inválido')
    if not row.get('cro'):
        missing.append('CRO')
    if row.get('cro') and not row.get('cro_uf'):
        missing.append('CRO-UF')
    elif row.get('cro_uf') and not has_valid_uf(row.get('cro_uf')):
        missing.append('CRO-UF inválido')
    return missing


def list_professionals_missing_required_data(limit=80):
    from constants import PROFESSIONAL_DATA_REQUIRED_ROLES

    roles = tuple(PROFESSIONAL_DATA_REQUIRED_ROLES)
    placeholders = ', '.join(['%s'] * len(roles))
    rows = query(
        f"""
        SELECT id, username, full_name, role, cns, cbo, cnes, ine, cro, cro_uf
        FROM users
        WHERE role IN ({placeholders}) AND active = TRUE
        ORDER BY role, full_name, username
        LIMIT %s
        """,
        (*roles, limit),
    )
    result = []
    for row in rows:
        missing = _missing_professional_fields(row)
        if missing:
            item = dict(row)
            item['missing_fields'] = missing
            result.append(item)
    return result


def get_patient_identifier_gaps():
    row = query(
        """
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (
                   WHERE COALESCE(NULLIF(TRIM(cns), ''), '') = ''
                     AND COALESCE(NULLIF(TRIM(cpf), ''), '') = ''
               ) AS missing_cns_or_cpf,
               COUNT(*) FILTER (
                   WHERE (COALESCE(NULLIF(TRIM(cns), ''), '') <> ''
                       OR COALESCE(NULLIF(TRIM(cpf), ''), '') <> '')
                     AND NOT (
                         length(regexp_replace(COALESCE(cns, ''), '\\D', '', 'g')) = 15
                         OR length(regexp_replace(COALESCE(cpf, ''), '\\D', '', 'g')) = 11
                     )
               ) AS invalid_cns_or_cpf
        FROM patients
        """,
        one=True,
    )
    return row or {'total': 0, 'missing_cns_or_cpf': 0, 'invalid_cns_or_cpf': 0}


def classify_esus_missing_fields(row, settings=None):
    missing = []
    if not row.get('sigtap_code'):
        missing.append('SIGTAP')
    if not row.get('sigtap_competence'):
        missing.append('competência SIGTAP')
    if not (row.get('cns') or row.get('cpf')):
        missing.append('CNS/CPF')
    elif not has_valid_patient_identifier(row):
        missing.append('CNS/CPF inválido')
    if not row.get('professor_id'):
        missing.append('profissional')
    if not row.get('professional_cns'):
        missing.append('CNS profissional')
    elif not has_digits_length(row.get('professional_cns'), 15):
        missing.append('CNS profissional inválido')
    if not row.get('professional_cbo'):
        missing.append('CBO')
    elif not has_digits_length(row.get('professional_cbo'), 6):
        missing.append('CBO inválido')
    if not row.get('cro'):
        missing.append('CRO')
    if row.get('cro') and not row.get('cro_uf'):
        missing.append('CRO-UF')
    elif row.get('cro_uf') and not has_valid_uf(row.get('cro_uf')):
        missing.append('CRO-UF inválido')
    if not row.get('service_datetime'):
        missing.append('data do atendimento')
    return missing


def build_esus_readiness(month_value=None, data_inicio=None, data_fim=None):
    if data_inicio and data_fim:
        rows = list_atendimentos_para_remessa(data_inicio, data_fim)
        reference = f'{data_inicio} a {data_fim}'
    else:
        rows = list_completed_procedures_for_esus(month_value)
        reference = month_value or current_month_value()
    ready, missing_sigtap, incomplete = [], [], []
    for raw_row in rows:
        row = dict(raw_row)
        row['missing_fields'] = classify_esus_missing_fields(row)
        if not row['missing_fields']:
            ready.append(row)
        elif 'SIGTAP' in row['missing_fields'] or 'competência SIGTAP' in row['missing_fields']:
            missing_sigtap.append(row)
        else:
            incomplete.append(row)
    return {
        'reference_month': reference,
        'total': len(rows),
        'ready': len(ready),
        'missing_sigtap': len(missing_sigtap),
        'incomplete': len(incomplete),
        'ready_records': ready,
        'missing_sigtap_records': missing_sigtap,
        'incomplete_records': incomplete,
    }


def list_professionals_for_readiness(readiness):
    professionals = {}
    for category, rows in (
        ('ready', readiness['ready_records']),
        ('pending', readiness['missing_sigtap_records'] + readiness['incomplete_records']),
    ):
        for row in rows:
            professional_id = row.get('professor_id')
            if not professional_id:
                continue
            item = professionals.setdefault(professional_id, {
                'id': professional_id,
                'name': row.get('professional_name') or f'Profissional #{professional_id}',
                'ready': 0,
                'pending': 0,
            })
            item[category] += 1
    return sorted(professionals.values(), key=lambda item: item['name'].lower())


def list_procedures_missing_sigtap(limit=80):
    return query(
        """
        SELECT tp.id, tp.patient_id, tp.dente, tp.descricao, tp.status, tp.criado_em,
               p.nome AS patient_name, p.cpf, p.cns
        FROM tratamento_procedimentos tp
        JOIN patients p ON p.id = tp.patient_id
        WHERE tp.sigtap_code IS NULL
        ORDER BY tp.criado_em DESC
        LIMIT %s
        """,
        (limit,),
    )


def update_treatment_sigtap(procedure_id, sigtap_code, sigtap_competence=None):
    locked = query(
        """
        SELECT r.id
        FROM esus_remessas r
        WHERE r.id = (
            SELECT esus_export_batch_id
            FROM tratamento_procedimentos
            WHERE id = %s AND esus_export_status IN ('generated', 'sent')
        )
        """,
        (procedure_id,),
        one=True,
    )
    if locked:
        raise ValueError(f"Procedimento já incluído na remessa e-SUS #{locked['id']}.")
    sigtap = get_sigtap_procedure(sigtap_code, sigtap_competence)
    if not sigtap:
        raise ValueError('Código SIGTAP não encontrado na competência carregada.')
    execute(
        """
        UPDATE tratamento_procedimentos
        SET sigtap_code = %s, sigtap_competence = %s, sigtap_name = %s,
            esus_export_status = CASE WHEN status = 'Concluído' THEN 'pending' ELSE esus_export_status END
        WHERE id = %s
        """,
        (sigtap['code'], sigtap['competence'], sigtap['name'], procedure_id),
    )
    return sigtap


def build_homologation_status(settings, readiness, sigtap_summary, patient_gaps, missing_professionals):
    settings_errors = settings_validation_errors(settings)
    items = [
        {
            'label': 'Envelope LEDI configurado',
            'ok': not settings_errors,
            'detail': 'completo' if not settings_errors else '; '.join(settings_errors),
        },
        {
            'label': 'E-mail de destino configurado',
            'ok': bool(settings.get('email_destino_remessa')),
            'detail': settings.get('email_destino_remessa') or 'pendente',
        },
        {
            'label': 'Catálogo SIGTAP carregado',
            'ok': bool(sigtap_summary['latest']['total']),
            'detail': f"{sigtap_summary['latest']['total']} procedimento(s)",
        },
        {
            'label': 'Pacientes com CNS/CPF válido',
            'ok': patient_gaps.get('missing_cns_or_cpf', 0) == 0
            and patient_gaps.get('invalid_cns_or_cpf', 0) == 0,
            'detail': (
                f"{patient_gaps.get('missing_cns_or_cpf', 0)} pendente(s), "
                f"{patient_gaps.get('invalid_cns_or_cpf', 0)} inválido(s)"
            ),
        },
        {
            'label': 'Profissionais com CNS/CBO/CRO',
            'ok': not missing_professionals,
            'detail': f'{len(missing_professionals)} pendente(s)',
        },
        {
            'label': 'Produção sem bloqueios',
            'ok': readiness['missing_sigtap'] == 0 and readiness['incomplete'] == 0,
            'detail': f"{readiness['missing_sigtap'] + readiness['incomplete']} bloqueio(s)",
        },
    ]
    return {
        'ready': all(item['ok'] for item in items),
        'items': items,
        'blocking_count': sum(not item['ok'] for item in items),
        'cnes_ine_missing': not has_digits_length(settings.get('cnes'), 7)
        or not has_digits_length(settings.get('ine'), 10),
        'settings_errors': settings_errors,
    }


def list_esus_remessas(limit=20):
    return query(
        """
        SELECT r.*, creator.username, creator.full_name,
               professional.full_name AS professional_name_current
        FROM esus_remessas r
        LEFT JOIN users creator ON creator.id = r.generated_by
        LEFT JOIN users professional ON professional.id = r.professional_id
        ORDER BY r.created_at DESC
        LIMIT %s
        """,
        (limit,),
    )


def get_esus_remessa(remessa_id):
    return query(
        """
        SELECT r.*, creator.username, creator.full_name,
               professional.full_name AS professional_name_current
        FROM esus_remessas r
        LEFT JOIN users creator ON creator.id = r.generated_by
        LEFT JOIN users professional ON professional.id = r.professional_id
        WHERE r.id = %s
        """,
        (remessa_id,),
        one=True,
    )


def find_existing_remessa(data_inicio, data_fim, professional_id):
    return query(
        """
        SELECT *
        FROM esus_remessas
        WHERE periodo_inicio = %s AND periodo_fim = %s AND professional_id = %s
        ORDER BY id DESC
        LIMIT 1
        """,
        (data_inicio, data_fim, professional_id),
        one=True,
    )


def _clean_period_label(value):
    return re.sub(r'[^A-Za-z0-9_.-]+', '_', str(value or '').strip()).strip('_') or 'periodo'


def _persist_remessa_and_link_procedures(remessa_params, procedure_ids):
    """Registra a remessa e vincula os procedimentos na mesma transação."""
    connection = get_db_connection()
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO esus_remessas (
                periodo_inicio, periodo_fim, periodo_label, professional_id, professional_name,
                xml_path, xml_hash, uuid_dado_serializado, uuid_ficha, num_lote,
                records_total, records_ready, records_skipped, status,
                xsd_valid, xsd_errors, generated_by
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, 0, 'gerado', TRUE, %s, %s
            )
            RETURNING id
            """,
            remessa_params,
        )
        remessa_id = cursor.fetchone()['id']
        cursor.execute(
            """
            UPDATE tratamento_procedimentos
            SET esus_export_status = 'generated',
                esus_exported_at = NOW(),
                esus_export_batch_id = %s
            WHERE id = ANY(%s)
            """,
            (remessa_id, procedure_ids),
        )
        if cursor.rowcount != len(procedure_ids):
            raise RuntimeError(
                'Nem todos os procedimentos foram vinculados à remessa '
                f'({cursor.rowcount}/{len(procedure_ids)}).'
            )
        connection.commit()
        return remessa_id
    except Exception:
        connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        put_db_connection(connection)


def gerar_remessa_xml(data_inicio, data_fim, periodo_label=None, generated_by=None, professional_id=None):
    data_inicio = parse_date(data_inicio)
    data_fim = parse_date(data_fim)
    if not data_inicio or not data_fim or data_inicio > data_fim:
        raise ValueError('Período de remessa inválido.')

    settings = get_esus_settings()
    setting_errors = settings_validation_errors(settings)
    if setting_errors:
        raise ValueError('Configuração do envelope incompleta: ' + '; '.join(setting_errors))

    if professional_id is not None:
        professional_id = int(professional_id)
        existing = find_existing_remessa(data_inicio, data_fim, professional_id)
        if existing:
            raise EsusDuplicateRemessaError(existing)

    readiness = build_esus_readiness(data_inicio=data_inicio, data_fim=data_fim)
    professionals = list_professionals_for_readiness(readiness)
    if professional_id is None:
        ready_ids = [item['id'] for item in professionals if item['ready']]
        if len(ready_ids) != 1:
            raise ValueError('Selecione o profissional da remessa.')
        professional_id = ready_ids[0]
    professional_id = int(professional_id)

    existing = find_existing_remessa(data_inicio, data_fim, professional_id)
    if existing:
        raise EsusDuplicateRemessaError(existing)

    ready_rows = [
        row for row in readiness['ready_records']
        if row.get('professor_id') == professional_id
    ]
    pending_rows = [
        row for row in readiness['missing_sigtap_records'] + readiness['incomplete_records']
        if row.get('professor_id') == professional_id
    ]
    if pending_rows:
        raise ValueError(
            f'Profissional possui {len(pending_rows)} procedimento(s) bloqueado(s) no período. '
            'Corrija os dados antes de gerar a remessa.'
        )
    if not ready_rows:
        raise ValueError('Nenhum procedimento pronto para o profissional no período informado.')

    professional_name = ready_rows[0].get('professional_name') or f'Profissional #{professional_id}'
    xml_bytes, metadata = build_xml_ficha_odontologica(
        ready_rows,
        settings,
        data_inicio=data_inicio,
        data_fim=data_fim,
        professional_id=professional_id,
    )
    assert_valid_xml(xml_bytes)
    hash_xml = xml_sha256(xml_bytes)

    output_dir = os.path.join(os.getcwd(), 'pdf_temp', 'esus')
    os.makedirs(output_dir, exist_ok=True)
    clean_label = _clean_period_label(periodo_label or f'{data_inicio}_{data_fim}')
    filename = (
        f'esus_odonto_{clean_label}_prof{professional_id}_'
        f'{metadata["uuid_ficha"][-8:]}_{uuid.uuid4().hex[:8]}.xml'
    )
    xml_path = os.path.join(output_dir, filename)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=output_dir, suffix='.xml.tmp', delete=False) as temp_file:
            temp_file.write(xml_bytes)
            temp_path = temp_file.name
        os.replace(temp_path, xml_path)
        temp_path = None

        procedure_ids = [row['id'] for row in ready_rows]
        remessa_id = _persist_remessa_and_link_procedures(
            (
                data_inicio, data_fim, periodo_label, professional_id, professional_name,
                xml_path, hash_xml, metadata['uuid_dado_serializado'], metadata['uuid_ficha'],
                metadata['num_lote'], len(ready_rows), len(ready_rows), json.dumps([]), generated_by,
            ),
            procedure_ids,
        )
    except Exception:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
        if os.path.exists(xml_path):
            os.remove(xml_path)
        duplicate = find_existing_remessa(data_inicio, data_fim, professional_id)
        if duplicate:
            raise EsusDuplicateRemessaError(duplicate)
        raise

    return {
        'remessa_id': remessa_id,
        'xml_path': xml_path,
        'filename': filename,
        'xml_bytes': xml_bytes,
        'xml_hash': hash_xml,
        **metadata,
        'professional_id': professional_id,
        'professional_name': professional_name,
        'records_ready': len(ready_rows),
        'records_skipped': 0,
        'xsd_valid': True,
        'xsd_errors': [],
    }


def marcar_remessa_enviada(remessa_id, email_destino):
    execute(
        """
        UPDATE esus_remessas
        SET status = 'enviado_email', email_destino = %s, enviado_em = NOW(),
            erro_mensagem = NULL
        WHERE id = %s
        """,
        (email_destino, remessa_id),
    )
    execute(
        """
        UPDATE tratamento_procedimentos
        SET esus_export_status = 'sent'
        WHERE esus_export_batch_id = %s
        """,
        (remessa_id,),
    )


def marcar_remessa_erro(remessa_id, mensagem_erro):
    execute(
        "UPDATE esus_remessas SET status = 'erro', erro_mensagem = %s WHERE id = %s",
        (mensagem_erro, remessa_id),
    )


def enviar_remessa_por_email(remessa_id, xml_path, periodo_label, email_destino, filename=None):
    from services.mail_service import send_email

    filename = filename or os.path.basename(xml_path)
    try:
        remessa = get_esus_remessa(remessa_id)
        if not remessa:
            raise ValueError('Remessa não encontrada.')
        with open(xml_path, 'rb') as xml_file:
            xml_content = xml_file.read()
        assert_valid_xml(xml_content)
        if xml_sha256(xml_content) != remessa.get('xml_hash'):
            raise ValueError('Hash do XML diverge do registro da remessa.')
        send_email(
            subject=f'Remessa e-SUS APS — Ficha Odontológica — {periodo_label}',
            to_email=email_destino,
            text_body=(
                f'Segue em anexo a remessa de atendimentos odontológicos de {periodo_label}.\n\n'
                f'Profissional: {remessa.get("professional_name") or remessa.get("professional_name_current")}\n'
                f'Arquivo: {filename}\n'
                f'SHA-256: {remessa.get("xml_hash")}\n'
            ),
            attachments=[(filename, xml_content, 'application/xml')],
        )
        marcar_remessa_enviada(remessa_id, email_destino)
        return True, None
    except Exception as exc:
        message = str(exc)
        marcar_remessa_erro(remessa_id, message)
        return False, message


def get_esus_dashboard(month_value=None):
    month_value = month_value or current_month_value()
    settings = get_esus_settings()
    readiness = build_esus_readiness(month_value)
    sigtap_summary = get_sigtap_summary()
    patient_gaps = get_patient_identifier_gaps()
    missing_professionals = list_professionals_missing_required_data(limit=80)
    return {
        'month': month_value,
        'readiness': readiness,
        'settings': settings,
        'patient_gaps': patient_gaps,
        'missing_professionals': missing_professionals,
        'homologation': build_homologation_status(
            settings, readiness, sigtap_summary, patient_gaps, missing_professionals
        ),
        'missing_sigtap': list_procedures_missing_sigtap(limit=80),
        'remessas': list_esus_remessas(limit=10),
        'periods': build_quinzenal_periods(),
        'settings_complete': is_settings_complete(settings),
        'sigtap_summary': sigtap_summary,
        'available_professionals': list_professionals_for_readiness(readiness),
    }


def list_esus_batches(limit=20):
    """Compatibilidade de leitura do histórico anterior ao pivô XML."""
    return query(
        """
        SELECT b.*, u.username, u.full_name
        FROM esus_export_batches b
        LEFT JOIN users u ON u.id = b.generated_by
        ORDER BY b.generated_at DESC
        LIMIT %s
        """,
        (limit,),
    )
