import datetime as dt

from database import query
from services.epidemiology_service import normalize_period, percentage


def _as_int(value):
    return int(value or 0)


def _as_float(value):
    return float(value or 0)


def _month_start(value):
    return value.replace(day=1)


def _previous_month(value):
    first = _month_start(value)
    previous_last_day = first - dt.timedelta(days=1)
    return previous_last_day.replace(day=1), previous_last_day


def _growth_rate(current, previous):
    previous = _as_float(previous)
    if previous <= 0:
        return 0
    return round(((_as_float(current) - previous) / previous) * 100, 1)


def get_summary(start, end):
    production = query(
        """
        SELECT COUNT(*) FILTER (WHERE status = 'Concluído') as completed,
               COUNT(*) FILTER (WHERE status = 'Pendente') as pending,
               COUNT(DISTINCT patient_id) FILTER (WHERE status = 'Concluído') as treated_patients
        FROM tratamento_procedimentos
        WHERE criado_em::date BETWEEN %s AND %s
        """,
        (start.isoformat(), end.isoformat()),
        one=True,
    )

    appointments = query(
        """
        SELECT COUNT(*) as total,
               COUNT(*) FILTER (WHERE status = 'Realizado') as done,
               COUNT(*) FILTER (WHERE status = 'Faltou') as no_shows,
               COUNT(*) FILTER (WHERE status = 'Cancelado') as canceled,
               COUNT(DISTINCT patient_id) FILTER (WHERE status = 'Realizado') as patients_seen
        FROM consultas
        WHERE data_consulta::date BETWEEN %s AND %s
        """,
        (start.isoformat(), end.isoformat()),
        one=True,
    )

    queue = query(
        """
        SELECT COUNT(DISTINCT s.patient_id) as total,
               COUNT(DISTINCT s.patient_id) FILTER (
                   WHERE EXISTS (
                       SELECT 1
                       FROM consultas c
                       WHERE c.patient_id = s.patient_id
                         AND c.status IN ('Confirmado', 'Realizado')
                   )
               ) as scheduled_or_seen,
               COUNT(DISTINCT s.patient_id) FILTER (
                   WHERE NOT EXISTS (
                       SELECT 1
                       FROM consultas c
                       WHERE c.patient_id = s.patient_id
                         AND c.status IN ('Confirmado', 'Realizado')
                   )
               ) as repressed
        FROM triagem_senhas s
        WHERE s.patient_id IS NOT NULL
          AND COALESCE(s.vinculada_em, s.entregue_em, s.criado_em)::date BETWEEN %s AND %s
        """,
        (start.isoformat(), end.isoformat()),
        one=True,
    )

    social = query(
        """
        SELECT COUNT(DISTINCT p.id) as reached_patients,
               COUNT(DISTINCT COALESCE(NULLIF(TRIM(p.atendido_em), ''), 'Não informado')) as neighborhoods,
               COUNT(DISTINCT ts.municipio_id) as municipalities
        FROM patients p
        LEFT JOIN consultas c
          ON c.patient_id = p.id
         AND c.status = 'Realizado'
         AND c.data_consulta::date BETWEEN %s AND %s
        LEFT JOIN tratamento_procedimentos tp
          ON tp.patient_id = p.id
         AND tp.status = 'Concluído'
         AND tp.criado_em::date BETWEEN %s AND %s
        LEFT JOIN estomatologia e
          ON e.patient_id = p.id
         AND e.data_registro::date BETWEEN %s AND %s
        LEFT JOIN triagem_senhas ts ON ts.patient_id = p.id
        WHERE c.id IS NOT NULL
           OR tp.id IS NOT NULL
           OR e.id IS NOT NULL
        """,
        (
            start.isoformat(), end.isoformat(),
            start.isoformat(), end.isoformat(),
            start.isoformat(), end.isoformat(),
        ),
        one=True,
    )

    financial = query(
        """
        SELECT COALESCE(SUM(custo_estimado), 0) as total,
               COALESCE(SUM(custo_estimado) FILTER (WHERE status = 'Aprovado'), 0) as approved
        FROM planos_tratamento
        WHERE criado_em::date BETWEEN %s AND %s
        """,
        (start.isoformat(), end.isoformat()),
        one=True,
    )

    total_appointments = _as_int(appointments['total'])
    no_shows = _as_int(appointments['no_shows'])
    done_appointments = _as_int(appointments['done'])
    completed_procedures = _as_int(production['completed'])
    queue_total = _as_int(queue['total'])
    queue_scheduled_or_seen = _as_int(queue['scheduled_or_seen'])

    return {
        'completed_procedures': completed_procedures,
        'pending_procedures': _as_int(production['pending']),
        'treated_patients': _as_int(production['treated_patients']),
        'appointments': total_appointments,
        'appointments_done': done_appointments,
        'no_shows': no_shows,
        'canceled_appointments': _as_int(appointments['canceled']),
        'patients_seen': _as_int(appointments['patients_seen']),
        'attendance_rate': percentage(done_appointments, total_appointments),
        'no_show_rate': percentage(no_shows, total_appointments),
        'queue_total': queue_total,
        'queue_scheduled_or_seen': queue_scheduled_or_seen,
        'queue_repressed': _as_int(queue['repressed']),
        'queue_resolution_rate': percentage(queue_scheduled_or_seen, queue_total),
        'reached_patients': _as_int(social['reached_patients']),
        'neighborhoods': _as_int(social['neighborhoods']),
        'municipalities': _as_int(social['municipalities']),
        'estimated_plan_value': _as_float(financial['total']),
        'approved_plan_value': _as_float(financial['approved']),
        'plan_conversion_rate': percentage(financial['approved'], financial['total']),
    }


