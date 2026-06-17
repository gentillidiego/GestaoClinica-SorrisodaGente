import datetime as dt
from collections import defaultdict

from constants import CLINICAL_EXECUTOR_ROLES
from database import query
from services.execution_unit_service import get_execution_unit_choices, get_execution_unit_label, normalize_execution_unit
from services.inventory_service import get_inventory_alerts


CRITICAL_ALERTS = {
    'red_alert',
    'lesion_without_return',
    'two_no_shows',
    'critical_queue',
    'critical_specialty_bottleneck',
    'expired_lot',
    'implant_postop_pending',
}

ACUTE_PAIN_KEYWORDS = (
    'dor aguda',
    'dor intensa',
    'dor espont',
    'dor ao mastigar',
    'dor noturna',
    'piora durante a noite',
    'abscesso',
    'abcesso',
    'edema',
    'pulsatil',
    'pulsátil',
)

DIABETES_KEYWORDS = ('diabet',)

SOCIAL_VULNERABILITY_KEYWORDS = (
    'baixa renda',
    'cadunico',
    'cadúnico',
    'bolsa familia',
    'bolsa família',
    'sem renda',
    'desempreg',
    'vulnerab',
    'morador de rua',
    'situacao de rua',
    'situação de rua',
)


def _parse_birthdate(value):
    if not value:
        return None

    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return dt.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _parse_date(value):
    if not value:
        return None

    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value

    value = str(value).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%Y-%m-%d %H:%M:%S'):
        try:
            return dt.datetime.strptime(value[:19], fmt).date()
        except ValueError:
            continue
    return None


def _normalize_text(*values):
    return ' '.join(str(value or '').lower() for value in values if value is not None)


def _has_keyword(text, keywords):
    normalized = _normalize_text(text)
    return any(keyword in normalized for keyword in keywords)


def _is_affirmative(value):
    normalized = _normalize_text(value).strip()
    return normalized in {'sim', 's', 'true', '1', 'yes'} or normalized.startswith('sim ')


def _as_int(value, default=0):
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _percentage(part, total):
    total = float(total or 0)
    if total <= 0:
        return 100.0
    return round((float(part or 0) / total) * 100, 1)


def _clamp_progress(value):
    return max(0, min(100, round(float(value or 0), 1)))


def _clean_int(value):
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_command_center_filters(raw_filters=None):
    raw_filters = raw_filters or {}
    start_date = _parse_date(raw_filters.get('start_date') or raw_filters.get('inicio'))
    end_date = _parse_date(raw_filters.get('end_date') or raw_filters.get('fim'))

    if start_date and end_date and start_date > end_date:
        start_date, end_date = end_date, start_date

    filters = {
        'municipio_id': _clean_int(raw_filters.get('municipio_id')),
        'especialidade_id': _clean_int(raw_filters.get('especialidade_id')),
        'professional_id': _clean_int(raw_filters.get('professional_id') or raw_filters.get('dentista_id')),
        'execution_unit': normalize_execution_unit(raw_filters.get('execution_unit')),
        'start_date': start_date,
        'end_date': end_date,
        'start_date_value': start_date.isoformat() if start_date else '',
        'end_date_value': end_date.isoformat() if end_date else '',
    }
    filters['active'] = any(
        filters[key]
        for key in ('municipio_id', 'especialidade_id', 'professional_id', 'execution_unit', 'start_date', 'end_date')
    )
    return filters


def _where_clause(conditions):
    return f"WHERE {' AND '.join(conditions)}" if conditions else ""


def _append_date_range(conditions, params, field, filters):
    if filters.get('start_date'):
        conditions.append(f"DATE({field}) >= %s")
        params.append(filters['start_date'].isoformat())
    if filters.get('end_date'):
        conditions.append(f"DATE({field}) <= %s")
        params.append(filters['end_date'].isoformat())


def _append_patient_triage_exists(conditions, params, filters, patient_alias='p'):
    triage_conditions = []
    if filters.get('municipio_id'):
        triage_conditions.append("s_filter.municipio_id = %s")
        params.append(filters['municipio_id'])
    if filters.get('especialidade_id'):
        triage_conditions.append("s_filter.especialidade_id = %s")
        params.append(filters['especialidade_id'])

    if triage_conditions:
        conditions.append(
            f"""
            EXISTS (
                SELECT 1
                FROM triagem_senhas s_filter
                JOIN triagem_acoes ta_filter ON ta_filter.id = s_filter.triagem_acao_id
                WHERE s_filter.patient_id = {patient_alias}.id
                  AND {' AND '.join(triage_conditions)}
            )
            """
        )


def _append_patient_professional_exists(conditions, params, filters, patient_alias='p'):
    if not filters.get('professional_id'):
        return

    professional_conditions = [
        f"c_filter.patient_id = {patient_alias}.id",
        "c_filter.dentista_id = %s",
    ]
    params.append(filters['professional_id'])
    if filters.get('start_date'):
        professional_conditions.append("DATE(c_filter.data_consulta) >= %s")
        params.append(filters['start_date'].isoformat())
    if filters.get('end_date'):
        professional_conditions.append("DATE(c_filter.data_consulta) <= %s")
        params.append(filters['end_date'].isoformat())
    if filters.get('execution_unit'):
        professional_conditions.append("c_filter.execution_unit = %s")
        params.append(filters['execution_unit'])

    conditions.append(
        f"""
        EXISTS (
            SELECT 1
            FROM consultas c_filter
            WHERE {' AND '.join(professional_conditions)}
        )
        """
    )


def _append_patient_scope_filters(conditions, params, filters, patient_alias='p'):
    _append_patient_triage_exists(conditions, params, filters, patient_alias=patient_alias)
    _append_patient_professional_exists(conditions, params, filters, patient_alias=patient_alias)


def get_command_center_filter_options():
    roles = tuple(sorted(CLINICAL_EXECUTOR_ROLES))
    placeholders = ', '.join(['%s'] * len(roles))
    professionals = query(
        f"""
        SELECT id, username, COALESCE(NULLIF(full_name, ''), username) as name
        FROM users
        WHERE active = TRUE
          AND role IN ({placeholders})
        ORDER BY name ASC, username ASC
        """,
        roles,
    )

    return {
        'municipalities': query("SELECT id, nome FROM municipios WHERE ativo = 1 ORDER BY nome ASC") or [],
        'specialties': query("SELECT id, nome FROM especialidades WHERE ativo = 1 ORDER BY nome ASC") or [],
        'professionals': professionals or [],
        'execution_units': [
            {'id': value, 'nome': label}
            for value, label in get_execution_unit_choices()
        ],
    }


def _goal_status(current, target, progress, lower_is_better=False):
    if lower_is_better:
        if current <= target:
            return 'achieved', 'Meta atingida'
        if current <= max(target + 1, target * 1.25):
            return 'attention', 'Atenção'
        return 'critical', 'Crítica'

    if progress >= 100:
        return 'achieved', 'Meta atingida'
    if progress >= 75:
        return 'attention', 'Atenção'
    return 'critical', 'Crítica'


def _build_goal(
    goal_id,
    label,
    current,
    target,
    unit,
    detail,
    action,
    lower_is_better=False,
    value_suffix='',
):
    current = round(float(current or 0), 1)
    target = round(float(target or 0), 1)
    if lower_is_better:
        progress = 100 if current <= target else _clamp_progress((target / current) * 100 if current else 100)
    else:
        progress = _clamp_progress((current / target) * 100 if target else 100)

    status, status_label = _goal_status(current, target, progress, lower_is_better=lower_is_better)
    current_label = f"{current:g}{value_suffix}"
    target_label = f"{target:g}{value_suffix}"

    return {
        'id': goal_id,
        'label': label,
        'current': current,
        'target': target,
        'unit': unit,
        'current_label': current_label,
        'target_label': target_label,
        'value_label': f"{current_label} / {target_label}",
        'progress': progress,
        'status': status,
        'status_label': status_label,
        'detail': detail,
        'action': action,
        'lower_is_better': lower_is_better,
    }


def build_operational_goals(production_count, agenda, pending_treatments, queue_metrics):
    agenda = agenda or {}
    wait_time = (queue_metrics or {}).get('wait_time', {})
    production_count = _as_int(production_count)
    pending_treatments = _as_int(pending_treatments)

    useful_appointments = (
        _as_int(agenda.get('pending'))
        + _as_int(agenda.get('confirmed'))
        + _as_int(agenda.get('done'))
    )
    no_show = _as_int(agenda.get('no_show'))
    production_target = max(1, useful_appointments)

    attendance_base = useful_appointments + no_show
    attendance_rate = _percentage(useful_appointments, attendance_base)

    treatment_base = production_count + pending_treatments
    treatment_completion_rate = _percentage(production_count, treatment_base)

    active_queue = _as_int(wait_time.get('active_count'))
    over_30_days = _as_int(wait_time.get('over_30_days'))
    queue_target = max(0, int(active_queue * 0.25))

    goals = [
        _build_goal(
            'clinical_production',
            'Produção clínica',
            production_count,
            production_target,
            'procedimento(s)',
            'Alvo automático: ao menos 1 procedimento concluído para cada consulta útil no recorte.',
            'Registrar procedimentos concluídos no plano de tratamento e revisar atendimentos sem produção lançada.',
        ),
        _build_goal(
            'attendance',
            'Comparecimento',
            attendance_rate,
            85,
            '%',
            'Alvo automático: manter comparecimento operacional em 85% ou mais, desconsiderando cancelamentos.',
            'Confirmar agenda ativa, revisar faltas e acionar recepção para reconvocação quando necessário.',
            value_suffix='%',
        ),
        _build_goal(
            'treatment_completion',
            'Conclusão de tratamento',
            treatment_completion_rate,
            70,
            '%',
            'Alvo automático: manter 70% ou mais dos procedimentos do recorte como concluídos.',
            'Priorizar planos com procedimentos pendentes e registrar conclusão clínica assim que executada.',
            value_suffix='%',
        ),
        _build_goal(
            'queue_reduction',
            'Fila reduzida 30d+',
            over_30_days,
            queue_target,
            'paciente(s)',
            'Alvo automático: manter pacientes aguardando 30 dias ou mais abaixo de 25% da fila ativa.',
            'Reagendar pacientes antigos, justificar impossibilidades e priorizar especialidades com maior espera.',
            lower_is_better=True,
        ),
    ]

    return goals


