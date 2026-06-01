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
        SELECT b.*, u.username, u.full_name,
               validator.username as validator_username,
               validator.full_name as validator_full_name
        FROM esus_export_batches b
        LEFT JOIN users u ON u.id = b.generated_by
        LEFT JOIN users validator ON validator.id = b.validated_by
        ORDER BY b.generated_at DESC
        LIMIT %s
        """,
        (limit,)
    )


def get_latest_esus_batch(month_value=None):
    where_sql = ''
    params = []
    if month_value:
        where_sql = 'WHERE b.reference_month = %s'
        params.append(month_value)

    return query(
        f"""
        SELECT b.*, u.username, u.full_name,
               validator.username as validator_username,
               validator.full_name as validator_full_name
        FROM esus_export_batches b
        LEFT JOIN users u ON u.id = b.generated_by
        LEFT JOIN users validator ON validator.id = b.validated_by
        {where_sql}
        ORDER BY b.generated_at DESC, b.id DESC
        LIMIT 1
        """,
        tuple(params),
        one=True,
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
            'patient_name': row.get('patient_name'),
            'patient_cns': row.get('cns'),
            'patient_cpf': row.get('cpf'),
            'professional_id': row.get('professor_id'),
            'professional_name': row.get('professional_name'),
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


def _as_payload(payload_json):
    if not payload_json:
        return None
    if isinstance(payload_json, str):
        return json.loads(payload_json)
    return payload_json


def get_esus_batch(batch_id):
    return query(
        """
        SELECT b.*, u.username, u.full_name,
               validator.username as validator_username,
               validator.full_name as validator_full_name
        FROM esus_export_batches b
        LEFT JOIN users u ON u.id = b.generated_by
        LEFT JOIN users validator ON validator.id = b.validated_by
        WHERE b.id = %s
        """,
        (batch_id,),
        one=True,
    )


def list_esus_transmission_attempts(batch_id, limit=20):
    return query(
        """
        SELECT a.*, u.username, u.full_name
        FROM esus_transmission_attempts a
        LEFT JOIN users u ON u.id = a.attempted_by
        WHERE a.batch_id = %s
        ORDER BY a.attempted_at DESC, a.id DESC
        LIMIT %s
        """,
        (batch_id, limit),
    )


def get_esus_batch_detail(batch_id):
    batch = get_esus_batch(batch_id)
    if not batch:
        return None

    payload = _as_payload(batch.get('payload_json'))
    legacy_payload = payload is None
    if payload is None:
        payload, _ = build_esus_payload(batch['reference_month'])

    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    computed_hash = hashlib.sha256(payload_json.encode('utf-8')).hexdigest()
    readiness = build_esus_readiness(batch['reference_month'])
    attempts = list_esus_transmission_attempts(batch_id)
    transmission_readiness = build_batch_transmission_readiness(batch, payload, computed_hash)

    return {
        'batch': batch,
        'payload': payload,
        'records': payload.get('records', []),
        'pending_records': readiness['missing_sigtap_records'] + readiness['incomplete_records'],
        'attempts': attempts,
        'transmission_readiness': transmission_readiness,
        'computed_hash': computed_hash,
        'hash_matches': not batch.get('payload_hash') or batch.get('payload_hash') == computed_hash,
        'legacy_payload': legacy_payload,
    }


def _snapshot_payload_if_missing(batch):
    payload = _as_payload(batch.get('payload_json'))
    if payload is not None:
        payload_hash = batch.get('payload_hash')
        if not payload_hash:
            payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
            payload_hash = hashlib.sha256(payload_json.encode('utf-8')).hexdigest()
        return payload, payload_hash

    payload, payload_hash = build_esus_payload(batch['reference_month'])
    summary = payload['summary']
    execute(
        """
        UPDATE esus_export_batches
        SET payload_json = %s::jsonb,
            payload_hash = %s,
            records_total = %s,
            records_ready = %s,
            records_missing_sigtap = %s,
            records_incomplete = %s
        WHERE id = %s
        """,
        (
            json.dumps(payload, ensure_ascii=False, default=str),
            payload_hash,
            summary['total'],
            summary['ready'],
            summary['missing_sigtap'],
            summary['incomplete'],
            batch['id'],
        )
    )
    return payload, payload_hash


def register_esus_export_batch(month_value=None, generated_by=None):
    payload, payload_hash = build_esus_payload(month_value)
    summary = payload['summary']
    batch_id = execute(
        """
        INSERT INTO esus_export_batches (
            reference_month, status, payload_hash, payload_json, records_total,
            records_ready, records_missing_sigtap, records_incomplete, generated_by
        )
        VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            payload['reference_month'],
            'draft',
            payload_hash,
            json.dumps(payload, ensure_ascii=False, default=str),
            summary['total'],
            summary['ready'],
            summary['missing_sigtap'],
            summary['incomplete'],
            generated_by,
        )
    )
    return batch_id, payload