def get_previous_summary(start):
    previous_start, previous_end = _previous_month(start)
    return get_summary(previous_start, previous_end)


def get_targets(summary, previous_summary):
    production_target = max(_as_int(previous_summary['completed_procedures']), 1)
    attendance_target = 85
    queue_target = max(_as_int(previous_summary['queue_scheduled_or_seen']), 1)

    return [
        {
            'label': 'Produção Clínica',
            'current': summary['completed_procedures'],
            'target': production_target,
            'unit': 'procedimentos',
            'rate': min(100, percentage(summary['completed_procedures'], production_target)),
        },
        {
            'label': 'Comparecimento',
            'current': summary['attendance_rate'],
            'target': attendance_target,
            'unit': '%',
            'rate': min(100, percentage(summary['attendance_rate'], attendance_target)),
        },
        {
            'label': 'Fila Encaminhada',
            'current': summary['queue_scheduled_or_seen'],
            'target': queue_target,
            'unit': 'pacientes',
            'rate': min(100, percentage(summary['queue_scheduled_or_seen'], queue_target)),
        },
    ]


def get_monthly_comparison(end, months=6):
    anchor = _month_start(end)
    first_month = anchor
    for _ in range(months - 1):
        first_month = _previous_month(first_month)[0]

    rows = query(
        """
        WITH month_series AS (
            SELECT generate_series(%s::date, %s::date, interval '1 month')::date as month_start
        )
        SELECT ms.month_start,
               (
                   SELECT COUNT(*)
                   FROM patients p
                   WHERE p.criado_em::date >= ms.month_start
                     AND p.criado_em::date < (ms.month_start + interval '1 month')::date
               ) as new_patients,
               (
                   SELECT COUNT(*)
                   FROM tratamento_procedimentos tp
                   WHERE tp.status = 'Concluído'
                     AND tp.criado_em::date >= ms.month_start
                     AND tp.criado_em::date < (ms.month_start + interval '1 month')::date
               ) as completed_procedures,
               (
                   SELECT COUNT(*)
                   FROM consultas c
                   WHERE c.status = 'Realizado'
                     AND c.data_consulta::date >= ms.month_start
                     AND c.data_consulta::date < (ms.month_start + interval '1 month')::date
               ) as appointments_done,
               (
                   SELECT COUNT(*)
                   FROM consultas c
                   WHERE c.status = 'Faltou'
                     AND c.data_consulta::date >= ms.month_start
                     AND c.data_consulta::date < (ms.month_start + interval '1 month')::date
               ) as no_shows,
               (
                   SELECT COUNT(*)
                   FROM estomatologia e
                   WHERE e.suspeita_neoplasia = TRUE
                     AND e.data_registro::date >= ms.month_start
                     AND e.data_registro::date < (ms.month_start + interval '1 month')::date
               ) as cancer_suspicions
        FROM month_series ms
        ORDER BY ms.month_start ASC
        """,
        (first_month.isoformat(), anchor.isoformat()),
    )

    return [
        {
            'month_start': row['month_start'],
            'label': row['month_start'].strftime('%m/%Y'),
            'new_patients': _as_int(row['new_patients']),
            'completed_procedures': _as_int(row['completed_procedures']),
            'appointments_done': _as_int(row['appointments_done']),
            'no_shows': _as_int(row['no_shows']),
            'cancer_suspicions': _as_int(row['cancer_suspicions']),
        }
        for row in rows or []
    ]