def _add_reason(reasons, reason_details, label, points, detail):
    reasons.append(label)
    reason_details.append({
        'label': label,
        'points': points,
        'detail': detail,
    })


def calculate_age(birthdate, today=None):
    birthdate = _parse_birthdate(birthdate) if isinstance(birthdate, str) else birthdate
    if not birthdate:
        return None

    today = today or dt.date.today()
    return today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))


def calculate_priority_score(patient, today=None):
    today = today or dt.date.today()
    score = 0
    reasons = []
    reason_details = []

    if patient.get('suspeita_neoplasia'):
        score += 100
        _add_reason(
            reasons,
            reason_details,
            'Suspeita de neoplasia',
            100,
            'Prioridade máxima para regulação oncológica e biópsia/cirurgia.'
        )

    age = calculate_age(patient.get('data_nascimento'), today=today)
    if age is not None and age >= 60:
        score += 25
        _add_reason(
            reasons,
            reason_details,
            'Idoso',
            25,
            f'Paciente com {age} anos.'
        )

    no_show_count = _as_int(patient.get('no_show_count'))
    if no_show_count >= 2:
        score += 20
        _add_reason(
            reasons,
            reason_details,
            'Duas faltas ou mais',
            20,
            f'{no_show_count} faltas registradas na agenda.'
        )

    pending_treatments = _as_int(patient.get('pending_treatments'))
    if pending_treatments > 0:
        points = min(20, pending_treatments * 5)
        score += points
        _add_reason(
            reasons,
            reason_details,
            'Tratamento pendente',
            points,
            f'{pending_treatments} procedimento(s) ainda pendente(s).'
        )

    lesion_days_without_return = patient.get('lesion_days_without_return')
    if lesion_days_without_return is not None and lesion_days_without_return >= 14:
        score += 30
        _add_reason(
            reasons,
            reason_details,
            'Lesão suspeita sem retorno',
            30,
            f'{lesion_days_without_return} dias sem retorno após registro da lesão suspeita.'
        )

    clinical_text = _normalize_text(
        patient.get('queixa_principal'),
        patient.get('historia_doenca_atual'),
        patient.get('dor_dentes_gengiva'),
    )
    if _is_affirmative(patient.get('dor_dentes_gengiva')) or _has_keyword(clinical_text, ACUTE_PAIN_KEYWORDS):
        score += 25
        _add_reason(
            reasons,
            reason_details,
            'Dor aguda',
            25,
            'Dor odontológica ativa registrada na anamnese ou queixa principal.'
        )

    medical_text = _normalize_text(
        patient.get('sofre_doenca_explica'),
        patient.get('tratamento_medico_explica'),
        patient.get('tomando_medicamento_explica'),
        patient.get('problemas_saude_ja_teve'),
        patient.get('queixa_principal'),
        patient.get('historia_doenca_atual'),
    )
    if patient.get('diabetes_risk') or _has_keyword(medical_text, DIABETES_KEYWORDS):
        score += 15
        _add_reason(
            reasons,
            reason_details,
            'Diabetes',
            15,
            'Condição sistêmica com impacto em risco periodontal, cicatrização e controle clínico.'
        )

    vulnerability_text = _normalize_text(
        patient.get('profissao'),
        patient.get('endereco_residencial'),
        patient.get('atendido_em'),
        patient.get('queixa_principal'),
        patient.get('historia_doenca_atual'),
    )
    if patient.get('social_vulnerability') or _has_keyword(vulnerability_text, SOCIAL_VULNERABILITY_KEYWORDS):
        score += 15
        _add_reason(
            reasons,
            reason_details,
            'Vulnerabilidade socioeconômica',
            15,
            'Indicador explícito de vulnerabilidade registrado no cadastro ou anamnese.'
        )

    waiting_days = patient.get('waiting_days')
    if waiting_days is not None:
        waiting_days = _as_int(waiting_days)
        if waiting_days >= 90:
            points = 30
        elif waiting_days >= 60:
            points = 20
        elif waiting_days >= 30:
            points = 10
        else:
            points = 0

        if points:
            score += points
            specialty = patient.get('especialidade_nome') or 'especialidade'
            _add_reason(
                reasons,
                reason_details,
                'Espera prolongada',
                points,
                f'{waiting_days} dias aguardando encaminhamento/atendimento em {specialty}.'
            )

    return {
        'score': score,
        'risk_level': get_risk_level(score),
        'reasons': reasons,
        'reason_details': reason_details,
        'age': age,
    }


def get_risk_level(score):
    if score >= 100:
        return 'critical'
    if score >= 50:
        return 'high'
    if score >= 25:
        return 'medium'
    return 'routine'


