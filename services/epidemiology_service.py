import datetime as dt
import json
from collections import Counter

from database import query


AGE_GROUPS = ('0-12', '13-17', '18-39', '40-59', '60+', 'Não informado')
DEFAULT_TREATMENT_STATUSES = ('Pendente', 'Planejado', 'Em andamento', 'Concluído', 'Cancelado')


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


def _selected(value):
    return _clean_label(value, '').strip()


def _neighborhood_expression(alias='p'):
    return f"COALESCE(NULLIF(TRIM(split_part({alias}.atendido_em, ' - ', 1)), ''), 'Não informado')"


def _shift_year(value, years):
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, month=2, day=28)


def _age_filter_condition(alias, age_group, today):
    if age_group == 'Não informado':
        return (
            f"""CASE
                WHEN {alias}.data_nascimento IS NULL OR TRIM({alias}.data_nascimento) = '' THEN TRUE
                WHEN {alias}.data_nascimento ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN FALSE
                ELSE TRUE
            END""",
            [],
        )

    ranges = {
        '0-12': (_shift_year(today, -13) + dt.timedelta(days=1), None),
        '13-17': (_shift_year(today, -18) + dt.timedelta(days=1), _shift_year(today, -13)),
        '18-39': (_shift_year(today, -40) + dt.timedelta(days=1), _shift_year(today, -18)),
        '40-59': (_shift_year(today, -60) + dt.timedelta(days=1), _shift_year(today, -40)),
        '60+': (None, _shift_year(today, -60)),
    }
    if age_group not in ranges:
        return '', []

    start_birth, end_birth = ranges[age_group]
    if start_birth and end_birth:
        return (
            f"""CASE
                WHEN {alias}.data_nascimento ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$'
                THEN {alias}.data_nascimento::date BETWEEN %s AND %s
                ELSE FALSE
            END""",
            [start_birth.isoformat(), end_birth.isoformat()],
        )
    if start_birth:
        return (
            f"""CASE
                WHEN {alias}.data_nascimento ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$'
                THEN {alias}.data_nascimento::date >= %s
                ELSE FALSE
            END""",
            [start_birth.isoformat()],
        )
    return (
        f"""CASE
            WHEN {alias}.data_nascimento ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$'
            THEN {alias}.data_nascimento::date <= %s
            ELSE FALSE
        END""",
        [end_birth.isoformat()],
    )


def build_filters(
    neighborhood=None,
    municipality=None,
    specialty=None,
    professional_id=None,
    gender=None,
    age_group=None,
    treatment_status=None,
):
    return {
        'neighborhood': _selected(neighborhood),
        'municipality': _selected(municipality),
        'specialty': _selected(specialty),
        'professional_id': _selected(professional_id),
        'gender': _selected(gender),
        'age_group': _selected(age_group),
        'treatment_status': _selected(treatment_status),
    }


def _coerce_filters(filters=None, neighborhood=None, today=None, **overrides):
    today = today or dt.date.today()
    current = build_filters()
    if filters:
        for key in current:
            current[key] = _selected(filters.get(key))
    if neighborhood is not None:
        current['neighborhood'] = _selected(neighborhood)
    for key, value in overrides.items():
        if key in current and value is not None:
            current[key] = _selected(value)
    return current, today


