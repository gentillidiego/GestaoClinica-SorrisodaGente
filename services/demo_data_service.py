import datetime as dt
import json
import random

from werkzeug.security import generate_password_hash

from constants import Role
from database import execute, query
from services.sigtap_service import get_sigtap_procedure, seed_odontology_sigtap


DEMO_SIGNATURE = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

FIRST_NAMES_F = [
    'Ana', 'Maria', 'Joana', 'Luciana', 'Patricia', 'Rafaela', 'Helena',
    'Sofia', 'Marina', 'Cecilia', 'Beatriz', 'Aline', 'Vitoria', 'Clara',
]
FIRST_NAMES_M = [
    'Jose', 'Antonio', 'Carlos', 'Joao', 'Pedro', 'Rafael', 'Lucas',
    'Miguel', 'Davi', 'Gustavo', 'Marcos', 'Fernando', 'Samuel', 'Heitor',
]
LAST_NAMES = [
    'Silva', 'Santos', 'Oliveira', 'Souza', 'Pereira', 'Lima', 'Costa',
    'Ferreira', 'Almeida', 'Nascimento', 'Melo', 'Barbosa', 'Cavalcante',
]
OCCUPATIONS = [
    'Agricultor', 'Professora', 'Autonomo', 'Aposentado', 'Comerciante',
    'Estudante', 'Pescador', 'Cuidadora', 'Motorista', 'Auxiliar de Servicos',
]
NEIGHBORHOODS = [
    'Centro', 'Benedito Bentes', 'Tabuleiro', 'Jacintinho', 'Ponta Grossa',
    'Vergel', 'Cidade Universitaria', 'Santa Lucia', 'Primavera', 'Canafistula',
    'Baixao', 'Nova Esperanca', 'Serraria', 'Pajucara', 'Farol',
]