def get_command_center_data(filters=None):
    filters = normalize_command_center_filters(filters)
    today = dt.date.today()
    today_str = today.isoformat()
    month_start = today.replace(day=1).isoformat()

    patients_conditions = []
    patients_params = []
    if filters.get('start_date') or filters.get('end_date'):
        _append_date_range(patients_conditions, patients_params, 'c.data_consulta', filters)
    else:
        patients_conditions.append("DATE(c.data_consulta) = %s")
        patients_params.append(today_str)
    if filters.get('professional_id'):
        patients_conditions.append("c.dentista_id = %s")
        patients_params.append(filters['professional_id'])
    if filters.get('execution_unit'):
        patients_conditions.append("c.execution_unit = %s")
        patients_params.append(filters['execution_unit'])
    _append_patient_triage_exists(patients_conditions, patients_params, filters, patient_alias='p')

    patients_today = query(
        f"""
        SELECT c.id, c.data_consulta, c.status, c.duracao_minutos,
               p.id as patient_id, p.nome as patient_nome,
               u.full_name as professional_name
        FROM consultas c
        JOIN patients p ON c.patient_id = p.id
        JOIN users u ON c.dentista_id = u.id
        {_where_clause(patients_conditions)}
        ORDER BY c.data_consulta ASC
        """,
        tuple(patients_params)
    )

    production_conditions = ["tp.status = 'Concluído'"]
    production_params = []
    if filters.get('start_date') or filters.get('end_date'):
        _append_date_range(production_conditions, production_params, "NULLIF(tp.data_sessao, '')::date", filters)
    else:
        production_conditions.append("tp.data_sessao = %s")
        production_params.append(today_str)
    if filters.get('professional_id'):
        production_conditions.append("tp.professor_id = %s")
        production_params.append(filters['professional_id'])
    _append_patient_triage_exists(production_conditions, production_params, filters, patient_alias='p')

    production = query(
        f"""
        SELECT COUNT(*) as today
        FROM tratamento_procedimentos tp
        JOIN patients p ON p.id = tp.patient_id
        {_where_clause(production_conditions)}
        """,
        tuple(production_params),
        one=True
    )

    agenda_conditions = []
    agenda_params = []
    if filters.get('start_date') or filters.get('end_date'):
        _append_date_range(agenda_conditions, agenda_params, 'c.data_consulta', filters)
    if filters.get('professional_id'):
        agenda_conditions.append("c.dentista_id = %s")
        agenda_params.append(filters['professional_id'])
    if filters.get('execution_unit'):
        agenda_conditions.append("c.execution_unit = %s")
        agenda_params.append(filters['execution_unit'])
    _append_patient_triage_exists(agenda_conditions, agenda_params, filters, patient_alias='p')

    agenda_stats_rows = query(
        f"""
        SELECT c.status, COUNT(*) as count
        FROM consultas c
        JOIN patients p ON p.id = c.patient_id
        {_where_clause(agenda_conditions)}
        GROUP BY c.status
        """,
        tuple(agenda_params),
    )
    agenda_by_status = {row['status']: row['count'] for row in agenda_stats_rows or []}

    red_alert_conditions = ["e.suspeita_neoplasia = TRUE"]
    red_alert_params = []
    _append_date_range(red_alert_conditions, red_alert_params, 'e.data_registro', filters)
    _append_patient_scope_filters(red_alert_conditions, red_alert_params, filters, patient_alias='p')
    red_alert_count = query(
        f"""
        SELECT COUNT(*) as count
        FROM estomatologia e
        JOIN patients p ON p.id = e.patient_id
        {_where_clause(red_alert_conditions)}
        """,
        tuple(red_alert_params),
        one=True
    )['count']

    pending_conditions = ["tp.status = 'Pendente'"]
    pending_params = []
    _append_date_range(pending_conditions, pending_params, 'tp.criado_em', filters)
    if filters.get('professional_id'):
        pending_conditions.append("tp.professor_id = %s")
        pending_params.append(filters['professional_id'])
    _append_patient_triage_exists(pending_conditions, pending_params, filters, patient_alias='p')
    pending_treatments = query(
        f"""
        SELECT COUNT(*) as count
        FROM tratamento_procedimentos tp
        JOIN patients p ON p.id = tp.patient_id
        {_where_clause(pending_conditions)}
        """,
        tuple(pending_params),
        one=True
    )['count']

    neighborhood_conditions = []
    neighborhood_params = []
    _append_date_range(neighborhood_conditions, neighborhood_params, 'p.criado_em', filters)
    _append_patient_scope_filters(neighborhood_conditions, neighborhood_params, filters, patient_alias='p')
    neighborhoods = query(
        f"""
        SELECT COALESCE(NULLIF(TRIM(endereco_bairro), ''), NULLIF(TRIM(atendido_em), ''), 'Não informado') as bairro,
               COUNT(*) as total
        FROM patients p
        {_where_clause(neighborhood_conditions)}
        GROUP BY bairro
        ORDER BY total DESC, bairro ASC
        LIMIT 8
        """,
        tuple(neighborhood_params),
    )

    specialty_conditions = ["s.patient_id IS NOT NULL"]
    specialty_params = []
    if filters.get('municipio_id'):
        specialty_conditions.append("s.municipio_id = %s")
        specialty_params.append(filters['municipio_id'])
    if filters.get('especialidade_id'):
        specialty_conditions.append("s.especialidade_id = %s")
        specialty_params.append(filters['especialidade_id'])
    _append_date_range(
        specialty_conditions,
        specialty_params,
        "COALESCE(s.vinculada_em, s.entregue_em, s.criado_em)",
        filters,
    )
    _append_patient_professional_exists(specialty_conditions, specialty_params, filters, patient_alias='p')
    specialty_queue = query(
        f"""
        SELECT e.nome as especialidade, COUNT(*) as total
        FROM triagem_senhas s
        JOIN patients p ON p.id = s.patient_id
        JOIN especialidades e ON s.especialidade_id = e.id
        JOIN triagem_acoes ta ON ta.id = s.triagem_acao_id
        {_where_clause(specialty_conditions)}
        GROUP BY e.nome
        ORDER BY total DESC, e.nome ASC
        LIMIT 8
        """,
        tuple(specialty_params),
    )

    full_priority_queue = get_priority_queue(limit=None, filters=filters)
    priority_queue = full_priority_queue[:12]
    specialty_bottlenecks = get_specialty_bottlenecks(full_priority_queue)
    demand_forecast = get_demand_forecast_snapshot(today=today, filters=filters)
    clinical_pending = get_clinical_pending_summary(filters=filters)
    queue_metrics = get_queue_operational_metrics(filters=filters, today=today)
    inventory_alerts = get_inventory_alerts(limit=20)
    production_count = _as_int(production.get('today'))
    agenda = {
        'pending': agenda_by_status.get('Pendente', 0),
        'confirmed': agenda_by_status.get('Confirmado', 0),
        'done': agenda_by_status.get('Realizado', 0),
        'canceled': agenda_by_status.get('Cancelado', 0),
        'no_show': agenda_by_status.get('Faltou', 0),
        'total': sum(agenda_by_status.values()),
    }
    operational_goals = build_operational_goals(
        production_count,
        agenda,
        pending_treatments,
        queue_metrics,
    )
    alerts = build_operational_alerts(
        red_alert_count,
        pending_treatments,
        agenda_by_status,
        full_priority_queue,
        inventory_alerts=inventory_alerts,
        specialty_bottlenecks=specialty_bottlenecks,
        clinical_pending=clinical_pending,
        queue_metrics=queue_metrics,
    )

    return {
        'today': today,
        'patients_today': patients_today,
        'production': {
            'today': production_count,
            'month': production_count,
        },
        'agenda': agenda,
        'red_alert_count': red_alert_count,
        'pending_treatments': pending_treatments,
        'neighborhoods': neighborhoods,
        'specialty_queue': specialty_queue,
        'priority_queue': priority_queue,
        'priority_queue_total': len(full_priority_queue),
        'specialty_bottlenecks': specialty_bottlenecks,
        'demand_forecast': demand_forecast,
        'clinical_pending': clinical_pending,
        'queue_metrics': queue_metrics,
        'operational_goals': operational_goals,
        'alerts': alerts,
        'inventory_alerts': inventory_alerts,
        'critical_alert_count': sum(1 for alert in alerts if alert['type'] in CRITICAL_ALERTS),
        'filters': filters,
        'filter_options': get_command_center_filter_options(),
    }


def _format_date_br(value):
    parsed = _parse_date(value)
    return parsed.strftime('%d/%m/%Y') if parsed else 'Não informado'


def _find_filter_option_label(options, option_id, fallback='Não informado'):
    option_id = _as_int(option_id)
    for option in options or []:
        if _as_int(option.get('id')) == option_id:
            return (
                option.get('nome')
                or option.get('name')
                or option.get('username')
                or fallback
            )
    return fallback


def _summary_period_label(filters, today):
    start_date = filters.get('start_date') or today
    end_date = filters.get('end_date') or today

    if start_date == end_date:
        return _format_date_br(start_date)
    return f"{_format_date_br(start_date)} a {_format_date_br(end_date)}"


def _applied_filter_labels(filters, filter_options, today):
    labels = [{
        'label': 'Período',
        'value': _summary_period_label(filters, today),
    }]

    if filters.get('municipio_id'):
        labels.append({
            'label': 'Município',
            'value': _find_filter_option_label(
                filter_options.get('municipalities'),
                filters['municipio_id'],
            ),
        })
    if filters.get('especialidade_id'):
        labels.append({
            'label': 'Especialidade',
            'value': _find_filter_option_label(
                filter_options.get('specialties'),
                filters['especialidade_id'],
            ),
        })
    if filters.get('professional_id'):
        labels.append({
            'label': 'Profissional',
            'value': _find_filter_option_label(
                filter_options.get('professionals'),
                filters['professional_id'],
            ),
        })
    if filters.get('execution_unit'):
        labels.append({
            'label': 'Unidade',
            'value': get_execution_unit_label(filters['execution_unit']),
        })

    if not filters.get('active'):
        labels.append({
            'label': 'Recorte',
            'value': 'Resumo do dia operacional atual',
        })

    return labels


def _build_daily_summary_recommendations(data):
    recommendations = []
    clinical_pending = data['clinical_pending']
    queue_metrics = data['queue_metrics']

    if data['critical_alert_count']:
        recommendations.append(
            'Priorizar a checagem dos alertas críticos antes da abertura ou encerramento da agenda.'
        )
    if data['red_alert_count']:
        recommendations.append(
            'Conferir pacientes em alerta vermelho e garantir encaminhamento/regulação sem atraso.'
        )
    if data['priority_queue_total'] >= 10:
        recommendations.append(
            'Revisar a fila inteligente com a coordenação, pois há 10 ou mais casos prioritários ativos.'
        )
    if queue_metrics['without_return']['total_over_30']:
        recommendations.append(
            'Reagendar ou justificar pacientes com mais de 30 dias sem retorno.'
        )
    if clinical_pending['pending_exams']['total'] or clinical_pending['unsigned_documents']['total']:
        recommendations.append(
            'Regularizar exames pendentes e documentos sem assinatura para reduzir risco de auditoria.'
        )
    if data['agenda']['no_show']:
        recommendations.append(
            'Acionar recepção para revisar faltas e confirmar próximos retornos dos pacientes ausentes.'
        )
    critical_goals = [
        goal for goal in data.get('operational_goals', [])
        if goal.get('status') == 'critical'
    ]
    if critical_goals:
        recommendations.append(
            'Revisar metas críticas: '
            + ', '.join(goal['label'] for goal in critical_goals[:3])
            + '.'
        )
    if not recommendations:
        recommendations.append(
            'Manter monitoramento de agenda, fila e pendências durante o expediente.'
        )

    return recommendations


