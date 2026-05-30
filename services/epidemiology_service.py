import datetime as dt
from collections import Counter

from database import query


def _parse_date(value, fallback):
    if not value:
        return fallback
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return fallback


def normalize_period(start_date=None, end_date=None, today=None):
    today = today or dt.date.today()
    start = _parse_date(start_date, today.replace(day=1))
    end = _parse_date(end_date, today)

    if start > end:
        start, end = end, start

    return start, end


def percentage(part, total):
    total = int(total or 0)
    if total <= 0:
        return 0
    return round((int(part or 0) / total) * 100, 1)


def _as_int(value):
    return int(value or 0)


def _clean_label(value, fallback='Não informado'):
    if value is None:
        return fallback
    cleaned = str(value).strip()
    return cleaned or fallback


def _neighborhood_filter(alias, neighborhood):
    if not neighborhood:
        return '', []
    return (
        f"AND COALESCE(NULLIF(TRIM({alias}.atendido_em), ''), 'Não informado') = %s",
        [neighborhood],
    )


def _parse_birthdate(value):
    if not value:
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value

    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return dt.datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _age_group(birthdate, today):
    parsed = _parse_birthdate(birthdate)
    if not parsed:
        return 'Não informado'

    age = today.year - parsed.year - ((today.month, today.day) < (parsed.month, parsed.day))
    if age <= 12:
        return '0-12'
    if age <= 17:
        return '13-17'
    if age <= 39:
        return '18-39'
    if age <= 59:
        return '40-59'
    return '60+'


def get_available_neighborhoods():
    return query(
        """
        SELECT DISTINCT COALESCE(NULLIF(TRIM(atendido_em), ''), 'Não informado') as bairro
        FROM patients
        ORDER BY bairro ASC
        """
    )


def get_summary(start, end, neighborhood=None):
    neighborhood_clause, neighborhood_params = _neighborhood_filter('p', neighborhood)

    patients = query(
        f"""
        SELECT COUNT(*) as total
        FROM patients p
        WHERE p.criado_em::date BETWEEN %s AND %s
        {neighborhood_clause}
        """,
        (start.isoformat(), end.isoformat(), *neighborhood_params),
        one=True,
    )

    lesions = query(
        f"""
        SELECT COUNT(*) as lesion_records,
               COUNT(DISTINCT e.patient_id) as lesion_patients,
               COUNT(DISTINCT e.patient_id) FILTER (WHERE e.suspeita_neoplasia = TRUE) as cancer_suspicions,
               COUNT(*) FILTER (WHERE e.encaminhado_para_biopsia = TRUE) as biopsy_referrals
        FROM estomatologia e
        JOIN patients p ON p.id = e.patient_id
        WHERE e.data_registro::date BETWEEN %s AND %s
        {neighborhood_clause}
        """,
        (start.isoformat(), end.isoformat(), *neighborhood_params),
        one=True,
    )

    appointments = query(
        f"""
        SELECT COUNT(*) as total,
               COUNT(*) FILTER (WHERE c.status = 'Faltou') as no_shows,
               COUNT(*) FILTER (WHERE c.status = 'Realizado') as done
        FROM consultas c
        JOIN patients p ON p.id = c.patient_id
        WHERE c.data_consulta::date BETWEEN %s AND %s
        {neighborhood_clause}
        """,
        (start.isoformat(), end.isoformat(), *neighborhood_params),
        one=True,
    )

    prosthetic_need = query(
        f"""
        WITH prosthetic_need AS (
            SELECT s.patient_id, COALESCE(s.vinculada_em, s.entregue_em, s.criado_em) as event_date
            FROM triagem_senhas s
            JOIN especialidades esp ON esp.id = s.especialidade_id
            WHERE s.patient_id IS NOT NULL
              AND (esp.codigo = 'P' OR esp.nome ILIKE '%%Prótese%%')
            UNION ALL
            SELECT patient_id, data as event_date
            FROM prosthesis
        )
        SELECT COUNT(DISTINCT p.id) as total
        FROM prosthetic_need pn
        JOIN patients p ON p.id = pn.patient_id
        WHERE pn.event_date::date BETWEEN %s AND %s
        {neighborhood_clause}
        """,
        (start.isoformat(), end.isoformat(), *neighborhood_params),
        one=True,
    )

    repressed_demand = query(
        f"""
        SELECT COUNT(DISTINCT s.patient_id) as total
        FROM triagem_senhas s
        JOIN patients p ON p.id = s.patient_id
        WHERE s.patient_id IS NOT NULL
          AND COALESCE(s.vinculada_em, s.entregue_em, s.criado_em)::date BETWEEN %s AND %s
          AND NOT EXISTS (
              SELECT 1
              FROM consultas c
              WHERE c.patient_id = s.patient_id
                AND c.status IN ('Confirmado', 'Realizado')
          )
        {neighborhood_clause}
        """,
        (start.isoformat(), end.isoformat(), *neighborhood_params),
        one=True,
    )

    total_appointments = _as_int(appointments['total'])
    lesion_records = _as_int(lesions['lesion_records'])

    return {
        'new_patients': _as_int(patients['total']),
        'lesion_records': lesion_records,
        'lesion_patients': _as_int(lesions['lesion_patients']),
        'cancer_suspicions': _as_int(lesions['cancer_suspicions']),
        'biopsy_referrals': _as_int(lesions['biopsy_referrals']),
        'appointments': total_appointments,
        'no_shows': _as_int(appointments['no_shows']),
        'done_appointments': _as_int(appointments['done']),
        'no_show_rate': percentage(appointments['no_shows'], total_appointments),
        'cancer_suspicion_rate': percentage(lesions['cancer_suspicions'], lesion_records),
        'prosthetic_need': _as_int(prosthetic_need['total']),
        'repressed_demand': _as_int(repressed_demand['total']),
    }


