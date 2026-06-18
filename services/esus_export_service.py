"""
Serviço de exportação e-SUS APS
Modelo: geração de arquivo XML quinzenal (Ficha de Atendimento Odontológico)
Entrega: download manual + e-mail para o TI da Secretaria de Saúde

Regra de corte:
  - Dia 15 do mês: exporta dias 1 a 14 do mês corrente
  - Dia 5 do mês seguinte: exporta dias 15 ao último do mês anterior
"""
import datetime as dt
import hashlib
import json
import os

from database import execute, query
from services.esus_xml_service import build_xml_ficha_odontologica, validate_xml_against_xsd, xml_sha256
from services.sigtap_service import get_sigtap_procedure, get_sigtap_summary


# ─────────────────────────────────────────
# Utilitários de período e validação
# ─────────────────────────────────────────

def month_period(month_value=None, today=None):
    """Retorna (data_inicio, data_fim) para um mês no formato 'YYYY-MM'."""
    if month_value:
        start = dt.datetime.strptime(month_value, '%Y-%m').date().replace(day=1)
    else:
        today = today or dt.date.today()
        start = today.replace(day=1)

    if start.month == 12:
        next_month = start.replace(year=start.year + 1, month=1)
    else:
        next_month = start.replace(month=start.month + 1)
    return start, next_month - dt.timedelta(days=1)


def current_month_value(today=None):
    today = today or dt.date.today()
    return today.strftime('%Y-%m')


def only_digits(value):
    return ''.join(ch for ch in str(value or '') if ch.isdigit())


def has_digits_length(value, length):
    return len(only_digits(value)) == length


def has_valid_patient_identifier(row):
    return has_digits_length(row.get('cns'), 15) or has_digits_length(row.get('cpf'), 11)


def has_valid_uf(value):
    return len(str(value or '').strip()) == 2 and str(value or '').strip().isalpha()


def build_quinzenal_periods(today=None):
    """
    Determina os períodos quinzenais de remessa com base na data atual.

    Retorna lista de dicts com:
      - periodo_inicio, periodo_fim (date)
      - periodo_label (str, ex: '2026-06 P1')
      - is_due_today (bool): True se hoje é o dia de envio deste período
    """
    today = today or dt.date.today()
    p1_day = int(os.getenv('ESUS_REMESSA_DIA_P1', '15'))
    p2_day = int(os.getenv('ESUS_REMESSA_DIA_P2', '5'))

    periods = []

    # Período 1: dias 1-14 do mês corrente (due: dia p1_day do mesmo mês)
    mes_corrente = today.replace(day=1)
    p1_inicio = mes_corrente
    p1_fim = mes_corrente.replace(day=14)
    p1_due = mes_corrente.replace(day=p1_day)
    periods.append({
        'periodo_inicio': p1_inicio,
        'periodo_fim': p1_fim,
        'periodo_label': f"{mes_corrente.strftime('%Y-%m')} P1",
        'is_due_today': today == p1_due,
    })

    # Período 2: dias 15-fim do mês anterior (due: dia p2_day do mês corrente)
    if mes_corrente.month == 1:
        mes_anterior = mes_corrente.replace(year=mes_corrente.year - 1, month=12)
    else:
        mes_anterior = mes_corrente.replace(month=mes_corrente.month - 1)

    if mes_anterior.month == 12:
        ultimo_dia_ant = mes_anterior.replace(day=31)
    else:
        ultimo_dia_ant = mes_corrente - dt.timedelta(days=1)

    p2_inicio = mes_anterior.replace(day=15)
    p2_fim = ultimo_dia_ant
    p2_due = mes_corrente.replace(day=p2_day)
    periods.append({
        'periodo_inicio': p2_inicio,
        'periodo_fim': p2_fim,
        'periodo_label': f"{mes_anterior.strftime('%Y-%m')} P2",
        'is_due_today': today == p2_due,
    })

    return periods