CLINICAL_PROFILES = [
    {
        'key': 'idoso_protese',
        'label': 'Idoso com necessidade protetica',
        'age': 68,
        'complaint': 'Dificuldade mastigatoria e perda de dentes posteriores.',
        'conditions': {'sofre_doenca': 'Sim', 'detail': 'Hipertensao controlada', 'pressure': '140x90'},
        'prosthesis': True,
        'lesion': False,
        'specialty': 'P',
        'procedures': [('0307040070', 'Moldagem para protese total'), ('0307030040', 'Profilaxia inicial')],
    },
    {
        'key': 'diabetico_periodontal',
        'label': 'Adulto diabetico com doenca periodontal',
        'age': 54,
        'complaint': 'Sangramento gengival e mobilidade em dentes inferiores.',
        'conditions': {'sofre_doenca': 'Sim', 'detail': 'Diabetes tipo 2', 'pressure': '130x80'},
        'prosthesis': False,
        'lesion': False,
        'specialty': 'PER',
        'procedures': [('0307030024', 'Raspagem subgengival por sextante'), ('0307030059', 'Raspagem e polimento supragengival')],
    },
    {
        'key': 'crianca_carie',
        'label': 'Crianca com carie ativa',
        'age': 9,
        'complaint': 'Dor ao mastigar e manchas escuras em molares deciduos.',
        'conditions': {'sofre_doenca': 'Nao', 'detail': '', 'pressure': '100x60'},
        'prosthesis': False,
        'lesion': False,
        'specialty': 'ODP',
        'procedures': [('0307010082', 'Restauracao em dente deciduo posterior'), ('0101020074', 'Aplicacao topica de fluor')],
    },
    {
        'key': 'lesao_suspeita',
        'label': 'Tabagista com lesao suspeita',
        'age': 62,
        'complaint': 'Ferida em borda lateral de lingua ha mais de 20 dias.',
        'conditions': {'sofre_doenca': 'Sim', 'detail': 'Tabagismo cronico', 'pressure': '150x90'},
        'prosthesis': False,
        'lesion': True,
        'specialty': 'CTBMF',
        'procedures': [('0201010526', 'Biopsia de tecidos moles da boca'), ('0307030075', 'Tratamento de lesao de mucosa oral')],
    },
    {
        'key': 'endodontia_dor',
        'label': 'Adulto com dor endodontica',
        'age': 34,
        'complaint': 'Dor espontanea no elemento 36, piora durante a noite.',
        'conditions': {'sofre_doenca': 'Nao', 'detail': '', 'pressure': '120x80'},
        'prosthesis': False,
        'lesion': False,
        'specialty': 'END',
        'procedures': [('0307020061', 'Tratamento endodontico unirradicular'), ('0307010120', 'Restauracao posterior com resina')],
    },
    {
        'key': 'implante_reabilitacao',
        'label': 'Reabilitacao com implante',
        'age': 47,
        'complaint': 'Ausencia dentaria em regiao posterior e queixa estetica.',
        'conditions': {'sofre_doenca': 'Nao', 'detail': '', 'pressure': '120x80'},
        'prosthesis': True,
        'lesion': False,
        'specialty': 'I',
        'procedures': [('0414020421', 'Implante dentario osteointegrador'), ('0307040070', 'Moldagem para reabilitacao')],
    },
    {
        'key': 'gestante_preventivo',
        'label': 'Gestante em cuidado preventivo',
        'age': 28,
        'complaint': 'Sangramento gengival durante escovacao.',
        'conditions': {'sofre_doenca': 'Nao', 'detail': 'Gestante 24 semanas', 'pressure': '110x70', 'gestante': 'Sim'},
        'prosthesis': False,
        'lesion': False,
        'specialty': 'D',
        'procedures': [('0307030040', 'Profilaxia e orientacao preventiva'), ('0101020104', 'Orientacao de higiene bucal')],
    },
    {
        'key': 'idoso_oncologico',
        'label': 'Paciente oncologico em acompanhamento',
        'age': 71,
        'complaint': 'Boca seca e necessidade de avaliacao antes de tratamento medico.',
        'conditions': {'sofre_doenca': 'Sim', 'detail': 'Historico oncologico em acompanhamento', 'pressure': '130x80', 'cancer': 'Sim'},
        'prosthesis': False,
        'lesion': True,
        'specialty': 'CTBMF',
        'procedures': [('0307030075', 'Tratamento de lesao de mucosa oral'), ('0201010526', 'Biopsia de tecidos moles')],
    },
]


def generate_valid_cpf(index):
    base = f"{100000000 + index:09d}"
    numbers = [int(digit) for digit in base]

    first = sum(value * weight for value, weight in zip(numbers, range(10, 1, -1)))
    first_digit = 11 - (first % 11)
    first_digit = 0 if first_digit >= 10 else first_digit

    second_numbers = numbers + [first_digit]
    second = sum(value * weight for value, weight in zip(second_numbers, range(11, 1, -1)))
    second_digit = 11 - (second % 11)
    second_digit = 0 if second_digit >= 10 else second_digit

    cpf = base + str(first_digit) + str(second_digit)
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


def generate_cns(index):
    return f"7{90000000000000 + index:014d}"[:15]


def clamp_demo_count(value):
    try:
        count = int(value)
    except (TypeError, ValueError):
        return 1
    return max(1, min(count, 100))


def _birthdate_for_age(age, offset):
    today = dt.date.today()
    month = (offset % 12) + 1
    day = (offset % 25) + 1
    return dt.date(today.year - age, month, day).isoformat()


def _created_at_for(index):
    today = dt.date.today()
    max_offset = max(today.day - 1, 0)
    return today - dt.timedelta(days=index % (max_offset + 1))


def _select_demo_profile(index):
    return CLINICAL_PROFILES[index % len(CLINICAL_PROFILES)]


def _select_municipality(index):
    municipios = query("SELECT id, nome, codigo FROM municipios WHERE ativo = 1 ORDER BY nome")
    if not municipios:
        return {'id': None, 'nome': 'Maceio', 'codigo': 'MCZ'}
    return municipios[index % len(municipios)]