def get_neighborhood_indicators(start, end, neighborhood=None, limit=12):
    where_clause = ''
    params = [start.isoformat(), end.isoformat(), start.isoformat(), end.isoformat()]
    if neighborhood:
        where_clause = "WHERE COALESCE(NULLIF(TRIM(p.atendido_em), ''), 'Não informado') = %s"
        params.append(neighborhood)

    params.append(limit)
    rows = query(
        f"""
        WITH prosthetic_need AS (
            SELECT DISTINCT s.patient_id
            FROM triagem_senhas s
            JOIN especialidades esp ON esp.id = s.especialidade_id
            WHERE s.patient_id IS NOT NULL
              AND (esp.codigo = 'P' OR esp.nome ILIKE '%%Prótese%%')
            UNION
            SELECT DISTINCT patient_id
            FROM prosthesis
        ),
        repressed_demand AS (
            SELECT DISTINCT s.patient_id
            FROM triagem_senhas s
            WHERE s.patient_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM consultas c2
                  WHERE c2.patient_id = s.patient_id
                    AND c2.status IN ('Confirmado', 'Realizado')
              )
        )
        SELECT COALESCE(NULLIF(TRIM(p.atendido_em), ''), 'Não informado') as bairro,
               COUNT(DISTINCT p.id) as total_patients,
               COUNT(DISTINCT e.id) as lesion_records,
               COUNT(DISTINCT e.patient_id) FILTER (WHERE e.suspeita_neoplasia = TRUE) as cancer_suspicions,
               COUNT(DISTINCT c.id) FILTER (WHERE c.status = 'Faltou') as no_shows,
               COUNT(DISTINCT c.id) as appointments,
               COUNT(DISTINCT pn.patient_id) as prosthetic_need,
               COUNT(DISTINCT rd.patient_id) as repressed_demand
        FROM patients p
        LEFT JOIN estomatologia e
          ON e.patient_id = p.id
         AND e.data_registro::date BETWEEN %s AND %s
        LEFT JOIN consultas c
          ON c.patient_id = p.id
         AND c.data_consulta::date BETWEEN %s AND %s
        LEFT JOIN prosthetic_need pn ON pn.patient_id = p.id
        LEFT JOIN repressed_demand rd ON rd.patient_id = p.id
        {where_clause}
        GROUP BY bairro
        ORDER BY cancer_suspicions DESC, lesion_records DESC, no_shows DESC, total_patients DESC, bairro ASC
        LIMIT %s
        """,
        tuple(params),
    )

    indicators = []
    for row in rows or []:
        appointments = _as_int(row['appointments'])
        indicators.append({
            **row,
            'total_patients': _as_int(row['total_patients']),
            'lesion_records': _as_int(row['lesion_records']),
            'cancer_suspicions': _as_int(row['cancer_suspicions']),
            'no_shows': _as_int(row['no_shows']),
            'appointments': appointments,
            'prosthetic_need': _as_int(row['prosthetic_need']),
            'repressed_demand': _as_int(row['repressed_demand']),
            'no_show_rate': percentage(row['no_shows'], appointments),
        })
    return indicators


