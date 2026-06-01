import datetime as dt
import hashlib
import json

from constants import PROFESSIONAL_DATA_REQUIRED_ROLES, role_requires_dental_license
from database import execute, query
from services.sigtap_service import get_sigtap_procedure, get_sigtap_summary


def month_period(month_value=None, today=None):
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


def list_completed_procedures_for_esus(month_value=None):
    start, end = month_period(month_value)
    return query(
        """
        SELECT tp.id,
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
               p.nome as patient_name,
               u.cns as professional_cns,
               u.cbo as professional_cbo,
               u.cnes as professional_cnes,
               u.ine as professional_ine,
               u.cro,
               u.cro_uf,
               u.full_name as professional_name
        FROM tratamento_procedimentos tp
        JOIN patients p ON p.id = tp.patient_id
        LEFT JOIN users u ON u.id = tp.professor_id
        WHERE tp.status = 'Concluído'
          AND tp.criado_em::date BETWEEN %s AND %s
        ORDER BY tp.criado_em ASC, tp.id ASC
        """,
        (start, end),
    )


def list_esus_batches(limit=20):
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


def get_patient_identifier_gaps():
    row = query(
        """
        SELECT COUNT(*) as total,
               COUNT(*) FILTER (
                   WHERE COALESCE(NULLIF(TRIM(cns), ''), '') = ''
                      OR COALESCE(NULLIF(TRIM(cpf), ''), '') = ''
               ) as missing_cns_or_cpf
        FROM patients
        """,
        one=True,
    )
    return row or {'total': 0, 'missing_cns_or_cpf': 0}


def _missing_professional_fields(row):
    missing = []
    if not row.get('cns'):
        missing.append('CNS profissional')
    if not row.get('cbo'):
        missing.append('CBO')
    if not row.get('cnes'):
        missing.append('CNES')
    if not row.get('ine'):
        missing.append('INE/equipe')
    if role_requires_dental_license(row.get('role')):
        if not row.get('cro'):
            missing.append('CRO')
        if not row.get('cro_uf'):
            missing.append('CRO-UF')
    return missing


def list_professionals_missing_required_data(limit=80):
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
        return settings

    return {
        'environment': 'aguardando_prefeitura',
        'base_url': '',
        'pec_version': '',
        'ledi_version': '',
        'cnes': '',
        'ine': '',
        'installation_id': '',
        'client_id': '',
        'credential_status': 'pending',
        'notes': '',
        'active': False,
    }


def update_esus_settings(data):
    existing = query(
        "SELECT id FROM esus_integration_settings ORDER BY updated_at DESC, id DESC LIMIT 1",
        one=True,
    )
    params = (
        data.get('environment') or 'aguardando_prefeitura',
        data.get('base_url') or None,
        data.get('pec_version') or None,
        data.get('ledi_version') or None,
        data.get('cnes') or None,
        data.get('ine') or None,
        data.get('installation_id') or None,
        data.get('client_id') or None,
        data.get('credential_status') or 'pending',
        data.get('notes') or None,
        bool(data.get('active')),
    )

    if existing:
        execute(
            """
            UPDATE esus_integration_settings
            SET environment = %s,
                base_url = %s,
                pec_version = %s,
                ledi_version = %s,
                cnes = %s,
                ine = %s,
                installation_id = %s,
                client_id = %s,
                credential_status = %s,
                notes = %s,
                active = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (*params, existing['id'])
        )
        return existing['id']

    return execute(
        """
        INSERT INTO esus_integration_settings (
            environment, base_url, pec_version, ledi_version, cnes, ine,
            installation_id, client_id, credential_status, notes, active
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        params
    )


def classify_esus_missing_fields(row, settings=None):
    settings = settings or get_esus_settings()
    missing = []
    if not row.get('sigtap_code'):
        missing.append('SIGTAP')
    if not row.get('sigtap_competence'):
        missing.append('competência SIGTAP')
    if not (row.get('cns') or row.get('cpf')):
        missing.append('CNS/CPF')
    if not row.get('professor_id'):
        missing.append('profissional')
    if not row.get('professional_cns'):
        missing.append('CNS profissional')
    if not row.get('professional_cbo'):
        missing.append('CBO')
    if not row.get('cro'):
        missing.append('CRO')
    if not (row.get('professional_cnes') or settings.get('cnes')):
        missing.append('CNES')
    if not (row.get('professional_ine') or settings.get('ine')):
        missing.append('INE/equipe')
    return missing


def build_esus_readiness(month_value=None):
    rows = list_completed_procedures_for_esus(month_value)
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
        'reference_month': month_value or dt.date.today().strftime('%Y-%m'),
        'total': len(rows),
        'ready': len(ready),
        'missing_sigtap': len(missing_sigtap),
        'incomplete': len(incomplete),
        'ready_records': ready,
        'missing_sigtap_records': missing_sigtap,
        'incomplete_records': incomplete,
    }


