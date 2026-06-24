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
            ('0301010048', 'Consulta de Profissionais de Nível Superior na Atenção Especializada (Exceto Médico)'),
            ('0101020040', 'Ação Coletiva de Exame Bucal com Finalidade Epidemiológica'),
            ('0101020112', 'Ação Coletiva de Prevenção de Câncer Bucal'),
            ('0101020066', 'Aplicação de Selante por Dente'),
            ('0101020074', 'Aplicação Tópica de Flúor por Sessão'),
            ('0101020058', 'Aplicação de Cariostático por Dente'),
            ('0101020104', 'Orientação de Higiene Bucal'),
            ('0101020120', 'Orientação de Higienização de Próteses Dentárias'),
            ('0101020082', 'Evidenciação de Placa Bacteriana'),
            ('0307030040', 'Profilaxia/Remoção de Placa Bacteriana'),
            ('0101020090', 'Selamento Provisório de Cavidade Dentária'),
            ('0307010155', 'Adequação do Comportamento de Crianças'),
            ('0307010147', 'Adequação do Comportamento da Pessoa com Deficiência'),
            ('0307010058', 'Tratamento de Nevralgias Faciais'),
            ('0307010066', 'Tratamento Inicial do Dente Traumatizado'),
            ('0307010023', 'Restauração de Dente Decíduo'),
            ('0307010031', 'Restauração de Dente Permanente Anterior com Resina Composta'),
            ('0307010040', 'Restauração de Dente Permanente Posterior'),
            ('0307010082', 'Restauração de Dente Decíduo Posterior com Resina Composta'),
            ('0307010090', 'Restauração de Dente Decíduo Posterior com Amálgama'),
            ('0307010104', 'Restauração de Dente Decíduo Posterior com Ionômero de Vidro'),
            ('0307010112', 'Restauração de Dente Decíduo Anterior com Resina Composta'),
            ('0307010120', 'Restauração de Dente Permanente Posterior com Resina Composta'),
            ('0307010139', 'Restauração de Dente Permanente Posterior com Amálgama'),
            ('0307010074', 'Tratamento Restaurador Atraumático (TRA/ART)'),
            ('0307020029', 'Curativo de Demora c/ ou s/ Preparo Biomecânico'),
        ],
    },
    {
        'value': 'endodontia',
        'label': 'Endodontia',
        'procedures': [
            ('0307010015', 'Capeamento Pulpar'),
            ('0307020010', 'Acesso à Polpa Dentária e Medicação por Dente'),
            ('0307020070', 'Pulpotomia Dentária'),
            ('0307020061', 'Tratamento Endodôntico de Dente Permanente Unirradicular'),
            ('0307020045', 'Tratamento Endodôntico de Dente Permanente Birradicular'),
            ('0307020053', 'Tratamento Endodôntico de Dente Permanente com Três ou Mais Raízes'),
            ('0307020037', 'Tratamento Endodôntico de Dente Decíduo'),
            ('0307020088', 'Retratamento Endodôntico em Dente Permanente Bi-radicular'),
            ('0307020096', 'Retratamento Endodôntico em Dente Permanente com 3 ou Mais Raízes'),
            ('0307020100', 'Retratamento Endodôntico em Dente Permanente Uni-radicular'),
            ('0307020118', 'Selamento de Perfuração Radicular'),
        ],
    },
    {
        'value': 'periodontia',
        'label': 'Periodontia',
        'procedures': [
            ('0307030059', 'Raspagem, Alisamento e Polimento Supragengivais por Sextante'),
            ('0307030024', 'Raspagem e Alisamento Subgengivais por Sextante'),
            ('0307030032', 'Raspagem Corono-radicular por Sextante'),
            ('0307030075', 'Tratamento de Lesões da Mucosa Oral'),
            ('0307030083', 'Tratamento de Pericoronarite'),
            ('0307030067', 'Tratamento de Gengivite Ulcerativa Necrosante Aguda (GUNA)'),
            ('0414020375', 'Tratamento Cirúrgico Periodontal (por Sextante)'),
            ('0414020154', 'Gengivectomia (por Sextante)'),
            ('0414020162', 'Gengivoplastia (por Sextante)'),
            ('0414020081', 'Enxerto Gengival'),
            ('0414020219', 'Odontosecção/Radilectomia/Tunelização'),
        ],
    },
    {
        'value': 'cirurgia_bucomaxilofacial',
        'label': 'Cirurgia Bucomaxilofacial',
        'procedures': [
            ('0414020120', 'Exodontia de Dente Decíduo'),
            ('0414020138', 'Exodontia de Dente Permanente'),
            ('0414020146', 'Exodontia Múltipla com Alveoloplastia por Sextante'),
            ('0414020278', 'Remoção de Dente Retido, Incluso ou Impactado'),
            ('0414020430', 'Exodontia de Dente Supranumerário'),
            ('0401010031', 'Drenagem de Abscesso'),
            ('0404020054', 'Drenagem de Abscesso da Boca e Anexos'),
            ('0404020089', 'Excisão de Rânula ou Fenômeno de Retenção Salivar'),
            ('0404020577', 'Redução de Fratura Alvéolo-dentária sem Osteossíntese'),
            ('0404020313', 'Retirada de Corpo Estranho dos Ossos da Face'),
            ('0404020488', 'Osteotomia das Fraturas Alvéolo-dentárias'),
            ('0404020623', 'Retirada de Material de Síntese Óssea / Dentária'),
            ('0414010256', 'Excisão de Cálculo de Glândula Salivar'),
            ('0414010345', 'Tratamento Cirúrgico de Fístula Oro-sinusal / Oro-nasal'),
            ('0414010388', 'Tratamento Cirúrgico de Fístula Intra / Extraoral'),
            ('0414010272', 'Tratamento Cirúrgico de Fístula Cutânea de Origem Dentária'),
            ('0414020022', 'Apicectomia com ou sem Obturação Retrógrada'),
            ('0414020030', 'Aprofundamento de Vestíbulo Oral (por Sextante)'),
            ('0414020049', 'Correção de Bridas Musculares'),
            ('0414020057', 'Correção de Irregularidades de Rebordo Alveolar'),
            ('0414020065', 'Correção de Tuberosidade do Maxilar'),
            ('0414020073', 'Curetagem Periapical'),
            ('0414020090', 'Enxerto Ósseo de Área Doadora Intrabucal'),
            ('0414020170', 'Glossorrafia'),
            ('0414020294', 'Remoção de Torus e Exostoses'),
            ('0414020359', 'Tratamento Cirúrgico de Hemorragia Buco-dental'),
            ('0414020367', 'Tratamento Cirúrgico para Tracionamento Dental'),
            ('0414020383', 'Tratamento de Alveolite'),
            ('0414020405', 'Ulotomia/Ulectomia'),
            ('0414020200', 'Marsupialização de Cistos e Pseudocistos'),
            ('0404020097', 'Excisão e Sutura de Lesão na Boca'),
            ('0404020100', 'Excisão em Cunha de Lábio'),
            ('0404020674', 'Reconstrução Parcial do Lábio Traumatizado'),
            ('0404010512', 'Sinusotomia Transmaxilar'),
            ('0401010082', 'Frenectomia / Frenotomia'),
            ('0404020631', 'Retirada de Meios de Fixação Maxilo-mandibular'),
            ('0401010066', 'Excisão e/ou Sutura Simples de Pequenas Lesões / Ferimentos de Pele / Anexos e Mucosa'),
        ],
    },
    {
        'value': 'protese_dentaria',
        'label': 'Prótese Dentária',
        'procedures': [
            ('0307040011', 'Colocação de Placa de Mordida'),
            ('0307040062', 'Manutenção Periódica de Prótese Buco-maxilo-facial'),
            ('0307040070', 'Moldagem Dento-gengival para Prótese Dentária'),
            ('0307040160', 'Instalação de Prótese Dentária'),
            ('0307040089', 'Reembasamento e Conserto de Prótese Dentária'),
            ('0307040143', 'Adaptação de Prótese Dentária'),
            ('0307040151', 'Ajuste Oclusal'),
            ('0307040135', 'Cimentação de Prótese Dentária'),
            ('0701070072', 'Placa Oclusal'),
            ('0701070099', 'Prótese Parcial Mandibular Removível'),
            ('0701070102', 'Prótese Parcial Maxilar Removível'),
            ('0701070129', 'Prótese Total Mandibular'),
            ('0701070137', 'Prótese Total Maxilar'),
            ('0701070145', 'Próteses Coronárias / Intrarradicular Fixas / Adesivas (por Elemento)'),
            ('0307040186', 'Escaneamento Intraoral'),
            ('0307040194', 'Planejamento de Prótese Dentária e Bucomaxilofacial em Fluxo Digital'),
            ('0701070188', 'Prótese Total Maxilar em Fluxo Digital'),
            ('0701070196', 'Prótese Total Mandibular em Fluxo Digital'),
            ('0701070200', 'Prótese Parcial Maxilar Removível em Fluxo Digital'),
            ('0701070218', 'Prótese Parcial Mandibular Removível em Fluxo Digital'),
            ('0701070226', 'Prótese Parcial Removível Temporária em Fluxo Digital'),
            ('0701070234', 'Próteses Coronárias / Intrarradiculares Fixas / Adesivas / Sobre Implante (por Elemento) em Fluxo Digital'),
            ('0701070242', 'Prótese Parcial Fixa, Protocolo e Overdenture Sobre Implante em Fluxo Digital (por Arcada)'),
            ('0701070250', 'Placa Oclusal em Fluxo Digital'),
        ],
    },
    {
        'value': 'alta_complexidade',
        'label': 'Alta Complexidade / Hospitalar / Implantodontia',
        'procedures': [
            ('0414020421', 'Implante Dentário Osteointegrado'),
            ('0701070153', 'Prótese Dentária Sobre Implante'),
            ('0701070056', 'Coroa Provisória'),
            ('0701070048', 'Coroa de Aço e Policarboxilato'),
            ('0414020243', 'Reimplante e Transplante Dental por Elemento'),
            ('0404020615', 'Redução de Luxação Têmporo-Mandibular'),
            ('0404020070', 'Ressecção de Glândula Salivar'),
            ('0414010361', 'Exérese de Cisto Odontogênico e Não Odontogênico'),
            ('0404020038', 'Correção Cirúrgica de Fístula Oronasal / Orosinusal'),
            ('0404020445', 'Contenção de Dentes por Splintagem'),
        ],
    },
    {
        'value': 'diagnostico_estomatologia_radiologia',
        'label': 'Diagnóstico / Estomatologia / Radiologia',
        'procedures': [
            ('0201010526', 'Biópsia dos Tecidos Moles da Boca'),
            ('0201010232', 'Biópsia de Glândula Salivar'),
            ('0201010348', 'Biópsia de Osso do Crânio e da Face'),
            ('0307050017', 'Fotobiomodulação a Laser de Baixa Potência para o Tratamento da Mucosite Oral'),
            ('0204010217', 'Radiografia Interproximal (Bite Wing)'),
            ('0204010225', 'Radiografia Periapical'),
            ('0204010160', 'Radiografia Oclusal'),
            ('0204010179', 'Radiografia Panorâmica'),
            ('0206010044', 'Tomografia Computadorizada de Face / Seios da Face / Articulações Têmporo-Mandibulares'),
            ('0204010209', 'Telerradiografia com Traçado Cefalométrico'),
            ('0204010233', 'Telerradiografia'),
        ],
    },
    {
        'value': 'urgencias_odontologicas',
        'label': 'Urgências Odontológicas',
        'procedures': [
            ('0301060061', 'Atendimento de Urgência em Atenção Especializada'),
        ],
    },
    {
        'value': 'apoio_diagnostico_laboratorial',
        'label': 'Apoio Diagnóstico / Exames Laboratoriais',
        'procedures': [
            ('0202010503', 'Hemograma Completo'),
            ('0202010473', 'Dosagem de Glicose'),
            ('0202010295', 'Dosagem de Colesterol Total'),
            ('0202010643', 'Dosagem de Triglicerídeos'),
            ('0202010317', 'Dosagem de Creatinina'),
            ('0202010694', 'Dosagem de Ureia'),
        ],
    },
]