def get_daily_operational_summary(filters=None, generated_by=None, generated_at=None):
    data = get_command_center_data(filters)
    today = data['today']
    generated_at = generated_at or dt.datetime.now()
    filters = data['filters']
    clinical_pending = data['clinical_pending']
    queue_metrics = data['queue_metrics']
    operational_goals = data.get('operational_goals', [])
    achieved_goals = sum(1 for goal in operational_goals if goal.get('status') == 'achieved')

    summary = {
        'generated_at': generated_at,
        'generated_by': generated_by or 'Sistema',
        'period_label': _summary_period_label(filters, today),
        'applied_filters': _applied_filter_labels(filters, data['filter_options'], today),
        'filters': filters,
        'source': data,
        'kpis': [
            {
                'label': 'Pacientes no recorte',
                'value': len(data['patients_today']),
                'detail': 'agenda exibida na Central de Comando',
            },
            {
                'label': 'Alertas críticos',
                'value': data['critical_alert_count'],
                'detail': f"{len(data['alerts'])} alerta(s) operacional(is) ativo(s)",
            },
            {
                'label': 'Produção realizada',
                'value': data['production']['today'],
                'detail': 'procedimentos concluídos no recorte',
            },
            {
                'label': 'Fila prioritária',
                'value': data['priority_queue_total'],
                'detail': f"{len(data['priority_queue'])} caso(s) exibidos no resumo",
            },
            {
                'label': 'Pendências clínicas',
                'value': clinical_pending['total'],
                'detail': (
                    f"{clinical_pending['pending_exams']['total']} exame(s), "
                    f"{clinical_pending['unsigned_documents']['total']} documento(s)"
                ),
            },
            {
                'label': 'Sem retorno 30d+',
                'value': queue_metrics['without_return']['total_over_30'],
                'detail': (
                    f"{queue_metrics['without_return']['over_60_days']} com 60d+, "
                    f"{queue_metrics['without_return']['over_90_days']} com 90d+"
                ),
            },
            {
                'label': 'Metas atingidas',
                'value': f"{achieved_goals}/{len(operational_goals)}",
                'detail': 'metas automáticas no recorte operacional',
            },
        ],
        'recommendations': _build_daily_summary_recommendations(data),
    }

    return summary


def build_daily_summary_csv_rows(summary):
    data = summary['source']
    rows = [
        ['Resumo', 'Período', summary['period_label'], ''],
        ['Resumo', 'Gerado por', summary['generated_by'], summary['generated_at'].strftime('%d/%m/%Y %H:%M')],
    ]

    for item in summary['applied_filters']:
        rows.append(['Filtro', item['label'], item['value'], ''])

    for item in summary['kpis']:
        rows.append(['Indicador', item['label'], item['value'], item['detail']])

    for goal in data.get('operational_goals', []):
        rows.append([
            'Meta operacional',
            goal['label'],
            goal['value_label'],
            f"{goal['status_label']} - {goal['detail']}",
        ])

    for alert in data['alerts']:
        rows.append(['Alerta', alert['title'], alert['severity'], alert['message']])

    for patient in data['priority_queue']:
        rows.append([
            'Fila prioritária',
            patient.get('nome'),
            patient.get('score'),
            ', '.join(patient.get('reasons') or []),
        ])

    for item in data['specialty_bottlenecks']:
        rows.append([
            'Gargalo por especialidade',
            item['especialidade'],
            item['total'],
            f"{item['max_waiting_days']} dia(s) de maior espera",
        ])

    for item in summary['recommendations']:
        rows.append(['Recomendação', item, '', ''])

    return rows


def get_priority_queue(limit=20, filters=None):
    filters = normalize_command_center_filters(filters)
    conditions = []
    params = []
    if filters.get('municipio_id'):
        conditions.append("s.municipio_id = %s")
        params.append(filters['municipio_id'])
    if filters.get('especialidade_id'):
        conditions.append("s.especialidade_id = %s")
        params.append(filters['especialidade_id'])
    _append_patient_professional_exists(conditions, params, filters, patient_alias='p')
    _append_date_range(
        conditions,
        params,
        "COALESCE(s.vinculada_em, s.entregue_em, s.criado_em, ta.data_acao::timestamp, p.criado_em)",
        filters,
    )

    rows = query(
        f"""
        WITH latest_estomatologia AS (
            SELECT DISTINCT ON (patient_id)
                   id, patient_id, suspeita_neoplasia, localizacao_lesao, data_registro
            FROM estomatologia
            ORDER BY patient_id, data_registro DESC, id DESC
        ),
        latest_anamnesis AS (
            SELECT DISTINCT ON (patient_id)
                   patient_id, queixa_principal, historia_doenca_atual,
                   sofre_doenca_explica, tratamento_medico_explica,
                   tomando_medicamento_explica, problemas_saude_ja_teve,
                   dor_dentes_gengiva, data_anamnese
            FROM anamnesis
            ORDER BY patient_id, data_anamnese DESC, id DESC
        )
        SELECT p.id, p.nome, p.data_nascimento, p.profissao,
               p.endereco_residencial, p.atendido_em,
               COALESCE(e.suspeita_neoplasia, FALSE) as suspeita_neoplasia,
               CASE
                   WHEN e.suspeita_neoplasia = TRUE
                        AND MAX(c.data_consulta) FILTER (
                            WHERE c.status IN ('Realizado', 'Confirmado')
                              AND c.data_consulta >= e.data_registro
                        ) IS NULL
                   THEN EXTRACT(DAY FROM NOW() - e.data_registro)::int
                   ELSE NULL
               END as lesion_days_without_return,
               COUNT(DISTINCT c.id) FILTER (WHERE c.status = 'Faltou') as no_show_count,
               COUNT(DISTINCT tp.id) FILTER (WHERE tp.status = 'Pendente') as pending_treatments,
               MAX(c.data_consulta) as last_schedule_at,
               e.localizacao_lesao,
               e.data_registro as estomatologia_data,
               a.queixa_principal,
               a.historia_doenca_atual,
               a.sofre_doenca_explica,
               a.tratamento_medico_explica,
               a.tomando_medicamento_explica,
               a.problemas_saude_ja_teve,
               a.dor_dentes_gengiva,
               CASE
                   WHEN LOWER(CONCAT_WS(' ', a.sofre_doenca_explica, a.tratamento_medico_explica,
                                            a.tomando_medicamento_explica, a.problemas_saude_ja_teve)) LIKE '%%diabet%%'
                   THEN TRUE ELSE FALSE
               END as diabetes_risk,
               CASE
                   WHEN LOWER(CONCAT_WS(' ', p.profissao, p.endereco_residencial, p.atendido_em,
                                            a.queixa_principal, a.historia_doenca_atual)) LIKE '%%baixa renda%%'
                     OR LOWER(CONCAT_WS(' ', p.profissao, p.endereco_residencial, p.atendido_em,
                                            a.queixa_principal, a.historia_doenca_atual)) LIKE '%%cadunico%%'
                     OR LOWER(CONCAT_WS(' ', p.profissao, p.endereco_residencial, p.atendido_em,
                                            a.queixa_principal, a.historia_doenca_atual)) LIKE '%%cadúnico%%'
                     OR LOWER(CONCAT_WS(' ', p.profissao, p.endereco_residencial, p.atendido_em,
                                            a.queixa_principal, a.historia_doenca_atual)) LIKE '%%bolsa familia%%'
                     OR LOWER(CONCAT_WS(' ', p.profissao, p.endereco_residencial, p.atendido_em,
                                            a.queixa_principal, a.historia_doenca_atual)) LIKE '%%bolsa família%%'
                     OR LOWER(CONCAT_WS(' ', p.profissao, p.endereco_residencial, p.atendido_em,
                                            a.queixa_principal, a.historia_doenca_atual)) LIKE '%%sem renda%%'
                     OR LOWER(CONCAT_WS(' ', p.profissao, p.endereco_residencial, p.atendido_em,
                                            a.queixa_principal, a.historia_doenca_atual)) LIKE '%%desempreg%%'
                     OR LOWER(CONCAT_WS(' ', p.profissao, p.endereco_residencial, p.atendido_em,
                                            a.queixa_principal, a.historia_doenca_atual)) LIKE '%%vulnerab%%'
                   THEN TRUE ELSE FALSE
               END as social_vulnerability,
               esp.nome as especialidade_nome,
               esp.codigo as especialidade_codigo,
               esp.id as especialidade_id,
               m.nome as municipio_nome,
               m.codigo as municipio_codigo,
               m.id as municipio_id,
               s.codigo as triagem_codigo,
               s.triagem_acao_id,
               ta.local as triagem_local,
               COALESCE(s.vinculada_em, s.entregue_em, s.criado_em, ta.data_acao::timestamp, p.criado_em) as queue_entry_at,
               MIN(c.data_consulta) FILTER (
                   WHERE c.status IN ('Realizado', 'Confirmado')
                     AND c.data_consulta >= COALESCE(s.vinculada_em, s.entregue_em, s.criado_em, ta.data_acao::timestamp, p.criado_em)
               ) as first_attended_or_confirmed_at,
               CASE
                   WHEN s.patient_id IS NOT NULL
                        AND MIN(c.data_consulta) FILTER (
                            WHERE c.status IN ('Realizado', 'Confirmado')
                              AND c.data_consulta >= COALESCE(s.vinculada_em, s.entregue_em, s.criado_em, ta.data_acao::timestamp, p.criado_em)
                        ) IS NULL
                   THEN GREATEST(EXTRACT(DAY FROM NOW() - COALESCE(s.vinculada_em, s.entregue_em, s.criado_em, ta.data_acao::timestamp, p.criado_em))::int, 0)
                   ELSE NULL
               END as waiting_days
        FROM patients p
        LEFT JOIN latest_estomatologia e ON e.patient_id = p.id
        LEFT JOIN latest_anamnesis a ON a.patient_id = p.id
        LEFT JOIN triagem_senhas s ON s.patient_id = p.id
        LEFT JOIN especialidades esp ON esp.id = s.especialidade_id
        LEFT JOIN municipios m ON m.id = s.municipio_id
        LEFT JOIN triagem_acoes ta ON ta.id = s.triagem_acao_id
        LEFT JOIN consultas c ON c.patient_id = p.id
        LEFT JOIN tratamento_procedimentos tp ON tp.patient_id = p.id
        {_where_clause(conditions)}
        GROUP BY p.id, p.nome, p.data_nascimento, p.profissao, p.endereco_residencial,
                 p.atendido_em, p.criado_em, e.suspeita_neoplasia, e.localizacao_lesao,
                 e.data_registro, a.queixa_principal, a.historia_doenca_atual,
                 a.sofre_doenca_explica, a.tratamento_medico_explica,
                 a.tomando_medicamento_explica, a.problemas_saude_ja_teve,
                 a.dor_dentes_gengiva, esp.nome, esp.codigo, esp.id, m.nome, m.codigo, m.id,
                 s.codigo, s.triagem_acao_id, s.patient_id, s.vinculada_em, s.entregue_em,
                 s.criado_em, ta.local, ta.data_acao
        """,
        tuple(params),
    )

    queue = []
    for row in rows or []:
        priority = calculate_priority_score(row)
        if priority['score'] <= 0:
            continue
        queue.append({**row, **priority})

    queue.sort(key=lambda item: (-item['score'], item['nome']))
    return queue[:limit] if limit else queue