def _select_specialty(code):
    specialty = query("SELECT id, nome, codigo FROM especialidades WHERE codigo = %s", (code,), one=True)
    if specialty:
        return specialty
    return query("SELECT id, nome, codigo FROM especialidades ORDER BY id LIMIT 1", one=True)


def _ensure_demo_professional():
    professional = query("SELECT id FROM users WHERE username = 'demo.dentista' LIMIT 1", one=True)
    if professional:
        return professional['id']

    return execute(
        """
        INSERT INTO users (
            username, password, role, full_name, cro, cro_uf, cns, cbo, cnes, ine, active
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
        RETURNING id
        """,
        (
            'demo.dentista',
            generate_password_hash('Demo@2026!'),
            Role.DENTISTA,
            'Dra. Marina Demo',
            '12345',
            'AL',
            '700000000000001',
            '223208',
            '2000001',
            '0000000001',
        )
    )


def _sigtap(code):
    return get_sigtap_procedure(code) or {'code': code, 'competence': None, 'name': None}


def _create_triage_ticket(patient_id, municipality, specialty, index, created_by, created_at):
    if not municipality.get('id') or not specialty:
        return None

    action_id = execute(
        """
        INSERT INTO triagem_acoes (municipio_id, data_acao, local, observacoes, status, created_by, criado_em)
        VALUES (%s, %s, %s, %s, 'Aberta', %s, %s)
        RETURNING id
        """,
        (
            municipality['id'],
            created_at,
            f"Acao demo - {municipality['nome']}",
            'Registro ficticio para demonstracao epidemiologica.',
            created_by,
            created_at,
        )
    )
    ticket_code = f"DEM-{municipality['codigo']}-{specialty['codigo']}-{index:04d}"
    execute(
        """
        INSERT INTO triagem_senhas (
            triagem_acao_id, municipio_id, especialidade_id, numero, codigo, status,
            patient_id, entregue_em, vinculada_em, criado_em
        )
        VALUES (%s, %s, %s, %s, %s, 'Vinculada', %s, %s, %s, %s)
        """,
        (
            action_id,
            municipality['id'],
            specialty['id'],
            800000 + index,
            ticket_code,
            patient_id,
            created_at,
            created_at,
            created_at,
        )
    )
    return ticket_code