ODONTOLOGY_SIGTAP_SEED = list({
    code: name.upper()
    for group in SIGTAP_SPECIALTY_GROUPS
    for code, name in group['procedures']
}.items())

SIGTAP_PROCEDURE_INDEX = {
    code: {
        'code': code,
        'name': name,
        'specialty': group['value'],
        'specialty_label': group['label'],
    }
    for group in SIGTAP_SPECIALTY_GROUPS
    for code, name in group['procedures']
}


def normalize_sigtap_code(value):
    digits = re.sub(r'\D', '', value or '')
    return digits if len(digits) == 10 else ''


def format_sigtap_code(value):
    normalized = normalize_sigtap_code(value)
    if not normalized:
        return value or ''
    return (
        f'{normalized[:2]}.{normalized[2:4]}.{normalized[4:6]}.'
        f'{normalized[6:9]}-{normalized[9]}'
    )


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
    configured_codes = tuple(SIGTAP_PROCEDURE_INDEX)
    placeholders = ', '.join(['%s'] * len(configured_codes))
    execute(
        f"""
        UPDATE sigtap_procedures
        SET active = FALSE
        WHERE competence = %s
          AND code NOT IN ({placeholders})
        """,
        (competence, *configured_codes),
    )
    for code, name in ODONTOLOGY_SIGTAP_SEED:
        upsert_sigtap_procedure(code, name, competence=competence, source='seed_odontologia')
    return len(ODONTOLOGY_SIGTAP_SEED)