def get_professional_ranking(start, end, limit=10):
    rows = query(
        """
        SELECT COALESCE(u.full_name, u.username, 'Não informado') as professional,
               COUNT(tp.id) FILTER (WHERE tp.status = 'Concluído') as completed_procedures,
               COUNT(DISTINCT tp.patient_id) FILTER (WHERE tp.status = 'Concluído') as patients
        FROM tratamento_procedimentos tp
        LEFT JOIN users u ON u.id = tp.professor_id
        WHERE tp.criado_em::date BETWEEN %s AND %s
        GROUP BY professional
        HAVING COUNT(tp.id) FILTER (WHERE tp.status = 'Concluído') > 0
        ORDER BY completed_procedures DESC, patients DESC, professional ASC
        LIMIT %s
        """,
        (start.isoformat(), end.isoformat(), limit),
    )
    return rows or []


def get_neighborhood_ranking(start, end, limit=10):
    rows = query(
        """
        SELECT COALESCE(NULLIF(TRIM(p.atendido_em), ''), 'Não informado') as bairro,
               COUNT(DISTINCT p.id) FILTER (
                   WHERE c.id IS NOT NULL OR tp.id IS NOT NULL OR e.id IS NOT NULL
               ) as reached_patients,
               COUNT(DISTINCT e.id) FILTER (WHERE e.suspeita_neoplasia = TRUE) as cancer_suspicions,
               COUNT(DISTINCT c.id) FILTER (WHERE c.status = 'Faltou') as no_shows
        FROM patients p
        LEFT JOIN consultas c
          ON c.patient_id = p.id
         AND c.data_consulta::date BETWEEN %s AND %s
        LEFT JOIN tratamento_procedimentos tp
          ON tp.patient_id = p.id
         AND tp.status = 'Concluído'
         AND tp.criado_em::date BETWEEN %s AND %s
        LEFT JOIN estomatologia e
          ON e.patient_id = p.id
         AND e.data_registro::date BETWEEN %s AND %s
        GROUP BY bairro
        ORDER BY reached_patients DESC, cancer_suspicions DESC, no_shows DESC, bairro ASC
        LIMIT %s
        """,
        (
            start.isoformat(), end.isoformat(),
            start.isoformat(), end.isoformat(),
            start.isoformat(), end.isoformat(),
            limit,
        ),
    )
    return rows or []


def get_specialty_ranking(start, end, limit=10):
    rows = query(
        """
        SELECT esp.nome as especialidade,
               COUNT(DISTINCT s.patient_id) as demand,
               COUNT(DISTINCT s.patient_id) FILTER (
                   WHERE EXISTS (
                       SELECT 1
                       FROM consultas c
                       WHERE c.patient_id = s.patient_id
                         AND c.status IN ('Confirmado', 'Realizado')
                   )
               ) as scheduled_or_seen,
               COUNT(DISTINCT s.patient_id) FILTER (
                   WHERE NOT EXISTS (
                       SELECT 1
                       FROM consultas c
                       WHERE c.patient_id = s.patient_id
                         AND c.status IN ('Confirmado', 'Realizado')
                   )
               ) as repressed
        FROM triagem_senhas s
        JOIN especialidades esp ON esp.id = s.especialidade_id
        WHERE s.patient_id IS NOT NULL
          AND COALESCE(s.vinculada_em, s.entregue_em, s.criado_em)::date BETWEEN %s AND %s
        GROUP BY esp.nome
        ORDER BY repressed DESC, demand DESC, esp.nome ASC
        LIMIT %s
        """,
        (start.isoformat(), end.isoformat(), limit),
    )
    return rows or []


def get_executive_bi_dashboard(start_date=None, end_date=None, today=None):
    today = today or dt.date.today()
    start, end = normalize_period(start_date, end_date, today=today)
    previous_summary = get_previous_summary(start)
    summary = get_summary(start, end)

    return {
        'period': {
            'start': start,
            'end': end,
        },
        'summary': summary,
        'previous_summary': previous_summary,
        'targets': get_targets(summary, previous_summary),
        'growth': {
            'production': _growth_rate(summary['completed_procedures'], previous_summary['completed_procedures']),
            'patients_seen': _growth_rate(summary['patients_seen'], previous_summary['patients_seen']),
            'queue_resolution': _growth_rate(summary['queue_scheduled_or_seen'], previous_summary['queue_scheduled_or_seen']),
            'no_show_rate': round(summary['no_show_rate'] - previous_summary['no_show_rate'], 1),
        },
        'monthly_comparison': get_monthly_comparison(end),
        'professional_ranking': get_professional_ranking(start, end),
        'neighborhood_ranking': get_neighborhood_ranking(start, end),
        'specialty_ranking': get_specialty_ranking(start, end),
    }
