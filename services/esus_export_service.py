import datetime as dt
import hashlib
import json

from database import execute, query


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


def build_esus_readiness(month_value=None):
    rows = list_completed_procedures_for_esus(month_value)
    ready = []
    missing_sigtap = []

    for row in rows:
        target = ready if row.get('sigtap_code') else missing_sigtap
        target.append(row)

    return {
        'reference_month': month_value or dt.date.today().strftime('%Y-%m'),
        'total': len(rows),
        'ready': len(ready),
        'missing_sigtap': len(missing_sigtap),
        'ready_records': ready,
        'missing_sigtap_records': missing_sigtap,
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