def search_sigtap_procedures(term='', limit=80, competence=None):
    competence = competence or get_latest_sigtap_competence()
    normalized_term = normalize_sigtap_code(term)
    text_term = (term or '').strip().casefold()
    procedures = []
    for item in SIGTAP_PROCEDURE_INDEX.values():
        if normalized_term and item['code'] != normalized_term:
            continue
        if text_term and not normalized_term and text_term not in item['name'].casefold():
            continue
        groups = split_sigtap_code(item['code'])
        procedures.append({
            **item,
            **groups,
            'competence': competence,
            'source': 'configured_table',
            'active': True,
        })
        if len(procedures) >= limit:
            break
    return procedures


def get_sigtap_procedure(code, competence=None):
    normalized = normalize_sigtap_code(code)
    item = SIGTAP_PROCEDURE_INDEX.get(normalized)
    if not item:
        return None
    groups = split_sigtap_code(normalized)
    return {
        **item,
        **groups,
        'competence': competence or get_latest_sigtap_competence(),
        'source': 'configured_table',
        'active': True,
    }


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

    with open(file_path, 'r', encoding='latin-1') as source:
        for line in source:
            parsed = parse_tb_procedimento_line(line)
            if not parsed:
                continue

            code, name = parsed
            if odontologia_only and code not in SIGTAP_PROCEDURE_INDEX:
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
            for raw_line in source:
                line = raw_line.decode('latin-1')
                parsed = parse_tb_procedimento_line(line)
                if not parsed:
                    continue

                code, name = parsed
                if odontologia_only and code not in SIGTAP_PROCEDURE_INDEX:
                    continue

                upsert_sigtap_procedure(code, name, competence=competence, source='sigtap_txt')
                imported += 1

    return imported


def build_sigtap_options():
    return [
        {
            'code': item['code'],
            'display_code': format_sigtap_code(item['code']),
            'competence': item['competence'],
            'name': item['name'],
            'label': f"{format_sigtap_code(item['code'])} — {item['name']}",
        }
        for item in search_sigtap_procedures(limit=len(SIGTAP_PROCEDURE_INDEX))
    ]


def build_sigtap_specialty_groups(competence=None):
    competence = competence or get_latest_sigtap_competence()
    groups = []
    for group in SIGTAP_SPECIALTY_GROUPS:
        procedures = []
        for code, name in group['procedures']:
            procedures.append({
                'code': code,
                'display_code': format_sigtap_code(code),
                'competence': competence,
                'name': name,
                'label': f"{format_sigtap_code(code)} — {name}",
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