# ─────────────────────────────────────────
# Configurações e-SUS (simplificadas)
# ─────────────────────────────────────────

def get_esus_settings():
    settings = query(
        """
        SELECT *
        FROM esus_integration_settings
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """,
        one=True,
    )
    if settings:
        return dict(settings)

    # Fallback para variáveis de ambiente (útil em primeiro acesso)
    return {
        'cnes': os.getenv('ESUS_CNES', ''),
        'ine': os.getenv('ESUS_INE', ''),
        'email_destino_remessa': os.getenv('ESUS_EMAIL_DESTINO', ''),
        'remessa_ativa': os.getenv('ESUS_REMESSA_ATIVA', 'false').lower() in {'1', 'true', 'yes', 'sim'},
        'notes': '',
    }


def update_esus_settings(data):
    existing = query(
        "SELECT id FROM esus_integration_settings ORDER BY updated_at DESC, id DESC LIMIT 1",
        one=True,
    )
    params = (
        data.get('cnes') or None,
        data.get('ine') or None,
        data.get('email_destino_remessa') or None,
        bool(data.get('remessa_ativa')),
        data.get('notes') or None,
    )

    if existing:
        execute(
            """
            UPDATE esus_integration_settings
            SET cnes = %s,
                ine = %s,
                email_destino_remessa = %s,
                remessa_ativa = %s,
                notes = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (*params, existing['id'])
        )
        return existing['id']

    return execute(
        """
        INSERT INTO esus_integration_settings (cnes, ine, email_destino_remessa, remessa_ativa, notes)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        params
    )


def is_settings_complete(settings=None):
    """Retorna True se CNES e INE estão configurados (pré-requisito para envio)."""
    s = settings or get_esus_settings()
    return (
        has_digits_length(s.get('cnes'), 7)
        and has_digits_length(s.get('ine'), 10)
    )


# ─────────────────────────────────────────
# Consultas de produção
# ─────────────────────────────────────────

def list_atendimentos_para_remessa(data_inicio, data_fim):
    """
    Lista atendimentos concluídos com SIGTAP e identificação de paciente válidos,
    dentro do período informado. Cada linha representa um procedimento (pode haver
    múltiplos por atendimento).
    """
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
            p.cns,
            p.cpf,
            p.nome           AS patient_name,
            p.data_nascimento,
            p.sexo,
            p.necessidade_especial,
            u.cns            AS professional_cns,
            u.cbo            AS professional_cbo,
            u.cnes           AS professional_cnes,
            u.ine            AS professional_ine,
            u.cro,
            u.cro_uf,
            u.full_name      AS professional_name,
            an.gestante
        FROM tratamento_procedimentos tp
        JOIN patients p ON p.id = tp.patient_id
        LEFT JOIN users u ON u.id = tp.professor_id
        LEFT JOIN anamnesis an ON an.patient_id = p.id
            AND an.id = (
                SELECT MAX(a2.id) FROM anamnesis a2 WHERE a2.patient_id = p.id
            )
        WHERE tp.status = 'Concluído'
          AND tp.sigtap_code IS NOT NULL
          AND tp.criado_em::date BETWEEN %s AND %s
        ORDER BY tp.criado_em ASC, tp.id ASC
        """,
        (data_inicio, data_fim),
    )


def list_completed_procedures_for_esus(month_value=None):
    """Compatibilidade: lista procedimentos do mês completo (usado pelo dashboard)."""
    start, end = month_period(month_value)
    return list_atendimentos_para_remessa(start, end)


# ─────────────────────────────────────────
# Qualidade / prontidão (preservado)
# ─────────────────────────────────────────

def _missing_professional_fields(row):
    from constants import role_requires_dental_license
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
        WHERE role IN ({placeholders})
          AND active = TRUE
        ORDER BY role, full_name, username
        LIMIT %s
        """,
        (*roles, limit),
    )

    missing_rows = []
    for row in rows:
        missing = _missing_professional_fields(row)
        if missing:
            row = dict(row)
            row['missing_fields'] = missing
            missing_rows.append(row)
    return missing_rows