def procedure_locked_by_validated_batch(procedure_id):
    batches = query(
        """
        SELECT id, payload_json
        FROM esus_export_batches
        WHERE status = 'validated_internally'
          AND payload_json IS NOT NULL
        """
    )
    for batch in batches:
        payload = _as_payload(batch.get('payload_json')) or {}
        for record in payload.get('records', []):
            if int(record.get('local_procedure_id') or 0) == int(procedure_id):
                return batch['id']
    return None


def validate_esus_export_batch(batch_id, validated_by, notes=None):
    batch = get_esus_batch(batch_id)
    if not batch:
        raise ValueError('Lote e-SUS não encontrado.')
    if batch['status'] != 'draft':
        raise ValueError('Apenas lotes em draft podem ser validados internamente.')

    payload, payload_hash = _snapshot_payload_if_missing(batch)
    summary = payload.get('summary', {})
    execute(
        """
        UPDATE esus_export_batches
        SET status = 'validated_internally',
            payload_hash = %s,
            records_total = %s,
            records_ready = %s,
            records_missing_sigtap = %s,
            records_incomplete = %s,
            validated_by = %s,
            validated_at = NOW(),
            validation_notes = %s
        WHERE id = %s
        """,
        (
            payload_hash,
            summary.get('total', 0),
            summary.get('ready', 0),
            summary.get('missing_sigtap', 0),
            summary.get('incomplete', 0),
            validated_by,
            notes or None,
            batch_id,
        )
    )
    return get_esus_batch(batch_id)


def build_batch_transmission_readiness(batch, payload, computed_hash=None, settings=None):
    settings = settings or get_esus_settings()
    blockers = []
    records = payload.get('records', []) if payload else []
    computed_hash = computed_hash or hashlib.sha256(
        json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, default=str).encode('utf-8')
    ).hexdigest()

    if batch.get('status') not in {'validated_internally', 'ready_to_send'}:
        blockers.append('lote ainda não validado internamente')
    if batch.get('payload_hash') and batch.get('payload_hash') != computed_hash:
        blockers.append('hash do payload divergente')
    if not records:
        blockers.append('payload sem registros prontos')
    if settings.get('environment') not in {'homologacao', 'producao'}:
        blockers.append('ambiente não definido para homologação/produção')
    if not settings.get('base_url'):
        blockers.append('URL PEC/e-SUS não informada')
    if settings.get('credential_status') not in {'received', 'validated'}:
        blockers.append('credenciais não recebidas/validadas')
    if not settings.get('cnes'):
        blockers.append('CNES não configurado')
    if not settings.get('ine'):
        blockers.append('INE/equipe não configurado')
    if not settings.get('active'):
        blockers.append('integração e-SUS inativa')

    return {
        'ready': not blockers,
        'blockers': blockers,
        'settings': settings,
        'endpoint_url': settings.get('base_url') or '',
        'records_count': len(records),
        'payload_hash': batch.get('payload_hash') or computed_hash,
    }


def register_esus_transmission_attempt(batch_id, mode, status, endpoint_url=None, http_status=None,
                                       request_hash=None, response_body=None, error_message=None,
                                       attempted_by=None, details=None):
    return execute(
        """
        INSERT INTO esus_transmission_attempts (
            batch_id, mode, status, endpoint_url, http_status, request_hash,
            response_body, error_message, attempted_by, details
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        RETURNING id
        """,
        (
            batch_id,
            mode,
            status,
            endpoint_url,
            http_status,
            request_hash,
            response_body,
            error_message,
            attempted_by,
            json.dumps(details, ensure_ascii=False, default=str) if details is not None else None,
        )
    )