def _patient_filter_clause(alias='p', filters=None, today=None, prefix='AND'):
    filters, today = _coerce_filters(filters, today=today)
    clauses = []
    params = []

    if filters['neighborhood']:
        clauses.append(f"{_neighborhood_expression(alias)} = %s")
        params.append(filters['neighborhood'])

    if filters['municipality']:
        clauses.append(
            f"""(
                EXISTS (
                    SELECT 1
                    FROM triagem_senhas s_m
                    JOIN municipios m_m ON m_m.id = s_m.municipio_id
                    WHERE s_m.patient_id = {alias}.id
                      AND m_m.nome = %s
                )
                OR {alias}.atendido_em ILIKE %s
            )"""
        )
        params.extend([filters['municipality'], f"% - {filters['municipality']}"])

    if filters['specialty']:
        clauses.append(
            f"""EXISTS (
                SELECT 1
                FROM triagem_senhas s_esp
                JOIN especialidades esp_f ON esp_f.id = s_esp.especialidade_id
                WHERE s_esp.patient_id = {alias}.id
                  AND (
                      s_esp.especialidade_id::text = %s
                      OR esp_f.codigo = %s
                      OR esp_f.nome = %s
                  )
            )"""
        )
        params.extend([filters['specialty'], filters['specialty'], filters['specialty']])

    if filters['professional_id']:
        clauses.append(
            f"""(
                EXISTS (
                    SELECT 1 FROM tratamento_procedimentos tp_prof
                    WHERE tp_prof.patient_id = {alias}.id
                      AND tp_prof.professor_id::text = %s
                )
                OR EXISTS (
                    SELECT 1 FROM consultas c_prof
                    WHERE c_prof.patient_id = {alias}.id
                      AND c_prof.dentista_id::text = %s
                )
                OR EXISTS (
                    SELECT 1 FROM atendimentos a_prof
                    WHERE a_prof.patient_id = {alias}.id
                      AND a_prof.professor_id::text = %s
                )
                OR EXISTS (
                    SELECT 1 FROM exams ex_prof
                    WHERE ex_prof.patient_id = {alias}.id
                      AND ex_prof.professor_id::text = %s
                )
            )"""
        )
        params.extend([filters['professional_id']] * 4)

    if filters['gender']:
        clauses.append(f"COALESCE(NULLIF(TRIM({alias}.genero), ''), 'Não informado') = %s")
        params.append(filters['gender'])

    if filters['age_group']:
        condition, condition_params = _age_filter_condition(alias, filters['age_group'], today)
        if condition:
            clauses.append(condition)
            params.extend(condition_params)

    if filters['treatment_status']:
        clauses.append(
            f"""EXISTS (
                SELECT 1
                FROM tratamento_procedimentos tp_status
                WHERE tp_status.patient_id = {alias}.id
                  AND tp_status.status = %s
            )"""
        )
        params.append(filters['treatment_status'])

    if not clauses:
        return '', []
    return f" {prefix} " + " AND ".join(f"({clause})" for clause in clauses), params