def get_patient_identifier_gaps():
    row = query(
        """
        SELECT COUNT(*) as total,
               COUNT(*) FILTER (
                   WHERE COALESCE(NULLIF(TRIM(cns), ''), '') = ''
                      OR COALESCE(NULLIF(TRIM(cpf), ''), '') = ''
               ) as missing_cns_or_cpf,
               COUNT(*) FILTER (
                   WHERE (
                       COALESCE(NULLIF(TRIM(cns), ''), '') <> ''
                       OR COALESCE(NULLIF(TRIM(cpf), ''), '') <> ''
                   )
                   AND NOT (
                       length(regexp_replace(COALESCE(cns, ''), '\\D', '', 'g')) = 15
                       OR length(regexp_replace(COALESCE(cpf, ''), '\\D', '', 'g')) = 11
                   )
               ) as invalid_cns_or_cpf
        FROM patients
        """,
        one=True,
    )
    return row or {'total': 0, 'missing_cns_or_cpf': 0, 'invalid_cns_or_cpf': 0}


def classify_esus_missing_fields(row, settings=None):
    settings = settings or get_esus_settings()
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
    return missing


def build_esus_readiness(month_value=None, data_inicio=None, data_fim=None):
    if data_inicio and data_fim:
        rows = list_atendimentos_para_remessa(data_inicio, data_fim)
        ref = f"{data_inicio} a {data_fim}"
    else:
        rows = list_completed_procedures_for_esus(month_value)
        ref = month_value or dt.date.today().strftime('%Y-%m')

    ready = []
    missing_sigtap = []
    incomplete = []
    settings = get_esus_settings()

    for row in rows:
        missing = classify_esus_missing_fields(row, settings=settings)
        row = dict(row)
        row['missing_fields'] = missing
        if missing:
            if 'SIGTAP' in missing or 'competência SIGTAP' in missing:
                missing_sigtap.append(row)
            else:
                incomplete.append(row)
        else:
            ready.append(row)

    return {
        'reference_month': ref,
        'total': len(rows),
        'ready': len(ready),
        'missing_sigtap': len(missing_sigtap),
        'incomplete': len(incomplete),
        'ready_records': ready,
        'missing_sigtap_records': missing_sigtap,
        'incomplete_records': incomplete,
    }


def list_procedures_missing_sigtap(limit=80):
    return query(
        """
        SELECT tp.id, tp.patient_id, tp.dente, tp.descricao, tp.status, tp.criado_em,
               p.nome as patient_name, p.cpf, p.cns
        FROM tratamento_procedimentos tp
        JOIN patients p ON p.id = tp.patient_id
        WHERE tp.sigtap_code IS NULL
        ORDER BY tp.criado_em DESC
        LIMIT %s
        """,
        (limit,)
    )


def update_treatment_sigtap(procedure_id, sigtap_code, sigtap_competence=None):
    sigtap = get_sigtap_procedure(sigtap_code, sigtap_competence)
    if not sigtap:
        raise ValueError('Código SIGTAP não encontrado na competência carregada.')

    execute(
        """
        UPDATE tratamento_procedimentos
        SET sigtap_code = %s,
            sigtap_competence = %s,
            sigtap_name = %s,
            esus_export_status = CASE
                WHEN status = 'Concluído' THEN 'pending'
                ELSE esus_export_status
            END
        WHERE id = %s
        """,
        (sigtap['code'], sigtap['competence'], sigtap['name'], procedure_id)
    )
    return sigtap