def _create_anamnesis(patient_id, profile, created_at):
    conditions = profile['conditions']
    return execute(
        """
        INSERT INTO anamnesis (
            patient_id, queixa_principal, historia_doenca_atual,
            sofre_doenca, sofre_doenca_explica, tratamento_medico, tratamento_medico_explica,
            tomando_medicamento, tomando_medicamento_explica, tem_alergia, tem_alergia_explica,
            pressao_arterial, desmaios_convulsoes, tem_cancer, radioterapia_quimioterapia,
            falta_ar, fez_cirurgia, fez_cirurgia_explica, sangramento_cortar, cicatrizacao,
            foi_hospitalizado, foi_hospitalizado_explica, alergia_medicamento_alimento,
            gestante, gestante_semanas, problemas_saude_ja_teve, reacao_anestesia,
            reacao_anestesia_explica, ultimo_tratamento_dentario, dor_dentes_gengiva,
            gengiva_sangra, fio_dental, dores_estalos_maxilar, range_dentes,
            antecedentes_familiares, causas_obitos_familiares, fuma, fuma_quantidade,
            ingere_alcool, ingere_alcool_frequencia, exercicios_fisicos,
            exercicios_fisicos_frequencia, assinatura_base64, data_anamnese
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            patient_id,
            profile['complaint'],
            f"Evolucao relatada compativel com perfil demo: {profile['label']}.",
            conditions.get('sofre_doenca', 'Nao'),
            conditions.get('detail', ''),
            'Sim' if conditions.get('detail') else 'Nao',
            conditions.get('detail', ''),
            'Sim' if 'Hipertensao' in conditions.get('detail', '') or 'Diabetes' in conditions.get('detail', '') else 'Nao',
            'Losartana / Metformina conforme perfil clinico ficticio.' if conditions.get('detail') else '',
            'Nao',
            '',
            conditions.get('pressure', '120x80'),
            'Nao',
            conditions.get('cancer', 'Nao'),
            'Nao',
            'Nao',
            'Nao',
            '',
            'Nao',
            'Normal',
            'Nao',
            '',
            'Nao',
            conditions.get('gestante', 'Nao'),
            '24' if conditions.get('gestante') == 'Sim' else '',
            conditions.get('detail', ''),
            'Nao',
            '',
            'Ha mais de 2 anos',
            'Sim' if 'dor' in profile['key'] or 'carie' in profile['key'] else 'Nao',
            'Sim' if 'periodontal' in profile['key'] or conditions.get('gestante') == 'Sim' else 'Nao',
            'As vezes',
            'Nao',
            'Nao',
            'Hipertensao em familiares de primeiro grau.',
            'Sem relato relevante.',
            'Sim' if profile['lesion'] else 'Nao',
            '10 cigarros/dia' if profile['lesion'] else '',
            'Nao',
            '',
            'Nao',
            '',
            DEMO_SIGNATURE,
            created_at,
        )
    )


def _create_exams(patient_id, anamnesis_id, profile, professional_id, created_at):
    fisico_id = execute(
        "INSERT INTO exams (anamnesis_id, patient_id, tipo, resumo_clinico, professor_id, data_validacao, data_criacao) VALUES (%s, %s, 'fisico', %s, %s, %s, %s) RETURNING id",
        (anamnesis_id, patient_id, f"Exame fisico demo - {profile['label']}", professional_id, created_at, created_at)
    )
    execute(
        """
        INSERT INTO exam_fisico (
            exam_id, estado_geral, peso_referido, altura, pulso, freq_cardiaca, pa_x,
            lesao_presenca, exame_extrabucal, exame_intrabucal, hipoteses_diagnosticas,
            imagem_panoramica, imagem_resultado, hema_hemograma, hema_glicemia,
            histo_incisional, diagnostico_definitivo
        )
        VALUES (%s, 'Bom', %s, %s, '78 bpm', '78 bpm', %s, %s, %s, %s, %s, 1, %s, 1, %s, %s, %s)
        """,
        (
            fisico_id,
            '72 kg',
            '1,68 m',
            profile['conditions'].get('pressure', '120x80'),
            'Sim' if profile['lesion'] else 'Nao',
            'Sem assimetrias relevantes.',
            'Mucosa avaliada; alteracao descrita em estomatologia.' if profile['lesion'] else 'Sem lesoes aparentes.',
            'Lesao potencialmente maligna' if profile['lesion'] else 'Condicao odontologica compativel com queixa.',
            'Solicitada/avaliada panoramica para planejamento.',
            1 if 'diabetico' in profile['key'] else 0,
            1 if profile['lesion'] else 0,
            'Acompanhamento clinico conforme plano demo.',
        )
    )

    odontograma = {
        'ausentes': ['36', '46'] if profile['prosthesis'] else [],
        'carie': ['55', '65'] if 'crianca' in profile['key'] else ['36'] if 'endodontia' in profile['key'] else [],
        'restaurados': ['16', '26'],
        'observacao': profile['label'],
    }
    odontograma_id = execute(
        "INSERT INTO exams (anamnesis_id, patient_id, tipo, resumo_clinico, professor_id, data_validacao, data_criacao) VALUES (%s, %s, 'odontograma', %s, %s, %s, %s) RETURNING id",
        (anamnesis_id, patient_id, 'Odontograma demo com necessidades planejadas.', professional_id, created_at, created_at)
    )
    execute(
        "INSERT INTO exam_odontograma (exam_id, dentes_data, notas_dentes, observacoes) VALUES (%s, %s, %s, %s)",
        (odontograma_id, json.dumps(odontograma), 'Dentes marcados para demonstracao.', profile['complaint'])
    )

    periograma_id = execute(
        "INSERT INTO exams (anamnesis_id, patient_id, tipo, resumo_clinico, professor_id, data_validacao, data_criacao) VALUES (%s, %s, 'periograma', %s, %s, %s, %s) RETURNING id",
        (anamnesis_id, patient_id, 'Periograma demo.', professional_id, created_at, created_at)
    )
    periodontal = {
        'sangramento': profile['key'] in {'diabetico_periodontal', 'gestante_preventivo'},
        'bolsas_mm': 5 if 'periodontal' in profile['key'] else 3,
        'mobilidade': profile['key'] == 'diabetico_periodontal',
    }
    execute(
        "INSERT INTO exam_periograma (exam_id, fase, medicoes_data, diagnostico) VALUES (%s, %s, %s, %s)",
        (
            periograma_id,
            'Inicial',
            json.dumps(periodontal),
            'Periodontite estagio II demo.' if periodontal['bolsas_mm'] >= 5 else 'Gengivite leve / controle preventivo demo.',
        )
    )


def _create_treatments(patient_id, profile, professional_id, created_at):
    execute(
        """
        INSERT INTO planos_tratamento (patient_id, descricao, custo_estimado, status, criado_em)
        VALUES (%s, %s, %s, 'Aprovado', %s)
        """,
        (patient_id, f"Plano demo - {profile['label']}", 350 + (len(profile['procedures']) * 180), created_at)
    )

    for position, (code, description) in enumerate(profile['procedures']):
        sigtap = _sigtap(code)
        status = 'Concluído' if position == 0 else 'Pendente'
        execute(
            """
            INSERT INTO tratamento_procedimentos (
                patient_id, data_sessao, dente, descricao, sigtap_code, sigtap_competence,
                sigtap_name, professor_id, status, esus_export_status, criado_em
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                patient_id,
                created_at.isoformat(),
                ['36', '46', '11', '26'][position % 4],
                description,
                sigtap['code'],
                sigtap.get('competence'),
                sigtap.get('name') or description.upper(),
                professional_id if status == 'Concluído' else None,
                status,
                'pending' if status == 'Concluído' else 'pending',
                created_at,
            )
        )

    execute(
        """
        INSERT INTO atendimentos (patient_id, data, observacoes, assinatura_paciente_base64, professor_id, status, created_by)
        VALUES (%s, %s, %s, %s, %s, 'Concluído', %s)
        """,
        (
            patient_id,
            created_at,
            f"Evolucao demo: procedimento inicial realizado. Perfil: {profile['label']}.",
            DEMO_SIGNATURE,
            professional_id,
            professional_id,
        )
    )