def simulate_esus_transmission_preflight(batch_id, attempted_by=None):
    detail = get_esus_batch_detail(batch_id)
    if not detail:
        raise ValueError('Lote e-SUS não encontrado.')

    readiness = detail['transmission_readiness']
    response = {
        'simulated': True,
        'ready_to_send': readiness['ready'],
        'message': (
            'Pré-envio simulado aprovado. Lote pronto para transmissão real quando o conector for homologado.'
            if readiness['ready']
            else 'Pré-envio simulado bloqueado por pendências de configuração ou payload.'
        ),
        'blockers': readiness['blockers'],
        'records_count': readiness['records_count'],
        'payload_hash': readiness['payload_hash'],
        'endpoint_url': readiness['endpoint_url'],
    }
    status = 'success' if readiness['ready'] else 'blocked'
    http_status = 200 if readiness['ready'] else 428
    attempt_id = register_esus_transmission_attempt(
        batch_id=batch_id,
        mode='simulation',
        status=status,
        endpoint_url=readiness['endpoint_url'] or None,
        http_status=http_status,
        request_hash=readiness['payload_hash'],
        response_body=json.dumps(response, ensure_ascii=False, default=str),
        error_message='; '.join(readiness['blockers']) if readiness['blockers'] else None,
        attempted_by=attempted_by,
        details={
            'batch_status': detail['batch']['status'],
            'simulated': True,
            'blockers': readiness['blockers'],
        },
    )

    if readiness['ready']:
        execute(
            """
            UPDATE esus_export_batches
            SET status = 'ready_to_send',
                endpoint_url = %s,
                response_status = 'simulation_success',
                response_body = %s
            WHERE id = %s
            """,
            (readiness['endpoint_url'], json.dumps(response, ensure_ascii=False, default=str), batch_id)
        )
    else:
        execute(
            """
            UPDATE esus_export_batches
            SET response_status = 'simulation_blocked',
                response_body = %s
            WHERE id = %s
            """,
            (json.dumps(response, ensure_ascii=False, default=str), batch_id)
        )

    return {
        'attempt_id': attempt_id,
        'status': status,
        'ready_to_send': readiness['ready'],
        'response': response,
    }


def build_esus_meeting_checklist(settings, homologation, batch_detail=None):
    transmission = batch_detail.get('transmission_readiness') if batch_detail else None
    batch = batch_detail.get('batch') if batch_detail else None

    items = [
        {
            'group': 'Dados da prefeitura',
            'label': 'Ambiente de homologação definido',
            'ok': settings.get('environment') in {'homologacao', 'producao'},
            'detail': settings.get('environment') or 'pendente',
        },
        {
            'group': 'Dados da prefeitura',
            'label': 'Endpoint PEC/e-SUS informado',
            'ok': bool(settings.get('base_url')),
            'detail': settings.get('base_url') or 'pendente',
        },
        {
            'group': 'Dados da prefeitura',
            'label': 'Versão PEC confirmada',
            'ok': bool(settings.get('pec_version')),
            'detail': settings.get('pec_version') or 'pendente',
        },
        {
            'group': 'Dados da prefeitura',
            'label': 'Versão LEDI confirmada',
            'ok': bool(settings.get('ledi_version')),
            'detail': settings.get('ledi_version') or 'pendente',
        },
        {
            'group': 'Dados da prefeitura',
            'label': 'Credenciais recebidas/validadas',
            'ok': settings.get('credential_status') in {'received', 'validated'},
            'detail': settings.get('credential_status') or 'pending',
        },
        {
            'group': 'Identificação da unidade/equipe',
            'label': 'CNES configurado',
            'ok': bool(settings.get('cnes')),
            'detail': settings.get('cnes') or 'pendente',
        },
        {
            'group': 'Identificação da unidade/equipe',
            'label': 'INE/equipe configurado',
            'ok': bool(settings.get('ine')),
            'detail': settings.get('ine') or 'pendente',
        },
        {
            'group': 'Qualidade da produção',
            'label': 'Checklist de homologação sem bloqueios',
            'ok': homologation.get('ready', False),
            'detail': f"{homologation.get('blocking_count', 0)} bloqueio(s)",
        },
        {
            'group': 'Qualidade da produção',
            'label': 'Lote validado internamente',
            'ok': bool(batch and batch.get('status') in {'validated_internally', 'ready_to_send', 'sent'}),
            'detail': batch.get('status') if batch else 'sem lote',
        },
        {
            'group': 'Qualidade da produção',
            'label': 'Payload com hash SHA-256',
            'ok': bool(batch and batch.get('payload_hash')),
            'detail': (batch.get('payload_hash') or 'pendente') if batch else 'pendente',
        },
        {
            'group': 'Pré-envio',
            'label': 'Pré-envio simulado aprovado',
            'ok': bool(batch and batch.get('status') in {'ready_to_send', 'sent'}),
            'detail': batch.get('response_status') if batch else 'pendente',
        },
        {
            'group': 'Pré-envio',
            'label': 'Sem bloqueios para envio real',
            'ok': bool(transmission and transmission.get('ready')),
            'detail': f"{len(transmission.get('blockers', [])) if transmission else 0} bloqueio(s)",
        },
    ]

    grouped = {}
    for item in items:
        grouped.setdefault(item['group'], []).append(item)

    return {
        'items': items,
        'groups': grouped,
        'pending': [item for item in items if not item['ok']],
    }