def build_esus_payload(month_value=None):
    readiness = build_esus_readiness(month_value)
    records = []

    for row in readiness['ready_records']:
        records.append({
            'local_procedure_id': row['id'],
            'patient_id': row['patient_id'],
            'patient_cns': row.get('cns'),
            'patient_cpf': row.get('cpf'),
            'professional_id': row.get('professor_id'),
            'professional_cns': row.get('professional_cns'),
            'professional_cbo': row.get('professional_cbo'),
            'professional_cro': row.get('cro'),
            'professional_cro_uf': row.get('cro_uf'),
            'professional_cnes': row.get('professional_cnes'),
            'professional_ine': row.get('professional_ine'),
            'procedure': {
                'sigtap_code': row['sigtap_code'],
                'sigtap_competence': row['sigtap_competence'],
                'sigtap_name': row['sigtap_name'],
                'description': row['descricao'],
                'tooth': row.get('dente'),
                'performed_at': row['criado_em'].isoformat() if row.get('criado_em') else None,
            },
        })

    payload = {
        'reference_month': readiness['reference_month'],
        'system': 'GestaoSaudeOral',
        'status': 'draft_waiting_city_esus_credentials',
        'records': records,
        'summary': {
            'total': readiness['total'],
            'ready': readiness['ready'],
            'missing_sigtap': readiness['missing_sigtap'],
            'incomplete': readiness['incomplete'],
        },
    }
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return payload, hashlib.sha256(payload_json.encode('utf-8')).hexdigest()


def register_esus_export_batch(month_value=None, generated_by=None):
    payload, payload_hash = build_esus_payload(month_value)
    summary = payload['summary']
    batch_id = execute(
        """
        INSERT INTO esus_export_batches (
            reference_month, status, payload_hash, records_total, records_ready,
            records_missing_sigtap, generated_by
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            payload['reference_month'],
            'draft',
            payload_hash,
            summary['total'],
            summary['ready'],
            summary['missing_sigtap'],
            generated_by,
        )
    )
    return batch_id, payload


def build_homologation_status(settings, readiness, sigtap_summary, patient_gaps, missing_professionals):
    items = [
        {
            'label': 'Ambiente definido',
            'ok': settings.get('environment') in {'homologacao', 'producao'},
            'detail': settings.get('environment') or 'aguardando prefeitura',
        },
        {
            'label': 'URL PEC/e-SUS informada',
            'ok': bool(settings.get('base_url')),
            'detail': settings.get('base_url') or 'pendente',
        },
        {
            'label': 'Versão PEC informada',
            'ok': bool(settings.get('pec_version')),
            'detail': settings.get('pec_version') or 'pendente',
        },
        {
            'label': 'Versão LEDI informada',
            'ok': bool(settings.get('ledi_version')),
            'detail': settings.get('ledi_version') or 'pendente',
        },
        {
            'label': 'Credenciais recebidas/validadas',
            'ok': settings.get('credential_status') in {'received', 'validated'},
            'detail': settings.get('credential_status') or 'pending',
        },
        {
            'label': 'CNES configurado',
            'ok': bool(settings.get('cnes')),
            'detail': settings.get('cnes') or 'pendente',
        },
        {
            'label': 'INE/equipe configurado',
            'ok': bool(settings.get('ine')),
            'detail': settings.get('ine') or 'pendente',
        },
        {
            'label': 'Catálogo SIGTAP carregado',
            'ok': bool(sigtap_summary['latest']['total']),
            'detail': f"{sigtap_summary['latest']['total']} procedimento(s)",
        },
        {
            'label': 'Pacientes com CNS e CPF',
            'ok': patient_gaps['missing_cns_or_cpf'] == 0,
            'detail': f"{patient_gaps['missing_cns_or_cpf']} pendente(s)",
        },
        {
            'label': 'Profissionais com CNS/CBO/CNES/INE',
            'ok': len(missing_professionals) == 0,
            'detail': f"{len(missing_professionals)} pendente(s)",
        },
        {
            'label': 'Produção da competência sem bloqueios',
            'ok': readiness['missing_sigtap'] == 0 and readiness['incomplete'] == 0,
            'detail': f"{readiness['missing_sigtap'] + readiness['incomplete']} bloqueio(s)",
        },
    ]
    return {
        'ready': all(item['ok'] for item in items),
        'items': items,
        'blocking_count': sum(1 for item in items if not item['ok']),
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
            settings,
            readiness,
            sigtap_summary,
            patient_gaps,
            missing_professionals,
        ),
        'missing_sigtap': list_procedures_missing_sigtap(limit=80),
        'batches': list_esus_batches(limit=12),
    }