def _create_appointments(patient_id, professional_id, created_at, index):
    statuses = ['Realizado', 'Realizado', 'Confirmado', 'Faltou', 'Pendente']
    for offset in range(2):
        status = statuses[(index + offset) % len(statuses)]
        execute(
            """
            INSERT INTO consultas (patient_id, dentista_id, data_consulta, duracao_minutos, status, observacoes, created_by, criado_em)
            VALUES (%s, %s, %s, 30, %s, %s, %s, %s)
            """,
            (
                patient_id,
                professional_id,
                created_at + dt.timedelta(days=offset * 7),
                status,
                f"Consulta demo {status.lower()}",
                professional_id,
                created_at,
            )
        )


def _create_stomatology(patient_id, profile, professional_id, created_at):
    if not profile['lesion']:
        return
    est_id = execute(
        """
        INSERT INTO estomatologia (
            patient_id, dentista_id, data_registro, localizacao_lesao, tamanho_lesao,
            caracteristicas_lesao, habitos_paciente, tempo_evolucao, hipotese_diagnostica,
            suspeita_neoplasia, conduta_clinica, encaminhado_para_biopsia
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, %s, TRUE)
        RETURNING id
        """,
        (
            patient_id,
            professional_id,
            created_at,
            'Borda lateral de lingua',
            '1,2 cm',
            'Ulcera endurecida com bordas elevadas',
            'Tabagismo relatado',
            'Mais de 20 dias',
            'Lesao suspeita - descartar neoplasia',
            'Encaminhamento prioritario para biopsia e acompanhamento estomatologico.',
        )
    )
    execute(
        """
        INSERT INTO estomatologia_fotos (estomatologia_id, filename, file_path, legenda, data_upload)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (est_id, f'demo_lesao_{patient_id}.jpg', f'uploads/demo/demo_lesao_{patient_id}.jpg', 'Foto demo de lesao suspeita', created_at)
    )


def _create_prosthesis(patient_id, profile, professional_id, created_at):
    if not profile['prosthesis']:
        return
    prosthesis_id = execute(
        """
        INSERT INTO prosthesis (patient_id, created_by, aluno_responsavel_id, data, descricao, tipo, valor_acordado, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'Ativo')
        RETURNING id
        """,
        (patient_id, professional_id, professional_id, created_at, 'Protocolo demo de reabilitacao protetica.', 'Protocolo/Total', 1200)
    )
    execute(
        """
        INSERT INTO prosthesis_etapas (
            prosthesis_id, numero_etapa, nome_etapa, data_etapa, data_envio_lab,
            servico_solicitado, assinatura_paciente_base64, professor_id, status
        )
        VALUES (%s, 1, 'Moldagem inicial', %s, %s, 'Modelo de estudo demo', %s, %s, 'Concluído')
        """,
        (prosthesis_id, created_at.isoformat(), created_at.isoformat(), DEMO_SIGNATURE, professional_id)
    )


def _create_optional_documents(patient_id, professional_id, created_at, index):
    if index % 5 == 0:
        execute(
            """
            INSERT INTO receituarios (patient_id, created_by, data, uso, prescricao)
            VALUES (%s, %s, %s, 'Interno', %s)
            """,
            (
                patient_id,
                professional_id,
                created_at,
                json.dumps([{'medicamento': 'Dipirona 500mg', 'quantidade': '10 comprimidos', 'uso': 'Tomar se dor'}]),
            )
        )
    if index % 7 == 0:
        execute(
            """
            INSERT INTO atestados (patient_id, created_by, data, motivo, dias_repouso, cid, observacao)
            VALUES (%s, %s, %s, 'Procedimento odontologico demo', 1, 'Z01.2', 'Atestado ficticio para demonstracao.')
            """,
            (patient_id, professional_id, created_at)
        )


def create_demo_patient(index, run_id, created_by=None):
    seed_odontology_sigtap()
    rng = random.Random(index)
    profile = _select_demo_profile(index)
    municipality = _select_municipality(index)
    specialty = _select_specialty(profile['specialty'])
    professional_id = _ensure_demo_professional()
    created_at = _created_at_for(index)

    gender = 'Fem' if index % 2 == 0 else 'Masc'
    first_name = rng.choice(FIRST_NAMES_F if gender == 'Fem' else FIRST_NAMES_M)
    full_name = f"{first_name} {rng.choice(LAST_NAMES)} {rng.choice(LAST_NAMES)}"
    neighborhood = NEIGHBORHOODS[index % len(NEIGHBORHOODS)]
    attended_area = f"{neighborhood} - {municipality['nome']}"

    patient_id = execute(
        """
        INSERT INTO patients (
            cns, nome, rg, cpf, profissao, endereco_residencial, endereco_comercial,
            cd_anterior, endereco_comercial_adicional, email, genero, data_nascimento,
            nacionalidade, celular, estado_civil, atendido_em, nome_responsavel,
            rg_responsavel, telefone_expedidor_responsavel, email_responsavel,
            is_demo, demo_profile, demo_seed_run_id, criado_em
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, %s, %s, %s)
        RETURNING id
        """,
        (
            generate_cns(index),
            full_name,
            f"{index:02d}.{100 + index:03d}.{200 + index:03d}",
            generate_valid_cpf(index),
            OCCUPATIONS[index % len(OCCUPATIONS)],
            f"Rua Demo {index}, {100 + index}, {neighborhood}, {municipality['nome']} - AL",
            '',
            '',
            '',
            f"paciente.demo{index}@example.com",
            gender,
            _birthdate_for_age(profile['age'], index),
            'Brasileira',
            f"(82) 9{index % 9000 + 1000:04d}-{index % 9000 + 1000:04d}",
            'Casado' if profile['age'] > 30 else 'Solteiro',
            attended_area,
            f"Responsavel Demo {index}" if profile['age'] < 18 else '',
            f"RGRESP{index:04d}" if profile['age'] < 18 else '',
            f"(82) 9{index % 8000 + 2000:04d}-{index % 8000 + 2000:04d}" if profile['age'] < 18 else '',
            f"responsavel.demo{index}@example.com" if profile['age'] < 18 else '',
            profile['key'],
            run_id,
            created_at,
        )
    )

    if index % 3 != 0:
        _create_triage_ticket(patient_id, municipality, specialty, index, created_by or professional_id, created_at)

    execute(
        """
        INSERT INTO patient_tcle (patient_id, aluno_id, assinatura_base64, data_assinatura, texto_opcional)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (patient_id, professional_id, DEMO_SIGNATURE, created_at, 'TCLE ficticio para demonstracao do fluxo.')
    )
    anamnesis_id = _create_anamnesis(patient_id, profile, created_at)
    _create_exams(patient_id, anamnesis_id, profile, professional_id, created_at)
    _create_treatments(patient_id, profile, professional_id, created_at)
    _create_appointments(patient_id, professional_id, created_at, index)
    _create_stomatology(patient_id, profile, professional_id, created_at)
    _create_prosthesis(patient_id, profile, professional_id, created_at)
    _create_optional_documents(patient_id, professional_id, created_at, index)

    return {
        'patient_id': patient_id,
        'name': full_name,
        'profile': profile['label'],
        'municipality': municipality['nome'],
    }