def get_specialty_demand(start, end, neighborhood=None, limit=8):
    neighborhood_clause, neighborhood_params = _neighborhood_filter('p', neighborhood)
    rows = query(
        f"""
        SELECT esp.nome as especialidade,
               COUNT(DISTINCT s.patient_id) as linked_patients,
               COUNT(DISTINCT s.patient_id) FILTER (
                   WHERE NOT EXISTS (
                       SELECT 1
                       FROM consultas c
                       WHERE c.patient_id = s.patient_id
                         AND c.status IN ('Confirmado', 'Realizado')
                   )
               ) as repressed_demand
        FROM triagem_senhas s
        JOIN especialidades esp ON esp.id = s.especialidade_id
        JOIN patients p ON p.id = s.patient_id
        WHERE s.patient_id IS NOT NULL
          AND COALESCE(s.vinculada_em, s.entregue_em, s.criado_em)::date BETWEEN %s AND %s
        {neighborhood_clause}
        GROUP BY esp.nome
        ORDER BY repressed_demand DESC, linked_patients DESC, esp.nome ASC
        LIMIT %s
        """,
        (start.isoformat(), end.isoformat(), *neighborhood_params, limit),
    )
    return rows or []


def get_lesion_locations(start, end, neighborhood=None, limit=8):
    neighborhood_clause, neighborhood_params = _neighborhood_filter('p', neighborhood)
    return query(
        f"""
        SELECT COALESCE(NULLIF(TRIM(e.localizacao_lesao), ''), 'Não informado') as localizacao,
               COUNT(*) as lesion_records,
               COUNT(*) FILTER (WHERE e.suspeita_neoplasia = TRUE) as cancer_suspicions,
               COUNT(*) FILTER (WHERE e.encaminhado_para_biopsia = TRUE) as biopsy_referrals
        FROM estomatologia e
        JOIN patients p ON p.id = e.patient_id
        WHERE e.data_registro::date BETWEEN %s AND %s
        {neighborhood_clause}
        GROUP BY localizacao
        ORDER BY cancer_suspicions DESC, lesion_records DESC, localizacao ASC
        LIMIT %s
        """,
        (start.isoformat(), end.isoformat(), *neighborhood_params, limit),
    ) or []


def get_demographic_profile(start, end, neighborhood=None, today=None):
    today = today or dt.date.today()
    neighborhood_clause, neighborhood_params = _neighborhood_filter('p', neighborhood)
    rows = query(
        f"""
        SELECT data_nascimento, genero, profissao
        FROM patients p
        WHERE p.criado_em::date BETWEEN %s AND %s
        {neighborhood_clause}
        """,
        (start.isoformat(), end.isoformat(), *neighborhood_params),
    ) or []

    age_counts = Counter()
    gender_counts = Counter()
    occupation_counts = Counter()

    for row in rows:
        age_counts[_age_group(row.get('data_nascimento'), today)] += 1
        gender_counts[_clean_label(row.get('genero'))] += 1
        occupation_counts[_clean_label(row.get('profissao'), 'Não informada')] += 1

    total = len(rows)
    return {
        'total': total,
        'age_groups': [
            {'label': label, 'total': age_counts.get(label, 0), 'rate': percentage(age_counts.get(label, 0), total)}
            for label in ('0-12', '13-17', '18-39', '40-59', '60+', 'Não informado')
        ],
        'gender': [
            {'label': label, 'total': count, 'rate': percentage(count, total)}
            for label, count in gender_counts.most_common()
        ],
        'occupations': [
            {'label': label, 'total': count, 'rate': percentage(count, total)}
            for label, count in occupation_counts.most_common(8)
        ],
    }


def get_epidemiology_dashboard(start_date=None, end_date=None, neighborhood=None, today=None):
    today = today or dt.date.today()
    start, end = normalize_period(start_date, end_date, today=today)
    selected_neighborhood = _clean_label(neighborhood, '').strip()

    return {
        'period': {
            'start': start,
            'end': end,
        },
        'filters': {
            'neighborhood': selected_neighborhood,
            'neighborhoods': get_available_neighborhoods(),
        },
        'summary': get_summary(start, end, selected_neighborhood),
        'neighborhoods': get_neighborhood_indicators(start, end, selected_neighborhood),
        'specialties': get_specialty_demand(start, end, selected_neighborhood),
        'lesion_locations': get_lesion_locations(start, end, selected_neighborhood),
        'demographics': get_demographic_profile(start, end, selected_neighborhood, today=today),
    }
