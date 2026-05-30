import datetime as dt

from database import query


CRITICAL_ALERTS = {'red_alert', 'lesion_without_return', 'two_no_shows', 'critical_queue'}


def _parse_birthdate(value):
    if not value:
        return None

    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return dt.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


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

    if patient.get('suspeita_neoplasia'):
        score += 100
        reasons.append('Suspeita de neoplasia')

    age = calculate_age(patient.get('data_nascimento'), today=today)
    if age is not None and age >= 60:
        score += 25
        reasons.append('Idoso')

    no_show_count = int(patient.get('no_show_count') or 0)
    if no_show_count >= 2:
        score += 20
        reasons.append('Duas faltas ou mais')

    pending_treatments = int(patient.get('pending_treatments') or 0)
    if pending_treatments > 0:
        score += min(20, pending_treatments * 5)
        reasons.append('Tratamento pendente')

    lesion_days_without_return = patient.get('lesion_days_without_return')
    if lesion_days_without_return is not None and lesion_days_without_return >= 14:
        score += 30
        reasons.append('Lesão suspeita sem retorno')

    return {
        'score': score,
        'risk_level': get_risk_level(score),
        'reasons': reasons,
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


def get_command_center_data():
    today = dt.date.today()
    today_str = today.isoformat()
    month_start = today.replace(day=1).isoformat()

    patients_today = query(
        """
        SELECT c.id, c.data_consulta, c.status, c.duracao_minutos,
               p.id as patient_id, p.nome as patient_nome,
               u.full_name as professional_name
        FROM consultas c
        JOIN patients p ON c.patient_id = p.id
        JOIN users u ON c.dentista_id = u.id
        WHERE DATE(c.data_consulta) = %s
        ORDER BY c.data_consulta ASC
        """,
        (today_str,)
    )

    production = query(
        """
        SELECT COUNT(*) FILTER (WHERE status = 'Concluído' AND data_sessao = %s) as today,
               COUNT(*) FILTER (WHERE status = 'Concluído' AND data_sessao >= %s) as month
        FROM tratamento_procedimentos
        """,
        (today_str, month_start),
        one=True
    )

    agenda_stats_rows = query("SELECT status, COUNT(*) as count FROM consultas GROUP BY status")
    agenda_by_status = {row['status']: row['count'] for row in agenda_stats_rows or []}

    red_alert_count = query(
        "SELECT COUNT(*) as count FROM estomatologia WHERE suspeita_neoplasia = TRUE",
        one=True
    )['count']

    pending_treatments = query(
        "SELECT COUNT(*) as count FROM tratamento_procedimentos WHERE status = 'Pendente'",
        one=True
    )['count']

    neighborhoods = query(
        """
        SELECT COALESCE(NULLIF(TRIM(atendido_em), ''), 'Não informado') as bairro,
               COUNT(*) as total
        FROM patients
        GROUP BY bairro
        ORDER BY total DESC, bairro ASC
        LIMIT 8
        """
    )

    specialty_queue = query(
        """
        SELECT e.nome as especialidade, COUNT(*) as total
        FROM triagem_senhas s
        JOIN especialidades e ON s.especialidade_id = e.id
        WHERE s.patient_id IS NOT NULL
        GROUP BY e.nome
        ORDER BY total DESC, e.nome ASC
        LIMIT 8
        """
    )

    full_priority_queue = get_priority_queue(limit=None)
    priority_queue = full_priority_queue[:12]
    alerts = build_operational_alerts(red_alert_count, pending_treatments, agenda_by_status, full_priority_queue)

    return {
        'today': today,
        'patients_today': patients_today,
        'production': {
            'today': production['today'] or 0,
            'month': production['month'] or 0,
        },
        'agenda': {
            'pending': agenda_by_status.get('Pendente', 0),
            'confirmed': agenda_by_status.get('Confirmado', 0),
            'done': agenda_by_status.get('Realizado', 0),
            'canceled': agenda_by_status.get('Cancelado', 0),
            'no_show': agenda_by_status.get('Faltou', 0),
            'total': sum(agenda_by_status.values()),
        },
        'red_alert_count': red_alert_count,
        'pending_treatments': pending_treatments,
        'neighborhoods': neighborhoods,
        'specialty_queue': specialty_queue,
        'priority_queue': priority_queue,
        'alerts': alerts,
        'critical_alert_count': sum(1 for alert in alerts if alert['type'] in CRITICAL_ALERTS),
    }


def get_priority_queue(limit=20):
    rows = query(
        """
        WITH latest_estomatologia AS (
            SELECT DISTINCT ON (patient_id)
                   id, patient_id, suspeita_neoplasia, localizacao_lesao, data_registro
            FROM estomatologia
            ORDER BY patient_id, data_registro DESC, id DESC
        )
        SELECT p.id, p.nome, p.data_nascimento,
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
               e.data_registro as estomatologia_data
        FROM patients p
        LEFT JOIN latest_estomatologia e ON e.patient_id = p.id
        LEFT JOIN consultas c ON c.patient_id = p.id
        LEFT JOIN tratamento_procedimentos tp ON tp.patient_id = p.id
        GROUP BY p.id, p.nome, p.data_nascimento, e.suspeita_neoplasia,
                 e.localizacao_lesao, e.data_registro
        """
    )

    queue = []
    for row in rows or []:
        priority = calculate_priority_score(row)
        if priority['score'] <= 0:
            continue
        queue.append({**row, **priority})

    queue.sort(key=lambda item: (-item['score'], item['nome']))
    return queue[:limit] if limit else queue


def build_operational_alerts(red_alert_count, pending_treatments, agenda_by_status, priority_queue):
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

    return alerts
