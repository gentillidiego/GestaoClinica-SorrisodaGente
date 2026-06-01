import os
import re
import zipfile

from database import execute, query


DEFAULT_COMPETENCE = os.getenv('SIGTAP_DEFAULT_COMPETENCE', '202603')


ODONTOLOGY_SIGTAP_SEED = [
    ('0101020040', 'AÇÃO COLETIVA DE EXAME BUCAL COM FINALIDADE EPIDEMIOLÓGICA'),
    ('0101020066', 'APLICAÇÃO DE SELANTE (POR DENTE)'),
    ('0101020074', 'APLICAÇÃO TÓPICA DE FLÚOR (INDIVIDUAL POR SESSÃO)'),
    ('0101020090', 'SELAMENTO PROVISÓRIO DE CAVIDADE DENTÁRIA'),
    ('0101020104', 'ORIENTAÇÃO DE HIGIENE BUCAL'),
    ('0101020112', 'AÇÃO COLETIVA DE PREVENÇÃO DE CÂNCER BUCAL'),
    ('0201010526', 'BIÓPSIA DOS TECIDOS MOLES DA BOCA'),
    ('0307010015', 'CAPEAMENTO PULPAR'),
    ('0307010031', 'RESTAURAÇÃO DE DENTE PERMANENTE ANTERIOR COM RESINA COMPOSTA'),
    ('0307010074', 'TRATAMENTO RESTAURADOR ATRAUMÁTICO (TRA/ART)'),
    ('0307010082', 'RESTAURAÇÃO DE DENTE DECÍDUO POSTERIOR COM RESINA COMPOSTA'),
    ('0307010104', 'RESTAURAÇÃO DE DENTE DECÍDUO POSTERIOR COM IONÔMERO DE VIDRO'),
    ('0307010120', 'RESTAURAÇÃO DE DENTE PERMANENTE POSTERIOR COM RESINA COMPOSTA'),
    ('0307020010', 'ACESSO À POLPA DENTÁRIA E MEDICAÇÃO (POR DENTE)'),
    ('0307020037', 'TRATAMENTO ENDODÔNTICO DE DENTE DECÍDUO'),
    ('0307020045', 'TRATAMENTO ENDODÔNTICO DE DENTE PERMANENTE BIRRADICULAR'),
    ('0307020053', 'TRATAMENTO ENDODÔNTICO DE DENTE PERMANENTE COM TRÊS OU MAIS RAÍZES'),
    ('0307020061', 'TRATAMENTO ENDODÔNTICO DE DENTE PERMANENTE UNIRRADICULAR'),
    ('0307030024', 'RASPAGEM ALISAMENTO SUBGENGIVAIS (POR SEXTANTE)'),
    ('0307030032', 'RASPAGEM CORONO-RADICULAR (POR SEXTANTE)'),
    ('0307030040', 'PROFILAXIA / REMOÇÃO DA PLACA BACTERIANA'),
    ('0307030059', 'RASPAGEM ALISAMENTO E POLIMENTO SUPRAGENGIVAIS (POR SEXTANTE)'),
    ('0307030075', 'TRATAMENTO DE LESÕES DA MUCOSA ORAL'),
    ('0307030083', 'TRATAMENTO DE PERICORONARITE'),
    ('0307040070', 'MOLDAGEM DENTO-GENGIVAL P/ CONSTRUÇÃO DE PRÓTESE DENTÁRIA'),
    ('0307040089', 'REEMBASAMENTO E CONSERTO DE PRÓTESE DENTÁRIA'),
    ('0414020120', 'EXODONTIA DE DENTE DECÍDUO'),
    ('0414020138', 'EXODONTIA DE DENTE PERMANENTE'),
    ('0414020146', 'EXODONTIA MÚLTIPLA COM ALVEOLOPLASTIA POR SEXTANTE'),
    ('0414020278', 'REMOÇÃO DE DENTE RETIDO (INCLUSO / IMPACTADO)'),
    ('0414020375', 'TRATAMENTO CIRÚRGICO PERIODONTAL (POR SEXTANTE)'),
    ('0414020421', 'IMPLANTE DENTÁRIO OSTEOINTEGRADOR'),
]


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
