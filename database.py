import os
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

# Pool de conexões: mínimo 2, máximo 20 conexões simultâneas
_connection_pool = None

def init_pool():
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=20,
            dsn=DATABASE_URL,
            cursor_factory=RealDictCursor
        )

def get_db_connection():
    if _connection_pool is None:
        init_pool()
    return _connection_pool.getconn()

def put_db_connection(conn):
    _connection_pool.putconn(conn)

def query(sql, params=(), one=False):
    """Executa consultas SELECT e retorna dicionários."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        rv = cur.fetchall()
        cur.close()
        return (rv[0] if rv else None) if one else rv
    finally:
        put_db_connection(conn)

def execute(sql, params=()):
    """Executa comandos de escrita (INSERT, UPDATE, DELETE). Retorna lastrowid onde disponível."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
        # Para INSERT com RETURNING id, pegamos o resultado
        try:
            result = cur.fetchone()
            last_id = result['id'] if result else None
        except Exception:
            last_id = None
        cur.close()
        return last_id
    except Exception:
        conn.rollback()
        raise
    finally:
        put_db_connection(conn)

def execute_returning(sql, params=()):
    """Executa INSERT com RETURNING id para PostgreSQL."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql + " RETURNING id", params)
        result = cur.fetchone()
        conn.commit()
        cur.close()
        return result['id'] if result else None
    except Exception:
        conn.rollback()
        raise
    finally:
        put_db_connection(conn)

def execute_transaction(statements):
    """
    Executa uma lista de (sql, params) em uma única transação atômica.
    Se qualquer statement falhar, todos são revertidos (rollback).
    statements: lista de tuplas (sql, params) ou (sql,)
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        for item in statements:
            sql = item[0]
            params = item[1] if len(item) > 1 else ()
            cur.execute(sql, params)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        put_db_connection(conn)

def _ensure_columns_exist(table_name, columns):
    """
    Verifica se as colunas existem antes de adicioná-las (compatível com PostgreSQL).
    columns: lista de tuplas (nome_coluna, definicao)
    """
    existing_rows = query(
        "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
        (table_name,)
    )
    existing_columns = [r['column_name'] for r in existing_rows]
    for col_name, col_def in columns:
        if col_name not in existing_columns:
            execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}")


def _acquire_schema_lock():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT pg_advisory_lock(hashtext('gestao_saude_oral_init_db'))")
    cur.close()
    return conn


def _release_schema_lock(conn):
    try:
        cur = conn.cursor()
        cur.execute("SELECT pg_advisory_unlock(hashtext('gestao_saude_oral_init_db'))")
        cur.close()
    finally:
        put_db_connection(conn)

MIGRATIONS = {
    'anamnesis': [
        ('assinatura_base64', 'TEXT')
    ],
    'atendimentos': [
        ('assinatura_paciente_base64', 'TEXT'),
        ('professor_id', 'INTEGER'),
        ('aluno_executor_id', 'INTEGER'),
        ('status', "TEXT DEFAULT 'Pendente'"),
        ('created_by', 'INTEGER')
    ],
    'exam_odontograma': [
        ('notas_dentes', 'TEXT')
    ],
    'users': [
        ('full_name', 'TEXT'),
        ('matricula', 'TEXT'),
        ('cro', 'TEXT'),
        ('cro_uf', 'TEXT'),
        ('active', 'BOOLEAN DEFAULT TRUE'),
        ('last_login_at', 'TIMESTAMP'),
        ('last_login_ip', 'TEXT'),
        ('cns', 'TEXT'),
        ('cbo', 'TEXT'),
        ('cnes', 'TEXT'),
        ('ine', 'TEXT')
    ],
    'patients': [
        ('is_demo', 'BOOLEAN DEFAULT FALSE'),
        ('demo_profile', 'TEXT'),
        ('demo_seed_run_id', 'INTEGER')
    ],
    'exams': [
        ('professor_id', 'INTEGER'),
        ('data_validacao', 'TIMESTAMP')
    ],
    'generated_reports': [
        ('details', 'JSONB'),
        ('signature_hash', 'TEXT'),
        ('signature_status', "TEXT DEFAULT 'pending'"),
        ('signed_at', 'TIMESTAMP'),
        ('scheduled_key', 'TEXT'),
        ('delivery_channel', "TEXT DEFAULT 'painel_seguro'")
    ],
    'tratamento_procedimentos': [
        ('sigtap_code', 'TEXT'),
        ('sigtap_competence', 'TEXT'),
        ('sigtap_name', 'TEXT'),
        ('esus_export_status', "TEXT DEFAULT 'pending'"),
        ('esus_exported_at', 'TIMESTAMP'),
        ('esus_export_batch_id', 'INTEGER')
    ],
    'esus_integration_settings': [
        ('pec_version', 'TEXT'),
        ('ledi_version', 'TEXT'),
        ('cnes', 'TEXT'),
        ('ine', 'TEXT')
    ],
    'esus_export_batches': [
        ('payload_json', 'JSONB'),
        ('records_incomplete', 'INTEGER DEFAULT 0'),
        ('validated_by', 'INTEGER'),
        ('validated_at', 'TIMESTAMP'),
        ('validation_notes', 'TEXT')
    ]
}