def build_homologation_status(settings, readiness, sigtap_summary, patient_gaps, missing_professionals):
    patient_missing = patient_gaps.get('missing_cns_or_cpf', 0)
    patient_invalid = patient_gaps.get('invalid_cns_or_cpf', 0)
    cnes_ok = has_digits_length(settings.get('cnes'), 7)
    ine_ok = has_digits_length(settings.get('ine'), 10)
    items = [
        {
            'label': 'CNES configurado',
            'ok': cnes_ok,
            'detail': settings.get('cnes') or '⚠️ Aguardando TI da Secretaria',
        },
        {
            'label': 'INE/equipe configurado',
            'ok': ine_ok,
            'detail': settings.get('ine') or '⚠️ Aguardando TI da Secretaria',
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
            'ok': patient_missing == 0 and patient_invalid == 0,
            'detail': f"{patient_missing} pendente(s), {patient_invalid} inválido(s)",
        },
        {
            'label': 'Profissionais com CNS/CBO',
            'ok': len(missing_professionals) == 0,
            'detail': f"{len(missing_professionals)} pendente(s)",
        },
        {
            'label': 'Produção sem bloqueios de SIGTAP',
            'ok': readiness['missing_sigtap'] == 0 and readiness['incomplete'] == 0,
            'detail': f"{readiness['missing_sigtap'] + readiness['incomplete']} bloqueio(s)",
        },
    ]
    return {
        'ready': all(item['ok'] for item in items),
        'items': items,
        'blocking_count': sum(1 for item in items if not item['ok']),
        'cnes_ine_missing': not cnes_ok or not ine_ok,
    }


# ─────────────────────────────────────────
# Gestão de remessas XML
# ─────────────────────────────────────────

def list_esus_remessas(limit=20):
    return query(
        """
        SELECT r.*, u.username, u.full_name
        FROM esus_remessas r
        LEFT JOIN users u ON u.id = r.generated_by
        ORDER BY r.created_at DESC
        LIMIT %s
        """,
        (limit,),
    )


def get_esus_remessa(remessa_id):
    return query(
        """
        SELECT r.*, u.username, u.full_name
        FROM esus_remessas r
        LEFT JOIN users u ON u.id = r.generated_by
        WHERE r.id = %s
        """,
        (remessa_id,),
        one=True,
    )


def gerar_remessa_xml(data_inicio, data_fim, periodo_label=None, generated_by=None):
    """
    Gera o arquivo XML da Ficha de Atendimento Odontológico para o período,
    salva em pdf_temp/ e registra na tabela esus_remessas.

    Retorna: dict com id, xml_path, records_ready, records_skipped, xml_hash, erros_xsd
    """
    settings = get_esus_settings()
    cnes = settings.get('cnes') or ''
    ine = settings.get('ine') or ''

    # Busca atendimentos prontos
    readiness = build_esus_readiness(data_inicio=data_inicio, data_fim=data_fim)
    atendimentos_prontos = readiness['ready_records']
    skipped = readiness['missing_sigtap'] + readiness['incomplete']

    xml_bytes, uuid_ficha = build_xml_ficha_odontologica(atendimentos_prontos, cnes, ine)
    hash_xml = xml_sha256(xml_bytes)

    # Valida contra XSD
    valido, erros_xsd = validate_xml_against_xsd(xml_bytes)

    # Salva arquivo
    pdf_dir = os.path.join(os.getcwd(), 'pdf_temp', 'esus')
    os.makedirs(pdf_dir, exist_ok=True)
    label_clean = (periodo_label or f"{data_inicio}_{data_fim}").replace(' ', '_')
    filename = f"esus_odonto_{label_clean}_{uuid_ficha[:8]}.xml"
    xml_path = os.path.join(pdf_dir, filename)
    with open(xml_path, 'wb') as f:
        f.write(xml_bytes)

    # Registra remessa
    remessa_id = execute(
        """
        INSERT INTO esus_remessas (
            periodo_inicio, periodo_fim, periodo_label,
            xml_path, xml_hash, records_total, records_ready, records_skipped,
            status, generated_by
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'gerado', %s)
        RETURNING id
        """,
        (
            data_inicio, data_fim, periodo_label,
            xml_path, hash_xml,
            readiness['total'], len(atendimentos_prontos), skipped,
            generated_by,
        ),
    )

    return {
        'remessa_id': remessa_id,
        'xml_path': xml_path,
        'filename': filename,
        'xml_bytes': xml_bytes,
        'xml_hash': hash_xml,
        'uuid_ficha': uuid_ficha,
        'records_ready': len(atendimentos_prontos),
        'records_skipped': skipped,
        'xsd_valid': valido,
        'xsd_errors': erros_xsd,
    }


