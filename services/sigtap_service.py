import os
import re
import zipfile

from database import execute, query


DEFAULT_COMPETENCE = os.getenv('SIGTAP_DEFAULT_COMPETENCE', '202603')


SIGTAP_SPECIALTY_GROUPS = [
    {
        'value': 'atencao_primaria',
        'label': 'Atenção Primária / Clínico Geral',
        'procedures': [
            ('0301010153', 'Primeira Consulta Odontológica Programática'),
            ('0101020040', 'Ação Coletiva de Exame Bucal com Finalidade Epidemiológica'),
            ('0101020112', 'Ação Coletiva de Prevenção de Câncer Bucal'),
            ('0101020066', 'Aplicação de Selante (por dente)'),
            ('0101020074', 'Aplicação Tópica de Flúor (individual por sessão)'),
            ('0101020058', 'Aplicação de Cariostático (por dente)'),
            ('0101020104', 'Orientação de Higiene Bucal'),
            ('0101020082', 'Evidenciação de Placa Bacteriana'),
            ('0307030040', 'Profilaxia / Remoção de Placa Bacteriana'),
            ('0101020090', 'Selamento Provisório de Cavidade Dentária'),
            ('0307010023', 'Restauração de Dente Decíduo'),
            ('0307010031', 'Restauração de Dente Permanente Anterior'),
            ('0307010040', 'Restauração de Dente Permanente Posterior'),
            ('0307010074', 'Tratamento Restaurador Atraumático (TRA/ART)'),
        ],
    },
    {
        'value': 'endodontia',
        'label': 'Endodontia',
        'procedures': [
            ('0307010015', 'Capeamento Pulpar'),
            ('0307020010', 'Acesso à Polpa Dentária e Medicação (por dente)'),
            ('0307020070', 'Pulpotomia Dentária'),
            ('0307020061', 'Tratamento Endodôntico de Dente Permanente Unirradicular'),
            ('0307020045', 'Tratamento Endodôntico de Dente Permanente Birradicular'),
            ('0307020053', 'Tratamento Endodôntico de Dente Permanente com 3 ou mais Raízes'),
            ('0307020037', 'Tratamento Endodôntico de Dente Decíduo'),
        ],
    },
    {
        'value': 'periodontia',
        'label': 'Periodontia',
        'procedures': [
            ('0307030059', 'Raspagem Alisamento e Polimento Supragengivais (por sextante)'),
            ('0307030024', 'Raspagem Alisamento Subgengivais (por sextante)'),
            ('0307030032', 'Raspagem Corono-radicular (por sextante)'),
            ('0414020081', 'Enxerto Gengival'),
            ('0414020219', 'Odontosecção / Radilectomia / Tunelização'),
        ],
    },
    {
        'value': 'cirurgia_bucomaxilofacial',
        'label': 'Cirurgia Bucomaxilofacial',
        'procedures': [
            ('0414020120', 'Exodontia de Dente Decíduo'),
            ('0414020138', 'Exodontia de Dente Permanente'),
            ('0414020146', 'Exodontia Múltipla com Alveoloplastia por Sextante'),
            ('0414020278', 'Remoção de Dente Retido (Incluso / Impactado)'),
            ('0414020430', 'Exodontia de Dente Supranumerário'),
            ('0401010031', 'Drenagem de Abscesso'),
            ('0414020405', 'Ulotomia / Ulectomia'),
            ('0401010082', 'Frenectomia'),
            ('0414020022', 'Apicectomia c/ ou s/ Obturação Retrógrada'),
        ],
    },
    {
        'value': 'protese_dentaria',
        'label': 'Prótese Dentária',
        'procedures': [
            ('0307040070', 'Moldagem Dento-gengival p/ Construção de Prótese Dentária'),
            ('0307040160', 'Instalação de Prótese Dentária'),
            ('0307040089', 'Reembasamento e Conserto de Prótese Dentária'),
            ('0307040143', 'Adaptação de Prótese Dentária'),
            ('0701070099', 'Prótese Parcial Mandibular Removível'),
            ('0701070102', 'Prótese Parcial Maxilar Removível'),
            ('0701070129', 'Prótese Total Mandibular'),
            ('0701070137', 'Prótese Total Maxilar'),
        ],
    },
    {
        'value': 'alta_complexidade',
        'label': 'Alta Complexidade / Hospitalar',
        'procedures': [
            ('0414020421', 'Implante Dentário Osteointegrador'),
            ('0414020243', 'Reimplante e Transplante Dental (por elemento)'),
            ('0404020615', 'Redução de Luxação Têmporo-Mandibular'),
            ('0404020070', 'Ressecção de Glândula Salivar'),
            ('0414010361', 'Exérese de Cisto Odontogênico e Não-Odontogênico'),
            ('0414010256', 'Tratamento Cirúrgico de Fístula Oronasal/Orosinusal'),
            ('0404020445', 'Contenção de Dentes por Splintagem (Traumatologia)'),
        ],
    },
    {
        'value': 'diagnostico_estomatologia_radiologia',
        'label': 'Diagnóstico / Estomatologia / Radiologia',
        'procedures': [
            ('0201010526', 'Biópsia dos Tecidos Moles da Boca'),
            ('0204010187', 'Radiografia Periapical / Interproximal (Bite-Wing)'),
            ('0204010160', 'Radiografia Oclusal'),
            ('0204010217', 'Radiografia Panorâmica de Mandíbula/Maxila (Ortopantomografia)'),
            ('0204010225', 'Telerradiografia'),
        ],
    },
]