def init_db():
    """Inicializa o banco de dados PostgreSQL com a estrutura necessária."""
    schema_lock_conn = _acquire_schema_lock()
    try:
        _init_db_locked()
    finally:
        _release_schema_lock(schema_lock_conn)


def _init_db_locked():
    """Executa a criação/atualização do schema com lock global de banco."""
    execute('''
        CREATE TABLE IF NOT EXISTS municipios (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            codigo TEXT UNIQUE NOT NULL,
            ativo INTEGER DEFAULT 1
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS especialidades (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            codigo TEXT UNIQUE NOT NULL,
            ativo INTEGER DEFAULT 1
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'atendente',
            full_name TEXT,
            matricula TEXT,
            cro TEXT,
            cro_uf TEXT,
            cns TEXT,
            cbo TEXT,
            cnes TEXT,
            ine TEXT,
            active BOOLEAN DEFAULT TRUE,
            last_login_at TIMESTAMP,
            last_login_ip TEXT
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS triagem_acoes (
            id SERIAL PRIMARY KEY,
            municipio_id INTEGER NOT NULL,
            data_acao DATE NOT NULL,
            local TEXT,
            observacoes TEXT,
            status TEXT DEFAULT 'Aberta',
            created_by INTEGER,
            criado_em TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (municipio_id) REFERENCES municipios(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS patients (
            id SERIAL PRIMARY KEY,
            cns TEXT,
            nome TEXT NOT NULL,
            rg TEXT,
            cpf TEXT,
            profissao TEXT,
            endereco_residencial TEXT,
            endereco_comercial TEXT,
            cd_anterior TEXT,
            endereco_comercial_adicional TEXT,
            email TEXT,
            genero TEXT,
            data_nascimento TEXT,
            nacionalidade TEXT,
            celular TEXT,
            estado_civil TEXT,
            atendido_em TEXT,
            nome_responsavel TEXT,
            rg_responsavel TEXT,
            telefone_expedidor_responsavel TEXT,
            email_responsavel TEXT,
            is_demo BOOLEAN DEFAULT FALSE,
            demo_profile TEXT,
            demo_seed_run_id INTEGER,
            criado_em TIMESTAMP DEFAULT NOW()
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS demo_seed_runs (
            id SERIAL PRIMARY KEY,
            label TEXT,
            requested_count INTEGER DEFAULT 0,
            created_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'running',
            created_by INTEGER,
            details JSONB,
            created_at TIMESTAMP DEFAULT NOW(),
            completed_at TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            username TEXT,
            user_role TEXT,
            action TEXT NOT NULL,
            module TEXT NOT NULL,
            entity_type TEXT,
            entity_id TEXT,
            patient_id INTEGER,
            ip_address TEXT,
            user_agent TEXT,
            method TEXT,
            path TEXT,
            status TEXT DEFAULT 'success',
            details JSONB,
            created_at TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE SET NULL
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS patient_consents (
            id SERIAL PRIMARY KEY,
            patient_id INTEGER NOT NULL,
            consent_type TEXT NOT NULL,
            version TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            signed_by_name TEXT,
            signed_by_document TEXT,
            recorded_by INTEGER,
            signature_hash TEXT,
            source_ip TEXT,
            signed_at TIMESTAMP DEFAULT NOW(),
            revoked_at TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
            FOREIGN KEY (recorded_by) REFERENCES users(id) ON DELETE SET NULL
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS digital_signatures (
            id SERIAL PRIMARY KEY,
            document_type TEXT NOT NULL,
            document_id TEXT NOT NULL,
            patient_id INTEGER,
            signed_by INTEGER,
            signer_name TEXT,
            signer_role TEXT,
            signature_provider TEXT DEFAULT 'internal',
            signature_hash TEXT NOT NULL,
            signed_at TIMESTAMP DEFAULT NOW(),
            ip_address TEXT,
            metadata JSONB,
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE SET NULL,
            FOREIGN KEY (signed_by) REFERENCES users(id) ON DELETE SET NULL
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS triagem_senhas (
            id SERIAL PRIMARY KEY,
            triagem_acao_id INTEGER NOT NULL,
            municipio_id INTEGER NOT NULL,
            especialidade_id INTEGER NOT NULL,
            numero INTEGER NOT NULL,
            codigo TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'Disponível',
            patient_id INTEGER UNIQUE,
            entregue_em TIMESTAMP,
            vinculada_em TIMESTAMP,
            criado_em TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (triagem_acao_id) REFERENCES triagem_acoes(id) ON DELETE CASCADE,
            FOREIGN KEY (municipio_id) REFERENCES municipios(id),
            FOREIGN KEY (especialidade_id) REFERENCES especialidades(id),
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE SET NULL,
            UNIQUE (municipio_id, especialidade_id, numero)
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS anamnesis (
            id SERIAL PRIMARY KEY,
            patient_id INTEGER NOT NULL,
            queixa_principal TEXT,
            historia_doenca_atual TEXT,
            sofre_doenca TEXT, sofre_doenca_explica TEXT,
            tratamento_medico TEXT, tratamento_medico_explica TEXT,
            tomando_medicamento TEXT, tomando_medicamento_explica TEXT,
            tem_alergia TEXT, tem_alergia_explica TEXT,
            pressao_arterial TEXT,
            desmaios_convulsoes TEXT,
            tem_cancer TEXT,
            radioterapia_quimioterapia TEXT,
            falta_ar TEXT,
            fez_cirurgia TEXT, fez_cirurgia_explica TEXT,
            sangramento_cortar TEXT,
            cicatrizacao TEXT,
            foi_hospitalizado TEXT, foi_hospitalizado_explica TEXT,
            alergia_medicamento_alimento TEXT,
            gestante TEXT, gestante_semanas TEXT,
            problemas_saude_ja_teve TEXT,
            reacao_anestesia TEXT, reacao_anestesia_explica TEXT,
            ultimo_tratamento_dentario TEXT,
            dor_dentes_gengiva TEXT,
            gengiva_sangra TEXT,
            fio_dental TEXT,
            dores_estalos_maxilar TEXT,
            range_dentes TEXT,
            antecedentes_familiares TEXT,
            causas_obitos_familiares TEXT,
            fuma TEXT, fuma_quantidade TEXT,
            ingere_alcool TEXT, ingere_alcool_frequencia TEXT,
            exercicios_fisicos TEXT, exercicios_fisicos_frequencia TEXT,
            assinatura_base64 TEXT,
            data_anamnese TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (patient_id) REFERENCES patients (id)
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS exams (
            id SERIAL PRIMARY KEY,
            anamnesis_id INTEGER,
            patient_id INTEGER,
            tipo TEXT NOT NULL,
            data_criacao TIMESTAMP DEFAULT NOW(),
            resumo_clinico TEXT,
            professor_id INTEGER,
            data_validacao TIMESTAMP,
            FOREIGN KEY (anamnesis_id) REFERENCES anamnesis (id) ON DELETE CASCADE,
            FOREIGN KEY (patient_id) REFERENCES patients (id) ON DELETE CASCADE,
            FOREIGN KEY (professor_id) REFERENCES users (id) ON DELETE SET NULL
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS exam_fisico (
            id SERIAL PRIMARY KEY,
            exam_id INTEGER NOT NULL,
            estado_geral TEXT,
            peso_referido TEXT,
            altura TEXT,
            pulso TEXT,
            freq_cardiaca TEXT,
            pa_x TEXT,
            lesao_presenca TEXT,
            diagramas_pontos TEXT,
            exame_extrabucal TEXT,
            exame_intrabucal TEXT,
            hipoteses_diagnosticas TEXT,
            imagem_periapical INTEGER DEFAULT 0,
            imagem_oclusal INTEGER DEFAULT 0,
            imagem_panoramica INTEGER DEFAULT 0,
            imagem_tomografia INTEGER DEFAULT 0,
            imagem_outros TEXT,
            imagem_resultado TEXT,
            hema_hemograma INTEGER DEFAULT 0,
            hema_coagulograma INTEGER DEFAULT 0,
            hema_glicemia INTEGER DEFAULT 0,
            hema_outros TEXT,
            hema_resultado TEXT,
            histo_incisional INTEGER DEFAULT 0,
            histo_excisional INTEGER DEFAULT 0,
            diagnostico_definitivo TEXT,
            FOREIGN KEY (exam_id) REFERENCES exams (id)
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS exam_odontograma (
            id SERIAL PRIMARY KEY,
            exam_id INTEGER NOT NULL,
            dentes_data TEXT,
            notas_dentes TEXT,
            observacoes TEXT,
            FOREIGN KEY (exam_id) REFERENCES exams (id)
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS exam_imagem (
            id SERIAL PRIMARY KEY,
            exam_id INTEGER NOT NULL,
            tipo_imagem TEXT,
            escopo TEXT,
            detalhe_escopo TEXT,
            observacoes TEXT,
            FOREIGN KEY (exam_id) REFERENCES exams (id) ON DELETE CASCADE
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS exam_imagem_arquivos (
            id SERIAL PRIMARY KEY,
            exam_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            data_upload TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (exam_id) REFERENCES exams (id) ON DELETE CASCADE
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS atendimentos (
            id SERIAL PRIMARY KEY,
            patient_id INTEGER NOT NULL,
            data TIMESTAMP DEFAULT NOW(),
            observacoes TEXT,
            assinatura_paciente_base64 TEXT,
            professor_id INTEGER,
            aluno_executor_id INTEGER,
            status TEXT DEFAULT 'Pendente',
            created_by INTEGER,
            FOREIGN KEY (patient_id) REFERENCES patients (id),
            FOREIGN KEY (professor_id) REFERENCES users (id),
            FOREIGN KEY (aluno_executor_id) REFERENCES users (id),
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS planos_tratamento (
            id SERIAL PRIMARY KEY,
            patient_id INTEGER NOT NULL,
            descricao TEXT,
            custo_estimado REAL,
            status TEXT DEFAULT 'Pendente',
            criado_em TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (patient_id) REFERENCES patients (id)
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS prosthesis (
            id SERIAL PRIMARY KEY,
            patient_id INTEGER NOT NULL,
            created_by INTEGER NOT NULL,
            aluno_responsavel_id INTEGER,
            data TIMESTAMP DEFAULT NOW(),
            descricao TEXT,
            tipo TEXT,
            valor_acordado REAL DEFAULT 0,
            status TEXT DEFAULT 'Ativo',
            FOREIGN KEY (patient_id) REFERENCES patients (id),
            FOREIGN KEY (created_by) REFERENCES users (id),
            FOREIGN KEY (aluno_responsavel_id) REFERENCES users (id)
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS prosthesis_etapas (
            id SERIAL PRIMARY KEY,
            prosthesis_id INTEGER NOT NULL,
            numero_etapa INTEGER NOT NULL,
            nome_etapa TEXT NOT NULL,
            data_etapa TEXT,
            data_envio_lab TEXT,
            servico_solicitado TEXT,
            assinatura_paciente_base64 TEXT,
            professor_id INTEGER,
            status TEXT DEFAULT 'Pendente',
            FOREIGN KEY (prosthesis_id) REFERENCES prosthesis (id),
            FOREIGN KEY (professor_id) REFERENCES users (id)
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS prosthesis_pagamentos (
            id SERIAL PRIMARY KEY,
            prosthesis_id INTEGER NOT NULL,
            data_pagamento TIMESTAMP DEFAULT NOW(),
            valor REAL NOT NULL,
            responsavel_id INTEGER NOT NULL,
            assinatura_paciente_base64 TEXT,
            FOREIGN KEY (prosthesis_id) REFERENCES prosthesis (id),
            FOREIGN KEY (responsavel_id) REFERENCES users (id)
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS tratamento_procedimentos (
            id SERIAL PRIMARY KEY,
            patient_id INTEGER NOT NULL,
            data_sessao TEXT,
            dente TEXT,
            descricao TEXT,
            sigtap_code TEXT,
            sigtap_competence TEXT,
            sigtap_name TEXT,
            esus_export_status TEXT DEFAULT 'pending',
            esus_exported_at TIMESTAMP,
            esus_export_batch_id INTEGER,
            professor_id INTEGER,
            status TEXT DEFAULT 'Pendente',
            criado_em TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (patient_id) REFERENCES patients (id),
            FOREIGN KEY (professor_id) REFERENCES users (id)
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS sigtap_procedures (
            code TEXT NOT NULL,
            competence TEXT NOT NULL,
            name TEXT NOT NULL,
            group_code TEXT,
            subgroup_code TEXT,
            form_code TEXT,
            source TEXT DEFAULT 'seed',
            active BOOLEAN DEFAULT TRUE,
            imported_at TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (code, competence)
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS esus_integration_settings (
            id SERIAL PRIMARY KEY,
            environment TEXT DEFAULT 'aguardando_prefeitura',
            base_url TEXT,
            pec_version TEXT,
            ledi_version TEXT,
            cnes TEXT,
            ine TEXT,
            installation_id TEXT,
            client_id TEXT,
            credential_status TEXT DEFAULT 'pending',
            notes TEXT,
            active BOOLEAN DEFAULT FALSE,
            updated_at TIMESTAMP DEFAULT NOW()
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS esus_export_batches (
            id SERIAL PRIMARY KEY,
            reference_month TEXT NOT NULL,
            status TEXT DEFAULT 'draft',
            endpoint_url TEXT,
            payload_hash TEXT,
            payload_json JSONB,
            records_total INTEGER DEFAULT 0,
            records_ready INTEGER DEFAULT 0,
            records_missing_sigtap INTEGER DEFAULT 0,
            records_incomplete INTEGER DEFAULT 0,
            generated_by INTEGER,
            generated_at TIMESTAMP DEFAULT NOW(),
            validated_by INTEGER,
            validated_at TIMESTAMP,
            validation_notes TEXT,
            sent_at TIMESTAMP,
            response_status TEXT,
            response_body TEXT,
            FOREIGN KEY (generated_by) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (validated_by) REFERENCES users(id) ON DELETE SET NULL
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS esus_transmission_attempts (
            id SERIAL PRIMARY KEY,
            batch_id INTEGER NOT NULL,
            mode TEXT DEFAULT 'simulation',
            status TEXT DEFAULT 'blocked',
            endpoint_url TEXT,
            http_status INTEGER,
            request_hash TEXT,
            response_body TEXT,
            error_message TEXT,
            attempted_by INTEGER,
            attempted_at TIMESTAMP DEFAULT NOW(),
            details JSONB,
            FOREIGN KEY (batch_id) REFERENCES esus_export_batches(id) ON DELETE CASCADE,
            FOREIGN KEY (attempted_by) REFERENCES users(id) ON DELETE SET NULL
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS exam_controle_placa (
            id SERIAL PRIMARY KEY,
            exam_id INTEGER NOT NULL,
            data_faces TEXT,
            num_dentes INTEGER,
            num_faces_placa INTEGER,
            indice_placa REAL,
            psr_data TEXT,
            condicao_periodontal TEXT,
            FOREIGN KEY (exam_id) REFERENCES exams (id)
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS exam_periograma (
            id SERIAL PRIMARY KEY,
            exam_id INTEGER NOT NULL,
            fase TEXT,
            medicoes_data TEXT,
            diagnostico TEXT,
            FOREIGN KEY (exam_id) REFERENCES exams (id)
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS receituarios (
            id SERIAL PRIMARY KEY,
            patient_id INTEGER NOT NULL,
            created_by INTEGER NOT NULL,
            data TIMESTAMP DEFAULT NOW(),
            uso TEXT,
            prescricao TEXT,
            FOREIGN KEY (patient_id) REFERENCES patients (id),
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS atestados (
            id SERIAL PRIMARY KEY,
            patient_id INTEGER NOT NULL,
            created_by INTEGER NOT NULL,
            data TIMESTAMP DEFAULT NOW(),
            motivo TEXT,
            dias_repouso INTEGER,
            cid TEXT,
            observacao TEXT,
            FOREIGN KEY (patient_id) REFERENCES patients (id),
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS endodontia (
            id SERIAL PRIMARY KEY,
            patient_id INTEGER NOT NULL,
            elemento_dentario TEXT NOT NULL,
            aluno_id INTEGER NOT NULL,
            status TEXT DEFAULT 'Ativo',
            criado_em TIMESTAMP DEFAULT NOW(),
            coroa TEXT,
            canais_radiculares TEXT,
            regiao_apical TEXT,
            demais TEXT,
            diagnostico TEXT,
            grampo TEXT,
            finalidade_protetica TEXT,
            FOREIGN KEY (patient_id) REFERENCES patients (id),
            FOREIGN KEY (aluno_id) REFERENCES users (id)
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS endodontia_canais (
            id SERIAL PRIMARY KEY,
            endodontia_id INTEGER NOT NULL,
            canal TEXT,
            cad TEXT,
            referencia TEXT,
            ct TEXT,
            lima_inicial TEXT,
            lima_final TEXT,
            cone TEXT,
            selamento TEXT,
            FOREIGN KEY (endodontia_id) REFERENCES endodontia (id)
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS endodontia_followup (
            id SERIAL PRIMARY KEY,
            endodontia_id INTEGER NOT NULL,
            data TEXT NOT NULL,
            evolucao TEXT NOT NULL,
            assinatura_paciente_base64 TEXT,
            professor_id INTEGER,
            status TEXT DEFAULT 'Pendente',
            criado_em TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (endodontia_id) REFERENCES endodontia (id),
            FOREIGN KEY (professor_id) REFERENCES users (id)
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS patient_tcle (
            id SERIAL PRIMARY KEY,
            patient_id INTEGER NOT NULL,
            aluno_id INTEGER NOT NULL,
            assinatura_base64 TEXT NOT NULL,
            data_assinatura TIMESTAMP DEFAULT NOW(),
            texto_opcional TEXT,
            FOREIGN KEY (patient_id) REFERENCES patients (id),
            FOREIGN KEY (aluno_id) REFERENCES users (id)
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS estomatologia (
            id SERIAL PRIMARY KEY,
            patient_id INTEGER NOT NULL,
            dentista_id INTEGER,
            data_registro TIMESTAMP DEFAULT NOW(),
            localizacao_lesao TEXT NOT NULL,
            tamanho_lesao TEXT NOT NULL,
            caracteristicas_lesao TEXT NOT NULL,
            habitos_paciente TEXT,
            tempo_evolucao TEXT NOT NULL,
            hipotese_diagnostica TEXT,
            suspeita_neoplasia BOOLEAN DEFAULT FALSE,
            conduta_clinica TEXT,
            encaminhado_para_biopsia BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (patient_id) REFERENCES patients (id) ON DELETE CASCADE,
            FOREIGN KEY (dentista_id) REFERENCES users (id) ON DELETE SET NULL
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS estomatologia_fotos (
            id SERIAL PRIMARY KEY,
            estomatologia_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            legenda TEXT,
            data_upload TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (estomatologia_id) REFERENCES estomatologia (id) ON DELETE CASCADE
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS generated_reports (
            id SERIAL PRIMARY KEY,
            report_type TEXT NOT NULL,
            title TEXT NOT NULL,
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            task_id TEXT,
            generated_by INTEGER,
            status TEXT DEFAULT 'queued',
            details JSONB,
            signature_hash TEXT,
            signature_status TEXT DEFAULT 'pending',
            signed_at TIMESTAMP,
            scheduled_key TEXT,
            delivery_channel TEXT DEFAULT 'painel_seguro',
            created_at TIMESTAMP DEFAULT NOW(),
            completed_at TIMESTAMP,
            FOREIGN KEY (generated_by) REFERENCES users(id) ON DELETE SET NULL
        )
    ''')

    # Colunas adicionadas em atualizações graduais (já incorporadas no DDL acima,
    # mas mantido para retrocompatibilidade caso o schema já exista)
    for table, cols in MIGRATIONS.items():
        _ensure_columns_exist(table, cols)

    # Normaliza valores legados gravados sem acento para o padrão exibido na UI.
    execute("UPDATE tratamento_procedimentos SET status = 'Concluído' WHERE status = 'Concluido'")
    execute("UPDATE atendimentos SET status = 'Concluído' WHERE status = 'Concluido'")

    # === ÍNDICES DE PERFORMANCE ===
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_patients_nome ON patients(nome)",
        "CREATE INDEX IF NOT EXISTS idx_patients_cpf ON patients(cpf)",
        "CREATE INDEX IF NOT EXISTS idx_patients_cns ON patients(cns)",
        "CREATE INDEX IF NOT EXISTS idx_patients_is_demo ON patients(is_demo)",
        "CREATE INDEX IF NOT EXISTS idx_patients_demo_seed_run ON patients(demo_seed_run_id)",
        "CREATE INDEX IF NOT EXISTS idx_anamnesis_patient_id ON anamnesis(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_exams_patient_id ON exams(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_atendimentos_patient_id ON atendimentos(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_estomatologia_patient_id ON estomatologia(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_estomatologia_suspeita ON estomatologia(suspeita_neoplasia)",
        "CREATE INDEX IF NOT EXISTS idx_estomatologia_fotos_est_id ON estomatologia_fotos(estomatologia_id)",
        "CREATE INDEX IF NOT EXISTS idx_atendimentos_professor_id ON atendimentos(professor_id)",
        "CREATE INDEX IF NOT EXISTS idx_atendimentos_aluno_executor_id ON atendimentos(aluno_executor_id)",
        "CREATE INDEX IF NOT EXISTS idx_tratamento_patient_id ON tratamento_procedimentos(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_tratamento_status ON tratamento_procedimentos(status)",
        "CREATE INDEX IF NOT EXISTS idx_tratamento_sigtap_code ON tratamento_procedimentos(sigtap_code)",
        "CREATE INDEX IF NOT EXISTS idx_tratamento_esus_status ON tratamento_procedimentos(esus_export_status)",
        "CREATE INDEX IF NOT EXISTS idx_prosthesis_patient_id ON prosthesis(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_prosthesis_etapas_id ON prosthesis_etapas(prosthesis_id)",
        "CREATE INDEX IF NOT EXISTS idx_prosthesis_pag_id ON prosthesis_pagamentos(prosthesis_id)",
        "CREATE INDEX IF NOT EXISTS idx_endodontia_patient_id ON endodontia(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_endodontia_canais_id ON endodontia_canais(endodontia_id)",
        "CREATE INDEX IF NOT EXISTS idx_endodontia_followup_id ON endodontia_followup(endodontia_id)",
        "CREATE INDEX IF NOT EXISTS idx_receituarios_patient_id ON receituarios(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_atestados_patient_id ON atestados(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_patient_tcle_patient_id ON patient_tcle(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
        "CREATE INDEX IF NOT EXISTS idx_users_active ON users(active)",
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_patient_id ON audit_logs(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action)",
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_module ON audit_logs(module)",
        "CREATE INDEX IF NOT EXISTS idx_patient_consents_patient_id ON patient_consents(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_patient_consents_status ON patient_consents(status)",
        "CREATE INDEX IF NOT EXISTS idx_digital_signatures_document ON digital_signatures(document_type, document_id)",
        "CREATE INDEX IF NOT EXISTS idx_digital_signatures_patient_id ON digital_signatures(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_exam_fisico_exam_id ON exam_fisico(exam_id)",
        "CREATE INDEX IF NOT EXISTS idx_exam_odontograma_exam_id ON exam_odontograma(exam_id)",
        "CREATE INDEX IF NOT EXISTS idx_exam_placa_exam_id ON exam_controle_placa(exam_id)",
        "CREATE INDEX IF NOT EXISTS idx_exam_periograma_exam_id ON exam_periograma(exam_id)",
        "CREATE INDEX IF NOT EXISTS idx_triagem_senhas_codigo ON triagem_senhas(codigo)",
        "CREATE INDEX IF NOT EXISTS idx_triagem_senhas_patient_id ON triagem_senhas(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_triagem_senhas_mun_esp ON triagem_senhas(municipio_id, especialidade_id)",
        "CREATE INDEX IF NOT EXISTS idx_triagem_acoes_municipio ON triagem_acoes(municipio_id)",
        "CREATE INDEX IF NOT EXISTS idx_generated_reports_type ON generated_reports(report_type)",
        "CREATE INDEX IF NOT EXISTS idx_generated_reports_period ON generated_reports(period_start, period_end)",
        "CREATE INDEX IF NOT EXISTS idx_generated_reports_status ON generated_reports(status)",
        "CREATE INDEX IF NOT EXISTS idx_generated_reports_scheduled_key ON generated_reports(scheduled_key)",
        "CREATE INDEX IF NOT EXISTS idx_generated_reports_signature_hash ON generated_reports(signature_hash)",
        "CREATE INDEX IF NOT EXISTS idx_sigtap_procedures_name ON sigtap_procedures(name)",
        "CREATE INDEX IF NOT EXISTS idx_sigtap_procedures_competence ON sigtap_procedures(competence)",
        "CREATE INDEX IF NOT EXISTS idx_esus_batches_reference_month ON esus_export_batches(reference_month)",
        "CREATE INDEX IF NOT EXISTS idx_esus_batches_status ON esus_export_batches(status)",
        "CREATE INDEX IF NOT EXISTS idx_esus_batches_validated_at ON esus_export_batches(validated_at)",
        "CREATE INDEX IF NOT EXISTS idx_esus_attempts_batch_id ON esus_transmission_attempts(batch_id)",
        "CREATE INDEX IF NOT EXISTS idx_esus_attempts_attempted_at ON esus_transmission_attempts(attempted_at)",
        "CREATE INDEX IF NOT EXISTS idx_demo_seed_runs_created_at ON demo_seed_runs(created_at)",
    ]
    for idx_sql in indexes:
        execute(idx_sql)

    # === TABELA AGENDA (CONSULTAS) ===
    execute('''
        CREATE TABLE IF NOT EXISTS consultas (
            id SERIAL PRIMARY KEY,
            patient_id INTEGER NOT NULL,
            dentista_id INTEGER NOT NULL,
            data_consulta TIMESTAMP NOT NULL,
            duracao_minutos INTEGER DEFAULT 30,
            status TEXT DEFAULT 'Pendente',
            observacoes TEXT,
            created_by INTEGER NOT NULL,
            criado_em TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
            FOREIGN KEY (dentista_id) REFERENCES users(id) ON DELETE RESTRICT,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    agenda_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_consultas_data ON consultas(data_consulta)",
        "CREATE INDEX IF NOT EXISTS idx_consultas_dentista ON consultas(dentista_id)",
        "CREATE INDEX IF NOT EXISTS idx_consultas_patient ON consultas(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_consultas_status ON consultas(status)",
    ]
    for idx_sql in agenda_indexes:
        execute(idx_sql)

    seed_reference_data()
    print("Banco de dados PostgreSQL inicializado/verificado com sucesso!")

def seed_reference_data():
    """Garante os cadastros base usados pelo módulo de triagem."""
    especialidades = [
        ('Prótese Dentária', 'P'),
        ('Implantodontia', 'I'),
        ('Dentística', 'D'),
        ('Ortodontia', 'ORT'),
        ('Endodontia', 'END'),
        ('Periodontia', 'PER'),
        ('Cirurgia e Traumatologia Buco-Maxilo-Facial', 'CTBMF'),
        ('Odontopediatria', 'ODP'),
        ('Estética', 'EST'),
    ]
    municipios = [
        ('Água Branca', 'AGB'),
        ('Anadia', 'ANA'),
        ('Arapiraca', 'ARA'),
        ('Atalaia', 'ATL'),
        ('Barra de Santo Antônio', 'BSA'),
        ('Barra de São Miguel', 'BSM'),
        ('Batalha', 'BAT'),
        ('Belém', 'BEL'),
        ('Belo Monte', 'BMT'),
        ('Boca da Mata', 'BDM'),
        ('Branquinha', 'BRQ'),
        ('Cacimbinhas', 'CAC'),
        ('Cajueiro', 'CAJ'),
        ('Campestre', 'CAM'),
        ('Campo Alegre', 'CPA'),
        ('Campo Grande', 'CPG'),
        ('Canapi', 'CAN'),
        ('Capela', 'CAP'),
        ('Carneiros', 'CAR'),
        ('Chã Preta', 'CHP'),
        ('Coité do Nóia', 'CDN'),
        ('Colônia Leopoldina', 'CLP'),
        ('Coqueiro Seco', 'CQS'),
        ('Coruripe', 'COR'),
        ('Craíbas', 'CRA'),
        ('Delmiro Gouveia', 'DMG'),
        ('Dois Riachos', 'DRI'),
        ('Estrela de Alagoas', 'EDA'),
        ('Feira Grande', 'FEG'),
        ('Feliz Deserto', 'FZD'),
        ('Flexeiras', 'FLX'),
        ('Girau do Ponciano', 'GDP'),
        ('Ibateguara', 'IBT'),
        ('Igaci', 'IGA'),
        ('Igreja Nova', 'IGN'),
        ('Inhapi', 'INH'),
        ('Jacaré dos Homens', 'JDH'),
        ('Jacuípe', 'JCP'),
        ('Japaratinga', 'JAP'),
        ('Jaramataia', 'JRM'),
        ('Jequiá da Praia', 'JQP'),
        ('Joaquim Gomes', 'JQG'),
        ('Jundiá', 'JUN'),
        ('Junqueiro', 'JQR'),
        ('Lagoa da Canoa', 'LDC'),
        ('Limoeiro de Anadia', 'LDA'),
        ('Maceió', 'MCZ'),
        ('Major Isidoro', 'MJI'),
        ('Mar Vermelho', 'MVM'),
        ('Maragogi', 'MRG'),
        ('Maravilha', 'MRV'),
        ('Marechal Deodoro', 'MDR'),
        ('Maribondo', 'MRB'),
        ('Mata Grande', 'MTG'),
        ('Matriz de Camaragibe', 'MTC'),
        ('Messias', 'MES'),
        ('Minador do Negrão', 'MDN'),
        ('Monteirópolis', 'MTP'),
        ('Murici', 'MUR'),
        ('Novo Lino', 'NVL'),
        ("Olho d'Água das Flores", 'OAF'),
        ("Olho d'Água do Casado", 'OAC'),
        ("Olho d'Água Grande", 'OAG'),
        ('Olivença', 'OLV'),
        ('Ouro Branco', 'OUB'),
        ('Palestina', 'PAL'),
        ('Palmeira dos Índios', 'PMI'),
        ('Pão de Açúcar', 'PDA'),
        ('Pariconha', 'PAR'),
        ('Paripueira', 'PRP'),
        ('Passo de Camaragibe', 'PDC'),
        ('Paulo Jacinto', 'PJT'),
        ('Penedo', 'PEN'),
        ('Piaçabuçu', 'PIA'),
        ('Pilar', 'PIL'),
        ('Pindoba', 'PIN'),
        ('Piranhas', 'PIR'),
        ('Poço das Trincheiras', 'PDT'),
        ('Porto Calvo', 'PTC'),
        ('Porto de Pedras', 'PTP'),
        ('Porto Real do Colégio', 'PRC'),
        ('Quebrangulo', 'QBR'),
        ('Rio Largo', 'RLG'),
        ('Roteiro', 'ROT'),
        ('Santa Luzia do Norte', 'SLN'),
        ('Santana do Ipanema', 'SDI'),
        ('Santana do Mundaú', 'SDM'),
        ('São Brás', 'SBR'),
        ('São José da Laje', 'SJL'),
        ('São José da Tapera', 'SJT'),
        ('São Luís do Quitunde', 'SLQ'),
        ('São Miguel dos Campos', 'SMC'),
        ('São Miguel dos Milagres', 'SMM'),
        ('São Sebastião', 'SSB'),
        ('Satuba', 'SAT'),
        ('Senador Rui Palmeira', 'SRP'),
        ("Tanque d'Arca", 'TDA'),
        ('Taquarana', 'TAQ'),
        ('Teotônio Vilela', 'TNV'),
        ('Traipu', 'TRP'),
        ('União dos Palmares', 'UDP'),
        ('Viçosa', 'VIC'),
    ]

    for nome, codigo in especialidades:
        execute(
            "INSERT INTO especialidades (nome, codigo) VALUES (%s, %s) ON CONFLICT (codigo) DO UPDATE SET nome = EXCLUDED.nome, ativo = 1",
            (nome, codigo)
        )

    for nome, codigo in municipios:
        execute(
            "INSERT INTO municipios (nome, codigo) VALUES (%s, %s) ON CONFLICT (codigo) DO UPDATE SET nome = EXCLUDED.nome, ativo = 1",
            (nome, codigo)
        )