def marcar_remessa_enviada(remessa_id, email_destino):
    """Atualiza o status da remessa após envio por e-mail."""
    execute(
        """
        UPDATE esus_remessas
        SET status = 'enviado_email',
            email_destino = %s,
            enviado_em = NOW()
        WHERE id = %s
        """,
        (email_destino, remessa_id),
    )


def marcar_remessa_erro(remessa_id, mensagem_erro):
    execute(
        """
        UPDATE esus_remessas
        SET status = 'erro',
            erro_mensagem = %s
        WHERE id = %s
        """,
        (mensagem_erro, remessa_id),
    )


def enviar_remessa_por_email(remessa_id, xml_path, periodo_label, email_destino, filename=None):
    """
    Envia o arquivo XML da remessa por e-mail usando o Postfix já configurado.
    Retorna True se enviou ou False com mensagem de erro.
    """
    from services.mail_service import send_mail

    filename = filename or os.path.basename(xml_path)
    subject = f'Remessa e-SUS APS — Ficha Odontológica — {periodo_label}'
    body = (
        f'Prezado(a),\n\n'
        f'Segue em anexo a remessa eletrônica de atendimentos odontológicos '
        f'referente ao período: {periodo_label}.\n\n'
        f'Arquivo: {filename}\n\n'
        f'Importar no concentrador e-SUS APS conforme procedimento habitual.\n\n'
        f'Clínica Sorriso da Gente'
    )

    try:
        with open(xml_path, 'rb') as f:
            xml_content = f.read()
        send_mail(
            to=email_destino,
            subject=subject,
            body=body,
            attachments=[(filename, xml_content, 'application/xml')],
        )
        marcar_remessa_enviada(remessa_id, email_destino)
        return True, None
    except Exception as exc:
        msg = str(exc)
        marcar_remessa_erro(remessa_id, msg)
        return False, msg


# ─────────────────────────────────────────
# Dashboard principal
# ─────────────────────────────────────────

def get_esus_dashboard(month_value=None):
    month_value = month_value or current_month_value()
    settings = get_esus_settings()
    readiness = build_esus_readiness(month_value)
    sigtap_summary = get_sigtap_summary()
    patient_gaps = get_patient_identifier_gaps()
    missing_professionals = list_professionals_missing_required_data(limit=80)
    remessas = list_esus_remessas(limit=10)
    periods = build_quinzenal_periods()

    homologation = build_homologation_status(
        settings, readiness, sigtap_summary, patient_gaps, missing_professionals
    )

    return {
        'month': month_value,
        'readiness': readiness,
        'settings': settings,
        'patient_gaps': patient_gaps,
        'missing_professionals': missing_professionals,
        'homologation': homologation,
        'missing_sigtap': list_procedures_missing_sigtap(limit=80),
        'remessas': remessas,
        'periods': periods,
        'settings_complete': is_settings_complete(settings),
        'sigtap_summary': sigtap_summary,
    }


# ─────────────────────────────────────────
# Compatibilidade legada (não removidos para não quebrar imports)
# ─────────────────────────────────────────

def list_esus_batches(limit=20):
    """Legado: lista lotes antigos (não mais gerados)."""
    return query(
        """
        SELECT b.*, u.username, u.full_name
        FROM esus_export_batches b
        LEFT JOIN users u ON u.id = b.generated_by
        ORDER BY b.generated_at DESC
        LIMIT %s
        """,
        (limit,)
    )