def get_specialty_bottlenecks(priority_queue, limit=6):
    grouped = {}

    for patient in priority_queue or []:
        specialty = patient.get('especialidade_nome') or 'Sem especialidade'
        item = grouped.setdefault(specialty, {
            'especialidade': specialty,
            'total': 0,
            'critical': 0,
            'high': 0,
            'risk_score': 0,
            'waiting_days_total': 0,
            'waiting_count': 0,
            'max_waiting_days': 0,
            'oldest_patient': None,
            'municipalities': set(),
            'neighborhoods': set(),
        })

        item['total'] += 1
        item['risk_score'] += _as_int(patient.get('score'))

        if patient.get('risk_level') == 'critical':
            item['critical'] += 1
        elif patient.get('risk_level') == 'high':
            item['high'] += 1

        waiting_days = patient.get('waiting_days')
        if waiting_days is not None:
            waiting_days = _as_int(waiting_days)
            item['waiting_days_total'] += waiting_days
            item['waiting_count'] += 1
            if waiting_days > item['max_waiting_days']:
                item['max_waiting_days'] = waiting_days
                item['oldest_patient'] = patient.get('nome')

        if patient.get('municipio_nome'):
            item['municipalities'].add(patient['municipio_nome'])
        if patient.get('atendido_em'):
            item['neighborhoods'].add(_extract_neighborhood(patient['atendido_em']))

    bottlenecks = []
    for item in grouped.values():
        waiting_count = item.pop('waiting_count')
        waiting_total = item.pop('waiting_days_total')
        item['avg_waiting_days'] = round(waiting_total / waiting_count, 1) if waiting_count else 0
        item['municipality_count'] = len(item.pop('municipalities'))
        item['neighborhood_count'] = len(item.pop('neighborhoods'))
        bottlenecks.append(item)

    bottlenecks.sort(
        key=lambda row: (
            -row['critical'],
            -row['high'],
            -row['max_waiting_days'],
            -row['total'],
            row['especialidade'],
        )
    )
    return bottlenecks[:limit]


def _extract_neighborhood(value):
    value = str(value or '').strip()
    if not value:
        return 'Não informado'
    if ' - ' in value:
        return value.rsplit(' - ', 1)[0].strip() or value
    return value


def _empty_forecast(today, days):
    return {
        'window_days': days,
        'reference_date': today,
        'specialties': [],
        'municipalities': [],
        'neighborhoods': [],
        'triage_actions': [],
        'periods': [],
    }


def _forecast_bucket():
    return {
        'total': 0,
        'last_30': 0,
        'previous_30': 0,
    }


def _finalize_forecast_groups(groups, label_field, limit=8):
    rows = []
    for label, item in groups.items():
        last_30 = item['last_30']
        previous_30 = item['previous_30']
        trend = last_30 - previous_30
        rows.append({
            label_field: label,
            'total': item['total'],
            'last_30': last_30,
            'previous_30': previous_30,
            'trend': trend,
            'trend_label': 'alta' if trend > 0 else 'queda' if trend < 0 else 'estável',
            'projected_next_30': max(0, last_30 + max(trend, 0)),
        })

    rows.sort(key=lambda row: (-row['projected_next_30'], -row['last_30'], -row['total'], row[label_field]))
    return rows[:limit]


def get_demand_forecast_snapshot(today=None, days=90, limit=8, filters=None):
    filters = normalize_command_center_filters(filters)
    today = today or dt.date.today()
    window_start = filters.get('start_date') or (today - dt.timedelta(days=days))
    reference_end = filters.get('end_date') or today
    window_days = max((reference_end - window_start).days + 1, 1) if filters.get('start_date') else days
    last_30_start = today - dt.timedelta(days=30)
    previous_30_start = today - dt.timedelta(days=60)

    conditions = [
        "s.patient_id IS NOT NULL",
        "DATE(COALESCE(s.vinculada_em, s.entregue_em, s.criado_em, ta.data_acao::timestamp)) >= %s",
    ]
    params = [window_start.isoformat()]
    if filters.get('end_date'):
        conditions.append("DATE(COALESCE(s.vinculada_em, s.entregue_em, s.criado_em, ta.data_acao::timestamp)) <= %s")
        params.append(filters['end_date'].isoformat())
    if filters.get('municipio_id'):
        conditions.append("s.municipio_id = %s")
        params.append(filters['municipio_id'])
    if filters.get('especialidade_id'):
        conditions.append("s.especialidade_id = %s")
        params.append(filters['especialidade_id'])
    _append_patient_professional_exists(conditions, params, filters, patient_alias='p')

    rows = query(
        f"""
        SELECT esp.nome as especialidade,
               COALESCE(NULLIF(TRIM(p.endereco_bairro), ''), NULLIF(TRIM(p.atendido_em), ''), 'Não informado') as bairro,
               m.nome as municipio,
               ta.id as triagem_acao_id,
               ta.local as triagem_local,
               DATE(COALESCE(s.vinculada_em, s.entregue_em, s.criado_em, ta.data_acao::timestamp)) as entry_date
        FROM triagem_senhas s
        JOIN patients p ON p.id = s.patient_id
        JOIN especialidades esp ON esp.id = s.especialidade_id
        JOIN municipios m ON m.id = s.municipio_id
        JOIN triagem_acoes ta ON ta.id = s.triagem_acao_id
        {_where_clause(conditions)}
        """,
        tuple(params)
    )

    if not rows:
        return _empty_forecast(today, window_days)

    specialties = defaultdict(_forecast_bucket)
    municipalities = defaultdict(_forecast_bucket)
    neighborhoods = defaultdict(_forecast_bucket)
    triage_actions = defaultdict(_forecast_bucket)
    periods = defaultdict(_forecast_bucket)

    for row in rows:
        entry_date = _parse_date(row.get('entry_date'))
        if not entry_date:
            continue

        period = entry_date.strftime('%Y-%m')
        labels = {
            'specialty': row.get('especialidade') or 'Sem especialidade',
            'municipality': row.get('municipio') or 'Não informado',
            'neighborhood': _extract_neighborhood(row.get('bairro')),
            'triage_action': (
                f"Ação #{row.get('triagem_acao_id')} - {row.get('triagem_local') or 'Local não informado'}"
                if row.get('triagem_acao_id') else 'Sem ação'
            ),
            'period': period,
        }

        for group, label in (
            (specialties, labels['specialty']),
            (municipalities, labels['municipality']),
            (neighborhoods, labels['neighborhood']),
            (triage_actions, labels['triage_action']),
            (periods, labels['period']),
        ):
            bucket = group[label]
            bucket['total'] += 1
            if entry_date >= last_30_start:
                bucket['last_30'] += 1
            elif entry_date >= previous_30_start:
                bucket['previous_30'] += 1

    return {
        'window_days': window_days,
        'reference_date': today,
        'specialties': _finalize_forecast_groups(specialties, 'especialidade', limit),
        'municipalities': _finalize_forecast_groups(municipalities, 'municipio', limit),
        'neighborhoods': _finalize_forecast_groups(neighborhoods, 'bairro', limit),
        'triage_actions': _finalize_forecast_groups(triage_actions, 'acao', limit),
        'periods': _finalize_forecast_groups(periods, 'periodo', limit),
    }


def get_pending_exam_alert_summary(limit=8, patient_id=None, filters=None):
    filters = normalize_command_center_filters(filters)
    conditions = ["(e.professor_id IS NULL OR e.data_validacao IS NULL)"]
    params = []
    if patient_id is not None:
        conditions.append("e.patient_id = %s")
        params.append(patient_id)
    _append_date_range(conditions, params, 'e.data_criacao', filters)
    _append_patient_scope_filters(conditions, params, filters, patient_alias='p')
    where = _where_clause(conditions)

    totals = query(
        f"""
        SELECT COUNT(*) as total,
               COUNT(DISTINCT e.patient_id) as patient_count
        FROM exams e
        JOIN patients p ON p.id = e.patient_id
        {where}
        """,
        tuple(params),
        one=True
    ) or {}

    rows = query(
        f"""
        SELECT e.id, e.patient_id, p.nome as patient_name, e.tipo,
               e.data_criacao, e.resumo_clinico
        FROM exams e
        JOIN patients p ON p.id = e.patient_id
        {where}
        ORDER BY e.data_criacao ASC, e.id ASC
        LIMIT %s
        """,
        tuple([*params, limit])
    ) or []

    return {
        'total': _as_int(totals.get('total')),
        'patient_count': _as_int(totals.get('patient_count')),
        'items': rows,
    }


