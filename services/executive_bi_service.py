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


BI_VIEWS = {
    'geral': {
        'label': 'Geral',
        'description': 'Síntese executiva consolidada para leitura rápida da operação.',
    },
    'prefeitura': {
        'label': 'Prefeitura',
        'description': 'Impacto social, bairros alcançados, fila e economia estimada.',
    },
    'ssa': {
        'label': 'SSA',
        'description': 'Produção assistencial, oncologia bucal, regulação e indicadores epidemiológicos.',
    },
    'sms': {
        'label': 'SMS',
        'description': 'Cobertura municipal, demanda reprimida, comparecimento e atendimento territorial.',
    },
    'coordenacao_clinica': {
        'label': 'Coordenação Clínica',
        'description': 'Produtividade, especialidades críticas, pendências e gargalos operacionais.',
    },
    'auditoria': {
        'label': 'Auditoria',
        'description': 'Conformidade operacional, rastreabilidade SIGTAP/e-SUS e cobertura metodológica.',
    },
}


def normalize_bi_view(value):
    selected = (value or '').strip()
    return selected if selected in BI_VIEWS else 'geral'


def get_bi_view_options():
    return [
        {'value': key, **metadata}
        for key, metadata in BI_VIEWS.items()
    ]


def _money(value):
    return f"R$ {_as_float(value):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def get_summary(start, end):
    production = query(
        """
        SELECT COUNT(*) FILTER (WHERE status = 'Concluído') as completed,
               COUNT(*) FILTER (WHERE status = 'Pendente') as pending,
               COUNT(DISTINCT patient_id) FILTER (WHERE status = 'Concluído') as treated_patients,
               COUNT(*) FILTER (WHERE status = 'Concluído' AND NULLIF(TRIM(sigtap_code), '') IS NOT NULL) as completed_with_sigtap,
               COUNT(*) FILTER (WHERE status = 'Concluído' AND NULLIF(TRIM(sigtap_code), '') IS NULL) as completed_without_sigtap
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
               COUNT(DISTINCT COALESCE(NULLIF(TRIM(p.endereco_bairro), ''), NULLIF(TRIM(p.atendido_em), ''), 'Não informado')) as neighborhoods,
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

    oncology = query(
        """
        SELECT COUNT(*) as lesion_records,
               COUNT(DISTINCT patient_id) FILTER (WHERE suspeita_neoplasia = TRUE) as cancer_suspicions,
               COUNT(DISTINCT patient_id) FILTER (WHERE cancer_confirmed = TRUE) as cancer_confirmed,
               COUNT(*) FILTER (WHERE encaminhado_para_biopsia = TRUE) as biopsy_referrals
        FROM estomatologia
        WHERE data_registro::date BETWEEN %s AND %s
        """,
        (start.isoformat(), end.isoformat()),
        one=True,
    )

    production = production or {}
    appointments = appointments or {}
    queue = queue or {}
    social = social or {}
    financial = financial or {}
    oncology = oncology or {}

    total_appointments = _as_int(appointments.get('total'))
    no_shows = _as_int(appointments.get('no_shows'))
    done_appointments = _as_int(appointments.get('done'))
    completed_procedures = _as_int(production.get('completed'))
    completed_with_sigtap = _as_int(production.get('completed_with_sigtap'))
    queue_total = _as_int(queue.get('total'))
    queue_scheduled_or_seen = _as_int(queue.get('scheduled_or_seen'))

    return {
        'completed_procedures': completed_procedures,
        'pending_procedures': _as_int(production.get('pending')),
        'treated_patients': _as_int(production.get('treated_patients')),
        'completed_with_sigtap': completed_with_sigtap,
        'completed_without_sigtap': _as_int(production.get('completed_without_sigtap')),
        'sigtap_coverage_rate': percentage(completed_with_sigtap, completed_procedures),
        'appointments': total_appointments,
        'appointments_done': done_appointments,
        'no_shows': no_shows,
        'canceled_appointments': _as_int(appointments.get('canceled')),
        'patients_seen': _as_int(appointments.get('patients_seen')),
        'attendance_rate': percentage(done_appointments, total_appointments),
        'no_show_rate': percentage(no_shows, total_appointments),
        'queue_total': queue_total,
        'queue_scheduled_or_seen': queue_scheduled_or_seen,
        'queue_repressed': _as_int(queue.get('repressed')),
        'queue_resolution_rate': percentage(queue_scheduled_or_seen, queue_total),
        'reached_patients': _as_int(social.get('reached_patients')),
        'neighborhoods': _as_int(social.get('neighborhoods')),
        'municipalities': _as_int(social.get('municipalities')),
        'estimated_plan_value': _as_float(financial.get('total')),
        'approved_plan_value': _as_float(financial.get('approved')),
        'plan_conversion_rate': percentage(financial.get('approved'), financial.get('total')),
        'lesion_records': _as_int(oncology.get('lesion_records')),
        'cancer_suspicions': _as_int(oncology.get('cancer_suspicions')),
        'cancer_confirmed': _as_int(oncology.get('cancer_confirmed')),
        'biopsy_referrals': _as_int(oncology.get('biopsy_referrals')),
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
        LEFT JOIN users u ON u.id = tp.validator_id
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
        SELECT COALESCE(NULLIF(TRIM(p.endereco_bairro), ''), NULLIF(TRIM(p.atendido_em), ''), 'Não informado') as bairro,
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


def get_economy_analysis(start, end, limit=8):
    rows = query(
        """
        SELECT COALESCE(NULLIF(TRIM(tp.sigtap_code), ''), 'sem_codigo') as sigtap_code,
               COALESCE(
                   MAX(NULLIF(TRIM(tp.sigtap_name), '')),
                   MAX(NULLIF(TRIM(cr.sigtap_name), '')),
                   MAX(NULLIF(TRIM(tp.descricao), '')),
                   'Não informado'
               ) as procedure_name,
               COUNT(tp.id) as completed_procedures,
               COALESCE(MAX(cr.public_cost), 0) as public_unit_cost,
               COALESCE(MAX(cr.private_reference), 0) as private_unit_reference,
               SUM(COALESCE(cr.public_cost, 0)) as public_value,
               SUM(COALESCE(cr.private_reference, 0)) as reference_value,
               SUM(GREATEST(COALESCE(cr.private_reference, 0) - COALESCE(cr.public_cost, 0), 0)) as estimated_savings,
               COUNT(tp.id) FILTER (WHERE cr.id IS NULL) as missing_reference,
               COALESCE(MAX(cr.reference_label), 'Sem referência cadastrada') as reference_label,
               COALESCE(MAX(cr.source), 'missing') as source,
               COALESCE(MAX(cr.methodology_status), 'missing') as methodology_status
        FROM tratamento_procedimentos tp
        LEFT JOIN procedure_cost_references cr
          ON cr.sigtap_code = tp.sigtap_code
         AND cr.active = TRUE
        WHERE tp.status = 'Concluído'
          AND tp.criado_em::date BETWEEN %s AND %s
        GROUP BY COALESCE(NULLIF(TRIM(tp.sigtap_code), ''), 'sem_codigo')
        ORDER BY estimated_savings DESC, completed_procedures DESC, procedure_name ASC
        """,
        (start.isoformat(), end.isoformat()),
    ) or []

    items = []
    for row in rows:
        completed = _as_int(row.get('completed_procedures'))
        item = {
            'sigtap_code': row.get('sigtap_code'),
            'procedure_name': row.get('procedure_name'),
            'completed_procedures': completed,
            'public_unit_cost': _as_float(row.get('public_unit_cost')),
            'private_unit_reference': _as_float(row.get('private_unit_reference')),
            'public_value': _as_float(row.get('public_value')),
            'reference_value': _as_float(row.get('reference_value')),
            'estimated_savings': _as_float(row.get('estimated_savings')),
            'missing_reference': _as_int(row.get('missing_reference')),
            'reference_label': row.get('reference_label'),
            'source': row.get('source'),
            'methodology_status': row.get('methodology_status'),
        }
        item['reference_coverage_rate'] = percentage(completed - item['missing_reference'], completed)
        items.append(item)

    totals = {
        'completed_procedures': sum(item['completed_procedures'] for item in items),
        'public_value': round(sum(item['public_value'] for item in items), 2),
        'reference_value': round(sum(item['reference_value'] for item in items), 2),
        'estimated_savings': round(sum(item['estimated_savings'] for item in items), 2),
        'missing_reference': sum(item['missing_reference'] for item in items),
    }
    totals['reference_coverage_rate'] = percentage(
        totals['completed_procedures'] - totals['missing_reference'],
        totals['completed_procedures'],
    )

    if totals['completed_procedures'] <= 0:
        methodology_status = 'sem produção concluída no período'
    elif totals['missing_reference']:
        methodology_status = 'referência parcial'
    elif any(item['methodology_status'] != 'validated' for item in items):
        methodology_status = 'estimativa operacional aguardando validação pública'
    else:
        methodology_status = 'metodologia validada'

    return {
        **totals,
        'methodology_status': methodology_status,
        'methodology_note': (
            'Economia estimada pela diferença entre referência privada/interna e custo público unitário '
            'por procedimento SIGTAP concluído. Valores draft devem ser substituídos por tabela homologada.'
        ),
        'items': items[:limit],
    }


def _view_card(label, value, note='', tone='primary'):
    return {
        'label': label,
        'value': value,
        'note': note,
        'tone': tone,
    }


def _view_focus(label, value, detail=''):
    return {
        'label': label,
        'value': value,
        'detail': detail,
    }


def get_government_view_context(
    selected_view,
    summary,
    economy,
    professional_ranking=None,
    neighborhood_ranking=None,
    specialty_ranking=None,
):
    selected_view = normalize_bi_view(selected_view)
    professional_ranking = professional_ranking or []
    neighborhood_ranking = neighborhood_ranking or []
    specialty_ranking = specialty_ranking or []

    contexts = {
        'geral': {
            'cards': [
                _view_card('Produção', summary['completed_procedures'], 'procedimentos concluídos'),
                _view_card('Atendidos', summary['patients_seen'], 'pacientes com consulta realizada', 'success'),
                _view_card('Fila encaminhada', summary['queue_scheduled_or_seen'], 'pacientes agendados ou atendidos'),
                _view_card('Economia estimada', _money(economy['estimated_savings']), economy['methodology_status'], 'success'),
            ],
            'focus': [
                _view_focus('Maior produção', professional_ranking[0]['professional'] if professional_ranking else 'Sem produção', 'ranking profissional'),
                _view_focus('Especialidade crítica', specialty_ranking[0]['especialidade'] if specialty_ranking else 'Sem demanda', 'demanda reprimida'),
                _view_focus('Território alcançado', f"{summary['neighborhoods']} bairros", f"{summary['municipalities']} municípios"),
            ],
        },
        'prefeitura': {
            'cards': [
                _view_card('Impacto social', summary['reached_patients'], 'pacientes alcançados', 'success'),
                _view_card('Bairros atendidos', summary['neighborhoods'], 'cobertura territorial'),
                _view_card('Fila reduzida', summary['queue_scheduled_or_seen'], f"{summary['queue_resolution_rate']}% de encaminhamento"),
                _view_card('Economia estimada', _money(economy['estimated_savings']), economy['methodology_status'], 'success'),
            ],
            'focus': [
                _view_focus('Demanda reprimida', summary['queue_repressed'], 'pacientes ainda sem agenda/atendimento'),
                _view_focus('Maior bairro atendido', neighborhood_ranking[0]['bairro'] if neighborhood_ranking else 'Sem bairro', 'alcance territorial'),
                _view_focus('Planos aprovados', _money(summary['approved_plan_value']), f"{summary['plan_conversion_rate']}% de conversão"),
            ],
        },
        'ssa': {
            'cards': [
                _view_card('Produção clínica', summary['completed_procedures'], 'procedimentos concluídos'),
                _view_card('Suspeitas oncológicas', summary['cancer_suspicions'], 'pacientes sinalizados', 'danger'),
                _view_card('Câncer confirmado', summary['cancer_confirmed'], 'diagnóstico formal registrado', 'danger'),
                _view_card('Biópsias', summary['biopsy_referrals'], 'encaminhamentos registrados'),
            ],
            'focus': [
                _view_focus('Lesões registradas', summary['lesion_records'], 'estomatologia no período'),
                _view_focus('Cobertura SIGTAP', f"{summary['sigtap_coverage_rate']}%", 'produção concluída codificada'),
                _view_focus('Especialidade crítica', specialty_ranking[0]['especialidade'] if specialty_ranking else 'Sem demanda', 'demanda reprimida'),
            ],
        },
        'sms': {
            'cards': [
                _view_card('Municípios vinculados', summary['municipalities'], 'origem dos pacientes'),
                _view_card('Demanda triada', summary['queue_total'], 'pacientes com senha vinculada'),
                _view_card('Demanda reprimida', summary['queue_repressed'], 'sem consulta confirmada/realizada', 'warning'),
                _view_card('Comparecimento', f"{summary['attendance_rate']}%", 'consultas realizadas'),
            ],
            'focus': [
                _view_focus('Absenteísmo', f"{summary['no_show_rate']}%", 'faltas sobre agenda'),
                _view_focus('Bairros alcançados', summary['neighborhoods'], 'cobertura local'),
                _view_focus('Fila encaminhada', summary['queue_scheduled_or_seen'], f"{summary['queue_resolution_rate']}% da demanda"),
            ],
        },
        'coordenacao_clinica': {
            'cards': [
                _view_card('Produção', summary['completed_procedures'], 'procedimentos concluídos'),
                _view_card('Pendentes', summary['pending_procedures'], 'procedimentos em aberto', 'warning'),
                _view_card('Comparecimento', f"{summary['attendance_rate']}%", 'adesão à agenda', 'success'),
                _view_card('Absenteísmo', f"{summary['no_show_rate']}%", 'faltas no período', 'warning'),
            ],
            'focus': [
                _view_focus('Profissional destaque', professional_ranking[0]['professional'] if professional_ranking else 'Sem produção', 'ranking de produção'),
                _view_focus('Especialidade crítica', specialty_ranking[0]['especialidade'] if specialty_ranking else 'Sem demanda', 'maior demanda reprimida'),
                _view_focus('Procedimentos sem SIGTAP', summary['completed_without_sigtap'], 'impacta e-SUS/relatórios'),
            ],
        },
        'auditoria': {
            'cards': [
                _view_card('Cobertura SIGTAP', f"{summary['sigtap_coverage_rate']}%", 'produção concluída codificada'),
                _view_card('Sem SIGTAP', summary['completed_without_sigtap'], 'exigem correção', 'warning'),
                _view_card('Cobertura referência', f"{economy['reference_coverage_rate']}%", 'custo por procedimento'),
                _view_card('Status metodologia', economy['methodology_status'], 'economia gerada'),
            ],
            'focus': [
                _view_focus('Referências faltantes', economy['missing_reference'], 'procedimentos sem custo configurado'),
                _view_focus('Produção rastreável', summary['completed_with_sigtap'], 'procedimentos concluídos com SIGTAP'),
                _view_focus('Economia estimada', _money(economy['estimated_savings']), 'exige validação da referência'),
            ],
        },
    }

    context = contexts[selected_view]
    return {
        'selected': selected_view,
        'label': BI_VIEWS[selected_view]['label'],
        'description': BI_VIEWS[selected_view]['description'],
        **context,
    }


def get_executive_bi_dashboard(start_date=None, end_date=None, today=None, view=None):
    today = today or dt.date.today()
    start, end = normalize_period(start_date, end_date, today=today)
    selected_view = normalize_bi_view(view)
    previous_summary = get_previous_summary(start)
    summary = get_summary(start, end)
    economy = get_economy_analysis(start, end)
    professional_ranking = get_professional_ranking(start, end)
    neighborhood_ranking = get_neighborhood_ranking(start, end)
    specialty_ranking = get_specialty_ranking(start, end)

    return {
        'period': {
            'start': start,
            'end': end,
        },
        'filters': {
            'view': selected_view,
            'views': get_bi_view_options(),
        },
        'summary': summary,
        'previous_summary': previous_summary,
        'economy': economy,
        'government_view': get_government_view_context(
            selected_view,
            summary,
            economy,
            professional_ranking=professional_ranking,
            neighborhood_ranking=neighborhood_ranking,
            specialty_ranking=specialty_ranking,
        ),
        'targets': get_targets(summary, previous_summary),
        'growth': {
            'production': _growth_rate(summary['completed_procedures'], previous_summary['completed_procedures']),
            'patients_seen': _growth_rate(summary['patients_seen'], previous_summary.get('patients_seen')),
            'queue_resolution': _growth_rate(summary['queue_scheduled_or_seen'], previous_summary.get('queue_scheduled_or_seen')),
            'no_show_rate': round(summary['no_show_rate'] - previous_summary.get('no_show_rate', 0), 1),
        },
        'monthly_comparison': get_monthly_comparison(end),
        'professional_ranking': professional_ranking,
        'neighborhood_ranking': neighborhood_ranking,
        'specialty_ranking': specialty_ranking,
    }
