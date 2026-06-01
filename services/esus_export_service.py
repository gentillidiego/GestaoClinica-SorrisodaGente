import datetime as dt
import hashlib
import json

from database import execute, query
from services.sigtap_service import get_sigtap_procedure


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
    if not row.get('cro'):
        missing.append('CRO')
    if not settings.get('cnes'):
        missing.append('CNES')
    if not settings.get('ine'):
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
            'professional_cro': row.get('cro'),
            'professional_cro_uf': row.get('cro_uf'),
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
    readiness = build_esus_readiness(month_value)
    return {
        'month': month_value,
        'readiness': readiness,
        'settings': get_esus_settings(),
        'missing_sigtap': list_procedures_missing_sigtap(limit=80),
        'batches': list_esus_batches(limit=12),
    }