ODONTOLOGY_SIGTAP_SEED = list({
    code: name.upper()
    for group in SIGTAP_SPECIALTY_GROUPS
    for code, name in group['procedures']
}.items())


def normalize_sigtap_code(value):
    digits = re.sub(r'\D', '', value or '')
    return digits if len(digits) == 10 else ''


def split_sigtap_code(code):
    normalized = normalize_sigtap_code(code)
    if not normalized:
        return {'group_code': None, 'subgroup_code': None, 'form_code': None}
    return {
        'group_code': normalized[:2],
        'subgroup_code': normalized[2:4],
        'form_code': normalized[4:6],
    }


def upsert_sigtap_procedure(code, name, competence=None, source='manual', active=True):
    normalized = normalize_sigtap_code(code)
    if not normalized:
        raise ValueError('Código SIGTAP inválido. Informe 10 dígitos.')

    competence = competence or DEFAULT_COMPETENCE
    groups = split_sigtap_code(normalized)
    execute(
        """
        INSERT INTO sigtap_procedures (
            code, competence, name, group_code, subgroup_code, form_code, source, active, imported_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (code, competence)
        DO UPDATE SET
            name = EXCLUDED.name,
            group_code = EXCLUDED.group_code,
            subgroup_code = EXCLUDED.subgroup_code,
            form_code = EXCLUDED.form_code,
            source = EXCLUDED.source,
            active = EXCLUDED.active,
            imported_at = NOW()
        """,
        (
            normalized,
            competence,
            name.strip().upper(),
            groups['group_code'],
            groups['subgroup_code'],
            groups['form_code'],
            source,
            active,
        )
    )
    return normalized


def seed_odontology_sigtap(competence=None):
    competence = competence or DEFAULT_COMPETENCE
    for code, name in ODONTOLOGY_SIGTAP_SEED:
        upsert_sigtap_procedure(code, name, competence=competence, source='seed_odontologia')
    return len(ODONTOLOGY_SIGTAP_SEED)


def search_sigtap_procedures(term='', limit=80, competence=None):
    competence = competence or get_latest_sigtap_competence()
    params = [competence]
    sql = """
        SELECT *
        FROM sigtap_procedures
        WHERE active = TRUE
          AND competence = %s
    """

    if term:
        normalized_code = normalize_sigtap_code(term)
        if normalized_code:
            sql += " AND code = %s"
            params.append(normalized_code)
        else:
            sql += " AND name ILIKE %s"
            params.append(f"%{term}%")

    sql += " ORDER BY name ASC LIMIT %s"
    params.append(limit)
    return query(sql, tuple(params))


def get_sigtap_procedure(code, competence=None):
    normalized = normalize_sigtap_code(code)
    if not normalized:
        return None

    if competence:
        return query(
            """
            SELECT *
            FROM sigtap_procedures
            WHERE code = %s AND competence = %s AND active = TRUE
            """,
            (normalized, competence),
            one=True,
        )

    return query(
        """
        SELECT *
        FROM sigtap_procedures
        WHERE code = %s AND active = TRUE
        ORDER BY competence DESC
        LIMIT 1
        """,
        (normalized,),
        one=True,
    )