def _unsigned_documents_base_sql():
    return """
        SELECT a.patient_id,
               p.nome as patient_name,
               'atendimento' as document_type,
               'tab-atendimento' as module_tab,
               'Evolução clínica' as document_label,
               a.id as document_id,
               a.data as created_at,
               COALESCE(a.professor_id, a.aluno_executor_id, a.created_by) as professional_id,
               TRIM(BOTH ', ' FROM CONCAT_WS(', ',
                   CASE
                       WHEN a.assinatura_paciente_base64 IS NULL OR a.assinatura_paciente_base64 = ''
                       THEN 'paciente' END,
                   CASE WHEN a.aluno_executor_id IS NULL THEN 'executor' END,
                   CASE WHEN a.professor_id IS NULL THEN 'dentista responsável' END
               )) as missing_signatures
        FROM atendimentos a
        JOIN patients p ON p.id = a.patient_id
        WHERE a.assinatura_paciente_base64 IS NULL OR a.assinatura_paciente_base64 = ''
           OR a.aluno_executor_id IS NULL
           OR a.professor_id IS NULL

        UNION ALL

        SELECT pr.patient_id,
               p.nome as patient_name,
               'prosthesis_step' as document_type,
               'tab-protese' as module_tab,
               'Etapa de prótese' as document_label,
               pe.id as document_id,
               COALESCE(NULLIF(pe.data_etapa, '')::timestamp, pr.data) as created_at,
               COALESCE(pe.professor_id, pr.aluno_responsavel_id, pr.created_by) as professional_id,
               TRIM(BOTH ', ' FROM CONCAT_WS(', ',
                   CASE
                       WHEN pe.assinatura_paciente_base64 IS NULL OR pe.assinatura_paciente_base64 = ''
                       THEN 'paciente' END,
                   CASE WHEN pe.professor_id IS NULL THEN 'dentista responsável' END
               )) as missing_signatures
        FROM prosthesis_etapas pe
        JOIN prosthesis pr ON pr.id = pe.prosthesis_id
        JOIN patients p ON p.id = pr.patient_id
        WHERE pe.assinatura_paciente_base64 IS NULL OR pe.assinatura_paciente_base64 = ''
           OR pe.professor_id IS NULL

        UNION ALL

        SELECT e.patient_id,
               p.nome as patient_name,
               'endodontia_followup' as document_type,
               'tab-endodontia' as module_tab,
               'Evolução endodôntica' as document_label,
               ef.id as document_id,
               ef.criado_em as created_at,
               COALESCE(ef.professor_id, e.aluno_id) as professional_id,
               TRIM(BOTH ', ' FROM CONCAT_WS(', ',
                   CASE
                       WHEN ef.assinatura_paciente_base64 IS NULL OR ef.assinatura_paciente_base64 = ''
                       THEN 'paciente' END,
                   CASE WHEN ef.professor_id IS NULL THEN 'dentista responsável' END
               )) as missing_signatures
        FROM endodontia_followup ef
        JOIN endodontia e ON e.id = ef.endodontia_id
        JOIN patients p ON p.id = e.patient_id
        WHERE e.cancelado_em IS NULL
          AND COALESCE(e.status, 'Ativo') != 'Cancelado'
          AND (
              ef.assinatura_paciente_base64 IS NULL OR ef.assinatura_paciente_base64 = ''
              OR ef.professor_id IS NULL
          )
    """


def get_unsigned_document_alert_summary(limit=8, patient_id=None, filters=None):
    filters = normalize_command_center_filters(filters)
    base_sql = _unsigned_documents_base_sql()
    conditions = []
    params = []
    if patient_id is not None:
        conditions.append("pending.patient_id = %s")
        params.append(patient_id)
    if filters.get('professional_id'):
        conditions.append("pending.professional_id = %s")
        params.append(filters['professional_id'])
    _append_date_range(conditions, params, 'pending.created_at', filters)

    if filters.get('municipio_id') or filters.get('especialidade_id'):
        triage_conditions = []
        if filters.get('municipio_id'):
            triage_conditions.append("s_filter.municipio_id = %s")
            params.append(filters['municipio_id'])
        if filters.get('especialidade_id'):
            triage_conditions.append("s_filter.especialidade_id = %s")
            params.append(filters['especialidade_id'])
        conditions.append(
            f"""
            EXISTS (
                SELECT 1
                FROM triagem_senhas s_filter
                JOIN triagem_acoes ta_filter ON ta_filter.id = s_filter.triagem_acao_id
                WHERE s_filter.patient_id = pending.patient_id
                  AND {' AND '.join(triage_conditions)}
            )
            """
        )
    patient_filter = _where_clause(conditions)

    totals = query(
        f"""
        SELECT COUNT(*) as total,
               COUNT(DISTINCT pending.patient_id) as patient_count
        FROM ({base_sql}) pending
        {patient_filter}
        """,
        tuple(params),
        one=True
    ) or {}

    rows = query(
        f"""
        SELECT *
        FROM ({base_sql}) pending
        {patient_filter}
        ORDER BY created_at ASC NULLS LAST, document_id ASC
        LIMIT %s
        """,
        tuple([*params, limit])
    ) or []

    return {
        'total': _as_int(totals.get('total')),
        'patient_count': _as_int(totals.get('patient_count')),
        'items': rows,
    }


def get_overdue_endodontia_return_summary(limit=8, patient_id=None, filters=None):
    filters = normalize_command_center_filters(filters)
    conditions = [
        "e.cancelado_em IS NULL",
        "COALESCE(e.status, 'Ativo') != 'Cancelado'",
        "e.proxima_sessao_prevista IS NOT NULL",
        "e.proxima_sessao_prevista < CURRENT_DATE",
        "COALESCE(e.status_tratamento, 'aguardando_inicio') IN ('em_andamento', 'aguardando_retorno')",
    ]
    params = []
    if patient_id is not None:
        conditions.append("e.patient_id = %s")
        params.append(patient_id)
    if filters.get('professional_id'):
        conditions.append("e.aluno_id = %s")
        params.append(filters['professional_id'])
    _append_patient_scope_filters(conditions, params, filters, patient_alias='p')
    where = _where_clause(conditions)

    totals = query(
        f"""
        SELECT COUNT(*) as total,
               COUNT(DISTINCT e.patient_id) as patient_count
        FROM endodontia e
        JOIN patients p ON p.id = e.patient_id
        {where}
        """,
        tuple(params),
        one=True,
    ) or {}

    rows = query(
        f"""
        SELECT e.id, e.patient_id, p.nome as patient_name,
               e.elemento_dentario, e.status_tratamento,
               e.proxima_sessao_prevista, e.janela_retorno_dias,
               COALESCE(u.full_name, u.username) as professional_name
        FROM endodontia e
        JOIN patients p ON p.id = e.patient_id
        LEFT JOIN users u ON u.id = e.aluno_id
        {where}
        ORDER BY e.proxima_sessao_prevista ASC, e.id ASC
        LIMIT %s
        """,
        tuple([*params, limit]),
    ) or []

    return {
        'total': _as_int(totals.get('total')),
        'patient_count': _as_int(totals.get('patient_count')),
        'items': rows,
    }


def get_unrestored_endodontia_summary(limit=8, patient_id=None, filters=None):
    filters = normalize_command_center_filters(filters)
    conditions = [
        "e.cancelado_em IS NULL",
        "COALESCE(e.status, 'Ativo') != 'Cancelado'",
        "COALESCE(e.status_tratamento, 'aguardando_inicio') = 'obturado_aguardando_restauracao'",
        "COALESCE(e.restauracao_definitiva_registrada, FALSE) = FALSE",
    ]
    params = []
    if patient_id is not None:
        conditions.append("e.patient_id = %s")
        params.append(patient_id)
    if filters.get('professional_id'):
        conditions.append("e.aluno_id = %s")
        params.append(filters['professional_id'])
    _append_patient_scope_filters(conditions, params, filters, patient_alias='p')
    where = _where_clause(conditions)

    totals = query(
        f"""
        SELECT COUNT(*) as total,
               COUNT(DISTINCT e.patient_id) as patient_count
        FROM endodontia e
        JOIN patients p ON p.id = e.patient_id
        {where}
        """,
        tuple(params),
        one=True,
    ) or {}

    rows = query(
        f"""
        SELECT e.id, e.patient_id, p.nome as patient_name,
               e.elemento_dentario, e.status_tratamento,
               e.proxima_sessao_prevista, e.janela_retorno_dias,
               COALESCE(u.full_name, u.username) as professional_name
        FROM endodontia e
        JOIN patients p ON p.id = e.patient_id
        LEFT JOIN users u ON u.id = e.aluno_id
        {where}
        ORDER BY e.updated_at ASC NULLS LAST, e.id ASC
        LIMIT %s
        """,
        tuple([*params, limit]),
    ) or []

    return {
        'total': _as_int(totals.get('total')),
        'patient_count': _as_int(totals.get('patient_count')),
        'items': rows,
    }