def _neighborhood_filter(alias, neighborhood):
    if not neighborhood:
        return '', []
    return (
        f"AND {_neighborhood_expression(alias)} = %s",
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
    bairro_expr = _neighborhood_expression('p')
    return query(
        f"""
        SELECT DISTINCT {bairro_expr} as bairro
        FROM patients p
        ORDER BY bairro ASC
        """
    )


def get_available_municipalities():
    return query(
        """
        SELECT DISTINCT nome
        FROM (
            SELECT nome
            FROM municipios
            WHERE ativo = 1
            UNION
            SELECT NULLIF(TRIM(split_part(atendido_em, ' - ', 2)), '') as nome
            FROM patients
            WHERE atendido_em LIKE '%% - %%'
        ) municipios_disponiveis
        WHERE nome IS NOT NULL
        ORDER BY nome ASC
        """
    ) or []


def get_available_specialties():
    return query(
        """
        SELECT id, nome, codigo
        FROM especialidades
        WHERE ativo = 1
        ORDER BY nome ASC
        """
    ) or []


def get_available_professionals():
    return query(
        """
        SELECT id, COALESCE(NULLIF(TRIM(full_name), ''), username) as nome, role
        FROM users
        WHERE active = TRUE
          AND role IN (
              'clinica_geral', 'dentista', 'endodontia', 'cirurgia', 'implantes',
              'estomatologia', 'radiologia', 'laboratorio', 'mutirao_movel', 'tsb'
          )
        ORDER BY nome ASC
        """
    ) or []


def get_available_genders():
    rows = query(
        """
        SELECT DISTINCT COALESCE(NULLIF(TRIM(genero), ''), 'Não informado') as genero
        FROM patients
        ORDER BY genero ASC
        """
    ) or []
    rows = [row for row in rows if row.get('genero')]
    return rows or [{'genero': 'Fem'}, {'genero': 'Masc'}, {'genero': 'Não informado'}]


def get_available_treatment_statuses():
    rows = query(
        """
        SELECT DISTINCT COALESCE(NULLIF(TRIM(status), ''), 'Pendente') as status
        FROM tratamento_procedimentos
        ORDER BY status ASC
        """
    ) or []
    rows = [row for row in rows if row.get('status')]
    existing = {row['status'] for row in rows}
    for status in DEFAULT_TREATMENT_STATUSES:
        if status not in existing:
            rows.append({'status': status})
    return rows


def get_summary(start, end, filters=None, neighborhood=None, today=None):
    filters, today = _coerce_filters(filters, neighborhood=neighborhood, today=today)
    patient_clause, patient_params = _patient_filter_clause('p', filters, today=today)

    patients = query(
        f"""
        SELECT COUNT(*) as total
        FROM patients p
        WHERE p.criado_em::date BETWEEN %s AND %s
        {patient_clause}
        """,
        (start.isoformat(), end.isoformat(), *patient_params),
        one=True,
    )

    lesions = query(
        f"""
        SELECT COUNT(*) as lesion_records,
               COUNT(DISTINCT e.patient_id) as lesion_patients,
               COUNT(DISTINCT e.patient_id) FILTER (WHERE e.suspeita_neoplasia = TRUE) as cancer_suspicions,
               COUNT(DISTINCT e.patient_id) FILTER (WHERE e.cancer_confirmed = TRUE) as cancer_confirmed,
               COUNT(*) FILTER (WHERE e.encaminhado_para_biopsia = TRUE) as biopsy_referrals
        FROM estomatologia e
        JOIN patients p ON p.id = e.patient_id
        WHERE e.data_registro::date BETWEEN %s AND %s
        {patient_clause}
        """,
        (start.isoformat(), end.isoformat(), *patient_params),
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
        {patient_clause}
        """,
        (start.isoformat(), end.isoformat(), *patient_params),
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
        {patient_clause}
        """,
        (start.isoformat(), end.isoformat(), *patient_params),
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
        {patient_clause}
        """,
        (start.isoformat(), end.isoformat(), *patient_params),
        one=True,
    )

    patients = patients or {}
    lesions = lesions or {}
    appointments = appointments or {}
    prosthetic_need = prosthetic_need or {}
    repressed_demand = repressed_demand or {}

    total_appointments = _as_int(appointments.get('total'))
    lesion_records = _as_int(lesions.get('lesion_records'))

    return {
        'new_patients': _as_int(patients.get('total')),
        'lesion_records': lesion_records,
        'lesion_patients': _as_int(lesions.get('lesion_patients')),
        'cancer_suspicions': _as_int(lesions.get('cancer_suspicions')),
        'cancer_confirmed': _as_int(lesions.get('cancer_confirmed')),
        'biopsy_referrals': _as_int(lesions.get('biopsy_referrals')),
        'appointments': total_appointments,
        'no_shows': _as_int(appointments.get('no_shows')),
        'done_appointments': _as_int(appointments.get('done')),
        'no_show_rate': percentage(appointments.get('no_shows'), total_appointments),
        'cancer_suspicion_rate': percentage(lesions.get('cancer_suspicions'), lesion_records),
        'prosthetic_need': _as_int(prosthetic_need.get('total')),
        'repressed_demand': _as_int(repressed_demand.get('total')),
    }


def _missing_teeth_from_odontogram(dentes_data):
    if not dentes_data:
        return set()
    if isinstance(dentes_data, str):
        try:
            data = json.loads(dentes_data)
        except (TypeError, ValueError):
            return set()
    else:
        data = dentes_data

    if not isinstance(data, dict):
        return set()

    missing = set()
    for key in ('ausentes', 'ausente', 'extraidos', 'extraídos', 'extracted', 'missing'):
        value = data.get(key)
        if isinstance(value, (list, tuple, set)):
            missing.update(str(item) for item in value if item)

    missing_colors = {'#2563eb', 'blue', 'azul', 'extraido', 'extraído', 'extracted'}
    for tooth, surfaces in data.items():
        if tooth in {'ausentes', 'ausente', 'extraidos', 'extraídos', 'extracted', 'missing', 'observacao'}:
            continue
        if isinstance(surfaces, dict):
            colors = {str(color).strip().lower() for color in surfaces.values()}
            if colors.intersection(missing_colors):
                missing.add(str(tooth))
        elif str(surfaces).strip().lower() in missing_colors:
            missing.add(str(tooth))

    return missing


def _odontogram_rows(start, end, filters=None, today=None):
    filters, today = _coerce_filters(filters, today=today)
    patient_clause, patient_params = _patient_filter_clause('p', filters, today=today)
    bairro_expr = _neighborhood_expression('p')
    return query(
        f"""
        SELECT p.id as patient_id,
               {bairro_expr} as bairro,
               eo.dentes_data
        FROM exam_odontograma eo
        JOIN exams ex ON ex.id = eo.exam_id
        LEFT JOIN anamnesis a ON a.id = ex.anamnesis_id
        JOIN patients p ON p.id = COALESCE(ex.patient_id, a.patient_id)
        WHERE ex.data_criacao::date BETWEEN %s AND %s
        {patient_clause}
        """,
        (start.isoformat(), end.isoformat(), *patient_params),
    ) or []


def get_tooth_loss_metrics(start, end, filters=None, neighborhood=None, today=None):
    filters, today = _coerce_filters(filters, neighborhood=neighborhood, today=today)
    patient_teeth = {}
    for row in _odontogram_rows(start, end, filters, today=today):
        missing = _missing_teeth_from_odontogram(row.get('dentes_data'))
        if missing:
            patient_teeth.setdefault(row['patient_id'], set()).update(missing)

    patients_with_loss = len(patient_teeth)
    missing_teeth = sum(len(teeth) for teeth in patient_teeth.values())
    return {
        'patients_with_tooth_loss': patients_with_loss,
        'missing_teeth': missing_teeth,
        'avg_missing_teeth': round(missing_teeth / patients_with_loss, 1) if patients_with_loss else 0,
    }


def get_tooth_loss_by_neighborhood(start, end, filters=None, neighborhood=None, today=None, limit=None):
    filters, today = _coerce_filters(filters, neighborhood=neighborhood, today=today)
    area_patients = {}
    for row in _odontogram_rows(start, end, filters, today=today):
        missing = _missing_teeth_from_odontogram(row.get('dentes_data'))
        if not missing:
            continue
        bairro = _clean_label(row.get('bairro'))
        area_patients.setdefault(bairro, {}).setdefault(row['patient_id'], set()).update(missing)

    areas = []
    for bairro, patients in area_patients.items():
        missing_teeth = sum(len(teeth) for teeth in patients.values())
        areas.append({
            'bairro': bairro,
            'patients_with_tooth_loss': len(patients),
            'missing_teeth': missing_teeth,
            'avg_missing_teeth': round(missing_teeth / len(patients), 1) if patients else 0,
        })

    areas.sort(key=lambda row: (-row['missing_teeth'], -row['patients_with_tooth_loss'], row['bairro']))
    return areas[:limit] if limit else areas


def _critical_score(row):
    return (
        (_as_int(row.get('cancer_confirmed')) * 60)
        + (_as_int(row.get('cancer_suspicions')) * 35)
        + (_as_int(row.get('lesion_records')) * 10)
        + (_as_int(row.get('repressed_demand')) * 8)
        + (_as_int(row.get('prosthetic_need')) * 6)
        + (_as_int(row.get('patients_with_tooth_loss')) * 5)
        + (_as_int(row.get('no_shows')) * 4)
    )


def _risk_label(score):
    if score >= 80:
        return 'Crítico'
    if score >= 35:
        return 'Atenção'
    return 'Monitorar'


def _critical_reasons(row):
    reasons = []
    if _as_int(row.get('cancer_confirmed')):
        reasons.append('câncer confirmado')
    if _as_int(row.get('cancer_suspicions')):
        reasons.append('suspeita oncológica')
    if _as_int(row.get('lesion_records')):
        reasons.append('lesões bucais')
    if _as_int(row.get('repressed_demand')):
        reasons.append('demanda reprimida')
    if _as_int(row.get('patients_with_tooth_loss')):
        reasons.append('perda dentária')
    if row.get('no_show_rate', 0) >= 25:
        reasons.append('absenteísmo alto')
    return ', '.join(reasons[:3]) or 'monitoramento territorial'


def get_critical_areas(neighborhoods, limit=8):
    areas = []
    for row in neighborhoods:
        if _as_int(row.get('critical_score')) <= 0:
            continue
        areas.append({
            'bairro': row['bairro'],
            'critical_score': row['critical_score'],
            'risk_label': row['risk_label'],
            'reasons': _critical_reasons(row),
        })
    return sorted(areas, key=lambda row: (-row['critical_score'], row['bairro']))[:limit]


def get_neighborhood_indicators(start, end, filters=None, neighborhood=None, limit=12, today=None):
    filters, today = _coerce_filters(filters, neighborhood=neighborhood, today=today)
    where_clause, where_params = _patient_filter_clause('p', filters, today=today, prefix='WHERE')
    bairro_expr = _neighborhood_expression('p')
    params = [start.isoformat(), end.isoformat(), start.isoformat(), end.isoformat()]
    params.extend(where_params)

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
        SELECT {bairro_expr} as bairro,
               COUNT(DISTINCT p.id) as total_patients,
               COUNT(DISTINCT e.id) as lesion_records,
               COUNT(DISTINCT e.patient_id) FILTER (WHERE e.suspeita_neoplasia = TRUE) as cancer_suspicions,
               COUNT(DISTINCT e.patient_id) FILTER (WHERE e.cancer_confirmed = TRUE) as cancer_confirmed,
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

    tooth_loss_map = {
        row['bairro']: row
        for row in get_tooth_loss_by_neighborhood(start, end, filters, today=today)
    }
    indicators = []
    for row in rows or []:
        appointments = _as_int(row.get('appointments'))
        tooth_loss = tooth_loss_map.get(row.get('bairro'), {})
        indicator = {
            **row,
            'total_patients': _as_int(row.get('total_patients')),
            'lesion_records': _as_int(row.get('lesion_records')),
            'cancer_suspicions': _as_int(row.get('cancer_suspicions')),
            'cancer_confirmed': _as_int(row.get('cancer_confirmed')),
            'no_shows': _as_int(row.get('no_shows')),
            'appointments': appointments,
            'prosthetic_need': _as_int(row.get('prosthetic_need')),
            'repressed_demand': _as_int(row.get('repressed_demand')),
            'patients_with_tooth_loss': _as_int(tooth_loss.get('patients_with_tooth_loss')),
            'missing_teeth': _as_int(tooth_loss.get('missing_teeth')),
            'avg_missing_teeth': tooth_loss.get('avg_missing_teeth', 0),
            'no_show_rate': percentage(row.get('no_shows'), appointments),
        }
        score = _critical_score(indicator)
        indicator['critical_score'] = score
        indicator['risk_label'] = _risk_label(score)
        indicators.append(indicator)
    return indicators


def get_specialty_demand(start, end, filters=None, neighborhood=None, limit=8, today=None):
    filters, today = _coerce_filters(filters, neighborhood=neighborhood, today=today)
    patient_clause, patient_params = _patient_filter_clause('p', filters, today=today)
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
        {patient_clause}
        GROUP BY esp.nome
        ORDER BY repressed_demand DESC, linked_patients DESC, esp.nome ASC
        LIMIT %s
        """,
        (start.isoformat(), end.isoformat(), *patient_params, limit),
    )
    return rows or []


def get_lesion_locations(start, end, filters=None, neighborhood=None, limit=8, today=None):
    filters, today = _coerce_filters(filters, neighborhood=neighborhood, today=today)
    patient_clause, patient_params = _patient_filter_clause('p', filters, today=today)
    return query(
        f"""
        SELECT COALESCE(NULLIF(TRIM(e.localizacao_lesao), ''), 'Não informado') as localizacao,
               COUNT(*) as lesion_records,
               COUNT(*) FILTER (WHERE e.suspeita_neoplasia = TRUE) as cancer_suspicions,
               COUNT(*) FILTER (WHERE e.cancer_confirmed = TRUE) as cancer_confirmed,
               COUNT(*) FILTER (WHERE e.encaminhado_para_biopsia = TRUE) as biopsy_referrals
        FROM estomatologia e
        JOIN patients p ON p.id = e.patient_id
        WHERE e.data_registro::date BETWEEN %s AND %s
        {patient_clause}
        GROUP BY localizacao
        ORDER BY cancer_confirmed DESC, cancer_suspicions DESC, lesion_records DESC, localizacao ASC
        LIMIT %s
        """,
        (start.isoformat(), end.isoformat(), *patient_params, limit),
    ) or []


def get_demographic_profile(start, end, neighborhood=None, today=None, filters=None):
    today = today or dt.date.today()
    filters, today = _coerce_filters(filters, neighborhood=neighborhood, today=today)
    patient_clause, patient_params = _patient_filter_clause('p', filters, today=today)
    rows = query(
        f"""
        SELECT data_nascimento, genero, profissao
        FROM patients p
        WHERE p.criado_em::date BETWEEN %s AND %s
        {patient_clause}
        """,
        (start.isoformat(), end.isoformat(), *patient_params),
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
            for label in AGE_GROUPS
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


def get_epidemiology_dashboard(
    start_date=None,
    end_date=None,
    neighborhood=None,
    municipality=None,
    specialty=None,
    professional_id=None,
    gender=None,
    age_group=None,
    treatment_status=None,
    today=None,
):
    today = today or dt.date.today()
    start, end = normalize_period(start_date, end_date, today=today)
    selected_filters = build_filters(
        neighborhood=neighborhood,
        municipality=municipality,
        specialty=specialty,
        professional_id=professional_id,
        gender=gender,
        age_group=age_group,
        treatment_status=treatment_status,
    )
    summary = get_summary(start, end, selected_filters, today=today)
    summary.update(get_tooth_loss_metrics(start, end, selected_filters, today=today))
    neighborhoods = get_neighborhood_indicators(start, end, selected_filters, today=today)

    return {
        'period': {
            'start': start,
            'end': end,
        },
        'filters': {
            **selected_filters,
            'neighborhoods': get_available_neighborhoods(),
            'municipalities': get_available_municipalities(),
            'specialties': get_available_specialties(),
            'professionals': get_available_professionals(),
            'genders': get_available_genders(),
            'age_groups': [{'value': label, 'label': label} for label in AGE_GROUPS],
            'treatment_statuses': get_available_treatment_statuses(),
        },
        'summary': summary,
        'neighborhoods': neighborhoods,
        'critical_areas': get_critical_areas(neighborhoods),
        'tooth_loss_areas': get_tooth_loss_by_neighborhood(start, end, selected_filters, today=today, limit=8),
        'specialties': get_specialty_demand(start, end, selected_filters, today=today),
        'lesion_locations': get_lesion_locations(start, end, selected_filters, today=today),
        'demographics': get_demographic_profile(start, end, today=today, filters=selected_filters),
    }