def get_next_demo_index():
    row = query("SELECT COUNT(*) as total FROM patients WHERE is_demo = TRUE", one=True)
    return int(row['total'] or 0) + 1


def create_demo_patients(count=1, created_by=None, label=None):
    count = clamp_demo_count(count)
    start_index = get_next_demo_index()
    run_id = execute(
        """
        INSERT INTO demo_seed_runs (label, requested_count, created_by, details)
        VALUES (%s, %s, %s, %s::jsonb)
        RETURNING id
        """,
        (label or 'Carga demo manual', count, created_by, json.dumps({'start_index': start_index}))
    )
    created = []

    try:
        for offset in range(count):
            created.append(create_demo_patient(start_index + offset, run_id, created_by=created_by))
        execute(
            """
            UPDATE demo_seed_runs
            SET created_count = %s, status = 'success', completed_at = NOW(), details = COALESCE(details, '{}'::jsonb) || %s::jsonb
            WHERE id = %s
            """,
            (len(created), json.dumps({'patients': created}, ensure_ascii=False), run_id)
        )
    except Exception as exc:
        execute(
            """
            UPDATE demo_seed_runs
            SET created_count = %s, status = 'failed', completed_at = NOW(), details = COALESCE(details, '{}'::jsonb) || %s::jsonb
            WHERE id = %s
            """,
            (len(created), json.dumps({'error': str(exc), 'patients': created}, ensure_ascii=False), run_id)
        )
        raise

    return {
        'run_id': run_id,
        'created_count': len(created),
        'patients': created,
    }