def get_overdue_endodontia_proservation_summary(limit=8, patient_id=None, filters=None):
    filters = normalize_command_center_filters(filters)
    conditions = [
        "e.cancelado_em IS NULL",
        "COALESCE(e.status, 'Ativo') != 'Cancelado'",
        "pr.data_prevista < CURRENT_DATE",
        "COALESCE(pr.status, 'planejado') IN ('planejado', 'reagendado')",
    ]
    params = []
    if patient_id is not None:
        conditions.append("pr.patient_id = %s")
        params.append(patient_id)
    if filters.get('professional_id'):
        conditions.append("e.aluno_id = %s")
        params.append(filters['professional_id'])
    _append_patient_scope_filters(conditions, params, filters, patient_alias='p')
    where = _where_clause(conditions)

    totals = query(
        f"""
        SELECT COUNT(*) as total,
               COUNT(DISTINCT pr.patient_id) as patient_count
        FROM endodontia_proservacao pr
        JOIN endodontia e ON e.id = pr.endodontia_id
        JOIN patients p ON p.id = pr.patient_id
        {where}
        """,
        tuple(params),
        one=True,
    ) or {}

    rows = query(
        f"""
        SELECT pr.id, pr.patient_id, pr.endodontia_id, p.nome as patient_name,
               e.elemento_dentario, pr.tipo_retorno, pr.data_prevista,
               pr.status, COALESCE(u.full_name, u.username) as professional_name
        FROM endodontia_proservacao pr
        JOIN endodontia e ON e.id = pr.endodontia_id
        JOIN patients p ON p.id = pr.patient_id
        LEFT JOIN users u ON u.id = e.aluno_id
        {where}
        ORDER BY pr.data_prevista ASC, pr.id ASC
        LIMIT %s
        """,
        tuple([*params, limit]),
    ) or []

    return {
        'total': _as_int(totals.get('total')),
        'patient_count': _as_int(totals.get('patient_count')),
        'items': rows,
    }


def get_clinical_pending_summary(limit=8, filters=None):
    pending_exams = get_pending_exam_alert_summary(limit=limit, filters=filters)
    unsigned_documents = get_unsigned_document_alert_summary(limit=limit, filters=filters)
    overdue_endodontia_returns = get_overdue_endodontia_return_summary(limit=limit, filters=filters)
    unrestored_endodontia = get_unrestored_endodontia_summary(limit=limit, filters=filters)
    overdue_endodontia_proservations = get_overdue_endodontia_proservation_summary(limit=limit, filters=filters)

    return {
        'pending_exams': pending_exams,
        'unsigned_documents': unsigned_documents,
        'overdue_endodontia_returns': overdue_endodontia_returns,
        'unrestored_endodontia': unrestored_endodontia,
        'overdue_endodontia_proservations': overdue_endodontia_proservations,
        'total': (
            pending_exams['total']
            + unsigned_documents['total']
            + overdue_endodontia_returns['total']
            + unrestored_endodontia['total']
            + overdue_endodontia_proservations['total']
        ),
    }


def get_patient_clinical_alert_summary(patient_id, limit=5):
    pending_exams = get_pending_exam_alert_summary(limit=limit, patient_id=patient_id)
    unsigned_documents = get_unsigned_document_alert_summary(limit=max(limit, 20), patient_id=patient_id)
    overdue_endodontia_returns = get_overdue_endodontia_return_summary(limit=limit, patient_id=patient_id)
    unrestored_endodontia = get_unrestored_endodontia_summary(limit=limit, patient_id=patient_id)
    overdue_endodontia_proservations = get_overdue_endodontia_proservation_summary(limit=limit, patient_id=patient_id)
    total = (
        pending_exams['total']
        + unsigned_documents['total']
        + overdue_endodontia_returns['total']
        + unrestored_endodontia['total']
        + overdue_endodontia_proservations['total']
    )

    return {
        'pending_exams': pending_exams,
        'unsigned_documents': unsigned_documents,
        'overdue_endodontia_returns': overdue_endodontia_returns,
        'unrestored_endodontia': unrestored_endodontia,
        'overdue_endodontia_proservations': overdue_endodontia_proservations,
        'total': total,
        'has_alerts': total > 0,
    }


def _avg(values):
    values = [value for value in values if value is not None]
    return round(sum(values) / len(values), 1) if values else 0


def _period_bounds(filters, today, default_days=30):
    period_end = filters.get('end_date') or today
    period_start = filters.get('start_date') or (period_end - dt.timedelta(days=default_days - 1))
    period_days = max((period_end - period_start).days + 1, 1)
    previous_end = period_start - dt.timedelta(days=1)
    previous_start = previous_end - dt.timedelta(days=period_days - 1)
    return period_start, period_end, previous_start, previous_end, period_days


def _build_queue_wait_rows(filters):
    conditions = ["s.patient_id IS NOT NULL"]
    params = []
    if filters.get('municipio_id'):
        conditions.append("s.municipio_id = %s")
        params.append(filters['municipio_id'])
    if filters.get('especialidade_id'):
        conditions.append("s.especialidade_id = %s")
        params.append(filters['especialidade_id'])
    _append_patient_professional_exists(conditions, params, filters, patient_alias='p')

    return query(
        f"""
        WITH queue_entries AS (
            SELECT s.id as ticket_id,
                   p.id as patient_id,
                   p.nome as patient_name,
                   esp.nome as especialidade,
                   m.nome as municipio,
                   COALESCE(s.vinculada_em, s.entregue_em, s.criado_em, ta.data_acao::timestamp, p.criado_em) as entry_at
            FROM triagem_senhas s
            JOIN patients p ON p.id = s.patient_id
            JOIN especialidades esp ON esp.id = s.especialidade_id
            JOIN municipios m ON m.id = s.municipio_id
            LEFT JOIN triagem_acoes ta ON ta.id = s.triagem_acao_id
            {_where_clause(conditions)}
        )
        SELECT qe.*,
               MIN(c.data_consulta) FILTER (
                   WHERE c.status IN ('Realizado', 'Confirmado')
                     AND c.data_consulta >= qe.entry_at
               ) as first_attended_at
        FROM queue_entries qe
        LEFT JOIN consultas c ON c.patient_id = qe.patient_id
        GROUP BY qe.ticket_id, qe.patient_id, qe.patient_name, qe.especialidade,
                 qe.municipio, qe.entry_at
        """,
        tuple(params),
    ) or []


def _queue_wait_metrics(rows, filters, today):
    period_start, period_end, previous_start, previous_end, period_days = _period_bounds(filters, today)
    current_waits = []
    previous_waits = []
    active_waits = []
    without_return_items = []

    for row in rows or []:
        entry_date = _parse_date(row.get('entry_at'))
        if not entry_date or entry_date > period_end:
            continue

        attended_date = _parse_date(row.get('first_attended_at'))
        completed_wait = None
        if attended_date:
            completed_wait = max((attended_date - entry_date).days, 0)
            if period_start <= attended_date <= period_end:
                current_waits.append(completed_wait)
            elif previous_start <= attended_date <= previous_end:
                previous_waits.append(completed_wait)

        is_active_in_period = not attended_date or attended_date > period_end
        if is_active_in_period:
            waiting_days = max((period_end - entry_date).days, 0)
            active_waits.append(waiting_days)
            if waiting_days >= 30:
                without_return_items.append({
                    'patient_id': row.get('patient_id'),
                    'patient_name': row.get('patient_name'),
                    'especialidade': row.get('especialidade') or 'Sem especialidade',
                    'municipio': row.get('municipio') or 'Não informado',
                    'waiting_days': waiting_days,
                    'ticket_id': row.get('ticket_id'),
                })

    current_avg = _avg(current_waits)
    previous_avg = _avg(previous_waits)
    reduction = round(previous_avg - current_avg, 1) if previous_waits and current_waits else 0
    active_avg = _avg(active_waits)
    without_return_items.sort(key=lambda item: (-item['waiting_days'], item['patient_name'] or ''))

    return {
        'period_start': period_start,
        'period_end': period_end,
        'previous_start': previous_start,
        'previous_end': previous_end,
        'period_days': period_days,
        'wait_time': {
            'current_avg_days': current_avg,
            'previous_avg_days': previous_avg,
            'reduction_days': reduction,
            'trend_label': 'redução' if reduction > 0 else 'aumento' if reduction < 0 else 'estável',
            'completed_current': len(current_waits),
            'completed_previous': len(previous_waits),
            'active_avg_days': active_avg,
            'active_count': len(active_waits),
            'over_30_days': sum(1 for value in active_waits if value >= 30),
            'over_60_days': sum(1 for value in active_waits if value >= 60),
            'over_90_days': sum(1 for value in active_waits if value >= 90),
            'max_active_wait_days': max(active_waits) if active_waits else 0,
        },
        'without_return': {
            'total_over_30': len(without_return_items),
            'over_60_days': sum(1 for item in without_return_items if item['waiting_days'] >= 60),
            'over_90_days': sum(1 for item in without_return_items if item['waiting_days'] >= 90),
            'items': without_return_items[:6],
        },
    }