def get_esus_quick_manual_steps():
    return [
        'Preencher dados obrigatórios de pacientes: CNS e CPF.',
        'Preencher dados obrigatórios dos profissionais: CNS, CBO, CNES, INE/equipe e CRO quando aplicável.',
        'Carregar ou conferir catálogo SIGTAP da competência.',
        'Vincular cada procedimento concluído ao código SIGTAP correto.',
        'Gerar lote draft da competência no painel SIGTAP/e-SUS.',
        'Abrir o detalhe do lote, conferir registros e baixar JSON para conferência técnica.',
        'Validar internamente o lote após conferência clínica/administrativa.',
        'Executar o pré-envio simulado e corrigir bloqueios apontados.',
        'Aguardar endpoint, autenticação e homologação oficial da prefeitura para ativar envio real.',
    ]


def get_esus_homologation_report(month_value=None, batch_id=None):
    month_value = month_value or current_month_value()
    dashboard = get_esus_dashboard(month_value)

    batch = get_esus_batch(batch_id) if batch_id else get_latest_esus_batch(month_value)
    batch_detail = get_esus_batch_detail(batch['id']) if batch else None
    checklist = build_esus_meeting_checklist(
        dashboard['settings'],
        dashboard['homologation'],
        batch_detail=batch_detail,
    )

    pending_items = []
    pending_items.extend(item['label'] for item in checklist['pending'])
    if batch_detail:
        pending_items.extend(batch_detail['transmission_readiness']['blockers'])
    else:
        pending_items.append('nenhum lote selecionado para homologação')

    return {
        'generated_at': dt.datetime.now(),
        'month': month_value,
        'settings': dashboard['settings'],
        'homologation': dashboard['homologation'],
        'readiness': dashboard['readiness'],
        'sigtap_summary': get_sigtap_summary(),
        'patient_gaps': dashboard['patient_gaps'],
        'missing_professionals': dashboard['missing_professionals'],
        'batch_detail': batch_detail,
        'checklist': checklist,
        'manual_steps': get_esus_quick_manual_steps(),
        'pending_items': pending_items,
        'status_label': 'Pronto para reunião técnica' if not pending_items else 'Com pendências para reunião técnica',
        'external_dependency_note': (
            'A transmissão real permanece aguardando endpoint, credenciais e regras oficiais de homologação da prefeitura.'
        ),
    }


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
    locked_batch_id = procedure_locked_by_validated_batch(procedure_id)
    if locked_batch_id:
        raise ValueError(f'Procedimento bloqueado por lote e-SUS validado internamente #{locked_batch_id}. Gere um novo lote para nova conferência.')

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