def get_latest_sigtap_competence():
    row = query(
        """
        SELECT competence
        FROM sigtap_procedures
        WHERE active = TRUE
        ORDER BY competence DESC
        LIMIT 1
        """,
        one=True,
    )
    return row['competence'] if row else DEFAULT_COMPETENCE


def get_sigtap_summary():
    rows = query(
        """
        SELECT competence,
               COUNT(*) as total,
               COUNT(*) FILTER (WHERE source = 'seed_odontologia') as seed_total,
               COUNT(*) FILTER (WHERE source = 'sigtap_txt') as official_total
        FROM sigtap_procedures
        WHERE active = TRUE
        GROUP BY competence
        ORDER BY competence DESC
        LIMIT 6
        """
    )
    latest = rows[0] if rows else {
        'competence': DEFAULT_COMPETENCE,
        'total': 0,
        'seed_total': 0,
        'official_total': 0,
    }
    return {
        'latest': latest,
        'competences': rows,
    }


def parse_tb_procedimento_line(line):
    raw = line.rstrip('\n\r')
    code = normalize_sigtap_code(raw[:10])
    name = raw[10:260].strip()
    if not code or not name:
        return None
    return code, name


def import_tb_procedimento_file(file_path, competence, odontologia_only=True):
    imported = 0
    accepted_prefixes = ('010102', '020101', '0307', '041402', '041401', '040402')

    with open(file_path, 'r', encoding='latin-1') as source:
        for line in source:
            parsed = parse_tb_procedimento_line(line)
            if not parsed:
                continue

            code, name = parsed
            if odontologia_only and not code.startswith(accepted_prefixes):
                continue

            upsert_sigtap_procedure(code, name, competence=competence, source='sigtap_txt')
            imported += 1

    return imported


def import_sigtap_zip(zip_path, competence, odontologia_only=True):
    with zipfile.ZipFile(zip_path) as archive:
        candidates = [
            name for name in archive.namelist()
            if name.upper().endswith('TB_PROCEDIMENTO.TXT')
        ]
        if not candidates:
            raise ValueError('Arquivo TB_PROCEDIMENTO.TXT não encontrado no ZIP SIGTAP.')

        with archive.open(candidates[0]) as source:
            imported = 0
            accepted_prefixes = ('010102', '020101', '0307', '041402', '041401', '040402')
            for raw_line in source:
                line = raw_line.decode('latin-1')
                parsed = parse_tb_procedimento_line(line)
                if not parsed:
                    continue

                code, name = parsed
                if odontologia_only and not code.startswith(accepted_prefixes):
                    continue

                upsert_sigtap_procedure(code, name, competence=competence, source='sigtap_txt')
                imported += 1

    return imported


def build_sigtap_options():
    return [
        {
            'code': item['code'],
            'competence': item['competence'],
            'name': item['name'],
            'label': f"{item['code']} - {item['name']}",
        }
        for item in search_sigtap_procedures(limit=120)
    ]


def build_sigtap_specialty_groups(competence=None):
    competence = competence or get_latest_sigtap_competence()
    groups = []
    for group in SIGTAP_SPECIALTY_GROUPS:
        procedures = []
        for code, name in group['procedures']:
            sigtap = get_sigtap_procedure(code, competence) or get_sigtap_procedure(code)
            procedures.append({
                'code': code,
                'competence': sigtap['competence'] if sigtap else competence,
                'name': sigtap['name'] if sigtap else name.upper(),
                'label': f"{code} - {(sigtap['name'] if sigtap else name.upper())}",
            })
        groups.append({
            'value': group['value'],
            'label': group['label'],
            'procedures': procedures,
        })
    return groups


def get_sigtap_specialty_label(value):
    for group in SIGTAP_SPECIALTY_GROUPS:
        if group['value'] == value:
            return group['label']
    return ''


def is_sigtap_code_allowed_for_specialty(specialty, code):
    normalized = normalize_sigtap_code(code)
    if not specialty or not normalized:
        return True
    for group in SIGTAP_SPECIALTY_GROUPS:
        if group['value'] != specialty:
            continue
        return any(procedure_code == normalized for procedure_code, _ in group['procedures'])
    return False