def _agenda_bottleneck_metrics(filters, period_start, period_end, limit=6):
    conditions = ["DATE(c.data_consulta) >= %s", "DATE(c.data_consulta) <= %s"]
    params = [period_start.isoformat(), period_end.isoformat()]
    if filters.get('professional_id'):
        conditions.append("c.dentista_id = %s")
        params.append(filters['professional_id'])
    if filters.get('execution_unit'):
        conditions.append("c.execution_unit = %s")
        params.append(filters['execution_unit'])
    _append_patient_triage_exists(conditions, params, filters, patient_alias='p')

    rows = query(
        f"""
        SELECT u.id as professional_id,
               COALESCE(NULLIF(u.full_name, ''), u.username) as professional_name,
               COUNT(*) as total,
               COUNT(*) FILTER (WHERE c.status = 'Pendente') as pending,
               COUNT(*) FILTER (WHERE c.status = 'Confirmado') as confirmed,
               COUNT(*) FILTER (WHERE c.status = 'Realizado') as done,
               COUNT(*) FILTER (WHERE c.status = 'Faltou') as no_show,
               COUNT(*) FILTER (WHERE c.status = 'Cancelado') as canceled
        FROM consultas c
        JOIN patients p ON p.id = c.patient_id
        JOIN users u ON u.id = c.dentista_id
        {_where_clause(conditions)}
        GROUP BY u.id, professional_name
        """,
        tuple(params),
    ) or []

    bottlenecks = []
    for row in rows:
        total = _as_int(row.get('total'))
        pending = _as_int(row.get('pending'))
        confirmed = _as_int(row.get('confirmed'))
        done = _as_int(row.get('done'))
        no_show = _as_int(row.get('no_show'))
        canceled = _as_int(row.get('canceled'))
        open_count = pending + confirmed
        bottleneck_score = (open_count * 2) + (no_show * 3) + canceled
        bottlenecks.append({
            'professional_id': row.get('professional_id'),
            'professional_name': row.get('professional_name') or 'Profissional não informado',
            'total': total,
            'pending': pending,
            'confirmed': confirmed,
            'done': done,
            'no_show': no_show,
            'canceled': canceled,
            'open_count': open_count,
            'no_show_rate': round((no_show / total) * 100, 1) if total else 0,
            'completion_rate': round((done / total) * 100, 1) if total else 0,
            'bottleneck_score': bottleneck_score,
        })

    bottlenecks.sort(key=lambda item: (-item['bottleneck_score'], -item['open_count'], item['professional_name']))
    return {
        'items': bottlenecks[:limit],
        'total_open': sum(item['open_count'] for item in bottlenecks),
        'total_no_show': sum(item['no_show'] for item in bottlenecks),
        'total_canceled': sum(item['canceled'] for item in bottlenecks),
    }


def get_queue_operational_metrics(filters=None, today=None):
    filters = normalize_command_center_filters(filters)
    today = today or dt.date.today()
    queue_rows = _build_queue_wait_rows(filters)
    queue_metrics = _queue_wait_metrics(queue_rows, filters, today)
    agenda_bottlenecks = _agenda_bottleneck_metrics(
        filters,
        queue_metrics['period_start'],
        queue_metrics['period_end'],
    )
    return {
        **queue_metrics,
        'agenda_bottlenecks': agenda_bottlenecks,
    }


def build_operational_alerts(
    red_alert_count,
    pending_treatments,
    agenda_by_status,
    priority_queue,
    inventory_alerts=None,
    specialty_bottlenecks=None,
    clinical_pending=None,
    queue_metrics=None,
):
    alerts = []

    if red_alert_count:
        alerts.append({
            'type': 'red_alert',
            'severity': 'critical',
            'title': 'Alerta vermelho oncológico',
            'message': f'{red_alert_count} paciente(s) com suspeita de neoplasia ativa.',
            'endpoint': 'patients.red_alert_list',
        })

    lesion_without_return = [
        patient for patient in priority_queue
        if patient.get('lesion_days_without_return') is not None
        and patient['lesion_days_without_return'] >= 14
    ]
    if lesion_without_return:
        alerts.append({
            'type': 'lesion_without_return',
            'severity': 'critical',
            'title': 'Lesão suspeita sem retorno',
            'message': f'{len(lesion_without_return)} paciente(s) com lesão suspeita sem retorno em 14 dias ou mais.',
            'endpoint': 'main.command_center',
        })

    two_no_shows = [patient for patient in priority_queue if int(patient.get('no_show_count') or 0) >= 2]
    if two_no_shows:
        alerts.append({
            'type': 'two_no_shows',
            'severity': 'critical',
            'title': 'Paciente faltou 2x',
            'message': f'{len(two_no_shows)} paciente(s) com duas faltas ou mais.',
            'endpoint': 'main.command_center',
        })

    if pending_treatments:
        alerts.append({
            'type': 'pending_treatments',
            'severity': 'warning',
            'title': 'Tratamentos pendentes',
            'message': f'{pending_treatments} procedimento(s) aguardando execução.',
            'endpoint': 'patients.pending_treatments',
        })

    if agenda_by_status.get('Faltou', 0):
        alerts.append({
            'type': 'no_show',
            'severity': 'warning',
            'title': 'Faltas registradas',
            'message': f"{agenda_by_status['Faltou']} falta(s) no histórico da agenda.",
            'endpoint': 'agenda.agenda_index',
            'endpoint_params': {'status': 'Faltou'},
        })

    if len(priority_queue) >= 10:
        alerts.append({
            'type': 'critical_queue',
            'severity': 'critical',
            'title': 'Fila crítica',
            'message': 'Fila de prioridade clínica com 10 ou mais pacientes ativos.',
            'endpoint': 'main.command_center',
        })

    if specialty_bottlenecks:
        top = specialty_bottlenecks[0]
        severity = 'critical' if top['critical'] or top['max_waiting_days'] >= 90 else 'warning'
        alerts.append({
            'type': 'critical_specialty_bottleneck' if severity == 'critical' else 'specialty_bottleneck',
            'severity': severity,
            'title': 'Gargalo por especialidade',
            'message': (
                f"{top['especialidade']} concentra {top['total']} caso(s) prioritário(s)"
                f" e espera máxima de {top['max_waiting_days']} dia(s)."
            ),
            'endpoint': 'main.command_center',
        })

    pending_exams = (clinical_pending or {}).get('pending_exams', {})
    if pending_exams.get('total'):
        alerts.append({
            'type': 'pending_exams',
            'severity': 'warning',
            'title': 'Exames pendentes',
            'message': (
                f"{pending_exams['total']} exame(s) aguardando validação clínica"
                f" em {pending_exams.get('patient_count', 0)} paciente(s)."
            ),
            'endpoint': 'main.command_center',
        })

    unsigned_documents = (clinical_pending or {}).get('unsigned_documents', {})
    if unsigned_documents.get('total'):
        alerts.append({
            'type': 'unsigned_documents',
            'severity': 'warning',
            'title': 'Documentos sem assinatura',
            'message': (
                f"{unsigned_documents['total']} documento(s) clínico(s) com assinatura pendente"
                f" em {unsigned_documents.get('patient_count', 0)} paciente(s)."
            ),
            'endpoint': 'main.command_center',
        })

    overdue_endodontia = (clinical_pending or {}).get('overdue_endodontia_returns', {})
    if overdue_endodontia.get('total'):
        alerts.append({
            'type': 'overdue_endodontia_returns',
            'severity': 'warning',
            'title': 'Endodontia sem retorno',
            'message': (
                f"{overdue_endodontia['total']} caso(s) endodôntico(s) com retorno vencido"
                f" em {overdue_endodontia.get('patient_count', 0)} paciente(s)."
            ),
            'endpoint': 'main.command_center',
        })

    unrestored_endodontia = (clinical_pending or {}).get('unrestored_endodontia', {})
    if unrestored_endodontia.get('total'):
        alerts.append({
            'type': 'unrestored_endodontia',
            'severity': 'warning',
            'title': 'Endodontia sem restauração',
            'message': (
                f"{unrestored_endodontia['total']} caso(s) obturado(s) aguardam restauração definitiva"
                f" em {unrestored_endodontia.get('patient_count', 0)} paciente(s)."
            ),
            'endpoint': 'main.command_center',
        })

    overdue_proservations = (clinical_pending or {}).get('overdue_endodontia_proservations', {})
    if overdue_proservations.get('total'):
        alerts.append({
            'type': 'overdue_endodontia_proservations',
            'severity': 'warning',
            'title': 'Proservação endodôntica vencida',
            'message': (
                f"{overdue_proservations['total']} retorno(s) de proservação vencido(s)"
                f" em {overdue_proservations.get('patient_count', 0)} paciente(s)."
            ),
            'endpoint': 'main.command_center',
        })

    without_return = (queue_metrics or {}).get('without_return', {})
    if without_return.get('total_over_30'):
        alerts.append({
            'type': 'queue_without_return',
            'severity': 'warning',
            'title': 'Fila sem retorno',
            'message': f"{without_return['total_over_30']} paciente(s) aguardam retorno há 30 dias ou mais.",
            'endpoint': 'main.command_center',
        })

    agenda_bottlenecks = (queue_metrics or {}).get('agenda_bottlenecks', {})
    if agenda_bottlenecks.get('total_open'):
        alerts.append({
            'type': 'agenda_bottleneck',
            'severity': 'warning',
            'title': 'Gargalo de agenda',
            'message': f"{agenda_bottlenecks['total_open']} consulta(s) pendente(s) ou confirmada(s) no período operacional.",
            'endpoint': 'main.command_center',
        })

    alerts.extend(inventory_alerts or [])

    return alerts
