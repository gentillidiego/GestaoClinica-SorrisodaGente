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


def _migrate_legacy_user_roles():
    from constants import get_legacy_role_migrations

    for legacy_role, canonical in get_legacy_role_migrations():
        execute(
            "UPDATE users SET role = %s WHERE role = %s",
            (canonical, legacy_role),
        )


def _seed_execution_units():
    from constants import DEFAULT_EXECUTION_UNIT, EXECUTION_UNITS

    for code, name in EXECUTION_UNITS:
        execute(
            """
            INSERT INTO execution_units (code, name, active, is_default)
            VALUES (%s, %s, TRUE, %s)
            ON CONFLICT (code) DO UPDATE
            SET name = COALESCE(NULLIF(execution_units.name, ''), EXCLUDED.name),
                active = COALESCE(execution_units.active, TRUE),
                updated_at = NOW()
            """,
            (code, name, code == DEFAULT_EXECUTION_UNIT),
        )
    execute(
        """
        UPDATE execution_units
        SET is_default = (code = %s)
        WHERE is_default = TRUE OR code = %s
        """,
        (DEFAULT_EXECUTION_UNIT, DEFAULT_EXECUTION_UNIT),
    )


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
        ('assinatura_base64', 'TEXT'),
        ('assinatura_modo', "TEXT DEFAULT 'patient_canvas'"),
        ('assinatura_event_id', 'INTEGER'),
        ('assinatura_document_hash', 'TEXT'),
        ('assinatura_auth_method', 'TEXT'),
        ('assinatura_source_ip', 'TEXT'),
        ('assinatura_user_agent', 'TEXT')
    ],
    'atendimentos': [
        ('assinatura_paciente_base64', 'TEXT'),
        ('assinatura_modo', "TEXT DEFAULT 'patient_canvas'"),
        ('assinatura_event_id', 'INTEGER'),
        ('assinatura_document_hash', 'TEXT'),
        ('assinatura_a_rogo_por', 'INTEGER'),
        ('assinatura_a_rogo_declaracao', 'TEXT'),
        ('assinatura_a_rogo_testemunhas', 'JSONB'),
        ('assinatura_auth_method', 'TEXT'),
        ('assinatura_source_ip', 'TEXT'),
        ('assinatura_user_agent', 'TEXT'),
        ('professor_id', 'INTEGER'),
        ('aluno_executor_id', 'INTEGER'),
        ('status', "TEXT DEFAULT 'Pendente'"),
        ('created_by', 'INTEGER')
    ],
    'patient_tcle': [
        ('assinatura_modo', "TEXT DEFAULT 'patient_canvas'"),
        ('assinatura_event_id', 'INTEGER'),
        ('assinatura_document_hash', 'TEXT'),
        ('assinatura_a_rogo_por', 'INTEGER'),
        ('assinatura_a_rogo_declaracao', 'TEXT'),
        ('assinatura_a_rogo_testemunhas', 'JSONB'),
        ('assinatura_auth_method', 'TEXT'),
        ('assinatura_source_ip', 'TEXT'),
        ('assinatura_user_agent', 'TEXT')
    ],
    'exam_odontograma': [
        ('notas_dentes', 'TEXT')
    ],
    'users': [
        ('full_name', 'TEXT'),
        ('matricula', 'TEXT'),
        ('email', 'TEXT'),
        ('celular', 'TEXT'),
        ('data_nascimento', 'DATE'),
        ('is_first_access', 'BOOLEAN DEFAULT FALSE'),
        ('first_access_completed_at', 'TIMESTAMP'),
        ('email_confirmed_at', 'TIMESTAMP'),
        ('password_changed_at', 'TIMESTAMP'),
        ('password_reset_token_hash', 'TEXT'),
        ('password_reset_expires_at', 'TIMESTAMP'),
        ('password_reset_used_at', 'TIMESTAMP'),
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
    'triagem_acoes': [
        ('execution_unit', "TEXT DEFAULT 'unidade_principal'")
    ],
    'consultas': [
        ('execution_unit', "TEXT DEFAULT 'unidade_principal'")
    ],
    'exams': [
        ('professor_id', 'INTEGER'),
        ('data_validacao', 'TIMESTAMP')
    ],
    'exam_imagem_arquivos': [
        ('patient_id', 'INTEGER'),
        ('visual_category', "TEXT DEFAULT 'radiografia'"),
        ('caption', 'TEXT'),
        ('clinical_context', 'TEXT'),
        ('comparison_label', "TEXT DEFAULT 'diagnostico'"),
        ('comparison_group', 'TEXT'),
        ('taken_at', 'TIMESTAMP'),
        ('uploaded_by', 'INTEGER'),
        ('active', 'BOOLEAN DEFAULT TRUE')
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
        ('especialidade_sigtap', 'TEXT'),
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
    ],
    'estomatologia': [
        ('cancer_confirmed', 'BOOLEAN DEFAULT FALSE'),
        ('cancer_confirmed_at', 'TIMESTAMP'),
        ('diagnostico_confirmado', 'TEXT')
    ],
    'estomatologia_fotos': [
        ('visual_category', "TEXT DEFAULT 'lesao'"),
        ('clinical_context', 'TEXT'),
        ('comparison_label', "TEXT DEFAULT 'evolucao'"),
        ('comparison_group', 'TEXT'),
        ('taken_at', 'TIMESTAMP'),
        ('uploaded_by', 'INTEGER'),
        ('active', 'BOOLEAN DEFAULT TRUE')
    ],
    'endodontia': [
        ('updated_at', 'TIMESTAMP'),
        ('cancelado_em', 'TIMESTAMP'),
        ('cancelado_por', 'INTEGER'),
        ('motivo_cancelamento', 'TEXT'),
        ('diagnostico_estruturado_status', "TEXT DEFAULT 'pendente'"),
        ('queixa_inicio', 'TEXT'),
        ('queixa_duracao', 'TEXT'),
        ('queixa_intensidade', 'TEXT'),
        ('queixa_localizacao', 'TEXT'),
        ('fatores_exacerbantes', 'TEXT'),
        ('fatores_alivio', 'TEXT'),
        ('queixa_descricao', 'TEXT'),
        ('linfadenopatia_cervical', 'BOOLEAN DEFAULT FALSE'),
        ('linfadenopatia_submandibular', 'BOOLEAN DEFAULT FALSE'),
        ('assimetria_facial', 'BOOLEAN DEFAULT FALSE'),
        ('edema_extraoral', 'BOOLEAN DEFAULT FALSE'),
        ('exame_extraoral_observacoes', 'TEXT'),
        ('edema_submucoso', 'BOOLEAN DEFAULT FALSE'),
        ('fistula_trajeto', 'BOOLEAN DEFAULT FALSE'),
        ('fistula_localizacao', 'TEXT'),
        ('carie_profunda', 'BOOLEAN DEFAULT FALSE'),
        ('restauracao_inadequada', 'BOOLEAN DEFAULT FALSE'),
        ('faceta_desgaste', 'BOOLEAN DEFAULT FALSE'),
        ('exame_intraoral_observacoes', 'TEXT'),
        ('mobilidade', 'TEXT'),
        ('sondagem_mesial_mm', 'NUMERIC(5,2)'),
        ('sondagem_distal_mm', 'NUMERIC(5,2)'),
        ('sondagem_vestibular_mm', 'NUMERIC(5,2)'),
        ('sondagem_lingual_palatino_mm', 'NUMERIC(5,2)'),
        ('tipo_lesao', 'TEXT'),
        ('diagnostico_pulpar', 'TEXT'),
        ('diagnostico_apical', 'TEXT'),
        ('cid10_sugerido', 'TEXT'),
        ('workflow_tipo', "TEXT DEFAULT 'tratamento'"),
        ('polpa_normal_justificativa', 'TEXT'),
        ('status_tratamento', "TEXT DEFAULT 'aguardando_inicio'"),
        ('sessoes_planejadas', 'INTEGER'),
        ('proxima_sessao_prevista', 'DATE'),
        ('janela_retorno_dias', 'INTEGER'),
        ('restauracao_definitiva_registrada', 'BOOLEAN DEFAULT FALSE'),
        ('restauracao_definitiva_data', 'DATE'),
        ('restauracao_definitiva_material', 'TEXT'),
        ('selamento_coronario_adequado', 'BOOLEAN DEFAULT FALSE'),
        ('restauracao_observacoes', 'TEXT'),
        ('lesao_periapical_extensa', 'BOOLEAN DEFAULT FALSE')
    ],
    'endodontia_canais': [
        ('ponto_referencia_coronario', 'TEXT'),
        ('cri_mm', 'NUMERIC(6,2)'),
        ('cai_mm', 'NUMERIC(6,2)'),
        ('crd_mm', 'NUMERIC(6,2)'),
        ('crt_sugerido_mm', 'NUMERIC(6,2)'),
        ('crt_final_mm', 'NUMERIC(6,2)'),
        ('crt_override_justificativa', 'TEXT'),
        ('localizador_apical_usado', 'BOOLEAN DEFAULT FALSE'),
        ('modelo_localizador', 'TEXT'),
        ('leitura_localizador', 'NUMERIC(5,2)'),
        ('confirmacao_eletronica', 'BOOLEAN DEFAULT FALSE')
    ],
    'endodontia_followup': [
        ('assinatura_modo', "TEXT DEFAULT 'patient_canvas'"),
        ('assinatura_event_id', 'INTEGER'),
        ('assinatura_document_hash', 'TEXT'),
        ('assinatura_auth_method', 'TEXT'),
        ('assinatura_source_ip', 'TEXT'),
        ('assinatura_user_agent', 'TEXT'),
        ('numero_sessao', 'INTEGER'),
        ('etapa_realizada', 'TEXT'),
        ('status_sessao', "TEXT DEFAULT 'realizada'"),
        ('proxima_sessao_prevista', 'DATE'),
        ('janela_retorno_dias', 'INTEGER'),
        ('observacao_clinica', 'TEXT'),
        ('lai_mm', 'NUMERIC(5,2)'),
        ('tecnica_instrumentacao', 'TEXT'),
        ('sistema_instrumentacao', 'TEXT'),
        ('liga_instrumento', 'TEXT'),
        ('protocolo_observacoes', 'TEXT'),
        ('solucao_irrigadora', 'TEXT'),
        ('edta_usado', 'BOOLEAN DEFAULT FALSE'),
        ('tempo_irrigacao_min', 'INTEGER'),
        ('agitacao_irrigadora', 'TEXT'),
        ('volume_irrigacao_ml', 'NUMERIC(6,2)'),
        ('irrigacao_observacoes', 'TEXT'),
        ('medicacao_intracanal', 'TEXT'),
        ('medicacao_intracanal_outra', 'TEXT'),
        ('medicacao_veiculo', 'TEXT'),
        ('medicacao_quantidade', 'TEXT'),
        ('selamento_provisorio', 'TEXT'),
        ('selamento_provisorio_outro', 'TEXT'),
        ('cone_principal_material', 'TEXT'),
        ('cone_principal_calibre', 'TEXT'),
        ('cone_principal_conicidade', 'TEXT'),
        ('prova_cone', 'BOOLEAN DEFAULT FALSE'),
        ('tug_back', 'BOOLEAN DEFAULT FALSE'),
        ('crt_confirmado_mm', 'NUMERIC(5,2)'),
        ('cimento_obturador', 'TEXT'),
        ('cimento_classe', 'TEXT'),
        ('cimento_classe_outro', 'TEXT'),
        ('cimento_lote', 'TEXT'),
        ('cimento_validade', 'DATE'),
        ('tecnica_obturacao', 'TEXT'),
        ('tecnica_obturacao_outra', 'TEXT'),
        ('radiografia_final_aprovada', 'BOOLEAN DEFAULT FALSE'),
        ('radiografia_final_gaps', 'BOOLEAN DEFAULT FALSE'),
        ('radiografia_final_voids', 'BOOLEAN DEFAULT FALSE'),
        ('controle_qualidade_observacoes', 'TEXT'),
        ('restauracao_definitiva_registrada', 'BOOLEAN DEFAULT FALSE'),
        ('restauracao_definitiva_data', 'DATE'),
        ('restauracao_definitiva_material', 'TEXT'),
        ('selamento_coronario_adequado', 'BOOLEAN DEFAULT FALSE'),
        ('restauracao_observacoes', 'TEXT')
    ],
    'procedure_cost_references': [
        ('methodology_status', "TEXT DEFAULT 'draft'"),
        ('notes', 'TEXT'),
        ('validated_by', 'INTEGER'),
        ('validated_at', 'TIMESTAMP'),
        ('validation_notes', 'TEXT')
    ],
    'prosthesis_etapas': [
        ('assinatura_modo', "TEXT DEFAULT 'patient_canvas'"),
        ('assinatura_event_id', 'INTEGER'),
        ('assinatura_document_hash', 'TEXT'),
        ('assinatura_auth_method', 'TEXT'),
        ('assinatura_source_ip', 'TEXT'),
        ('assinatura_user_agent', 'TEXT')
    ],
    'prosthesis_pagamentos': [
        ('assinatura_modo', "TEXT DEFAULT 'patient_canvas'"),
        ('assinatura_event_id', 'INTEGER'),
        ('assinatura_document_hash', 'TEXT'),
        ('assinatura_auth_method', 'TEXT'),
        ('assinatura_source_ip', 'TEXT'),
        ('assinatura_user_agent', 'TEXT')
    ],
    'professional_registration_requests': [
        ('data_nascimento', 'DATE'),
        ('review_notes', 'TEXT'),
        ('reviewed_by', 'INTEGER'),
        ('reviewed_at', 'TIMESTAMP'),
        ('created_user_id', 'INTEGER'),
        ('updated_at', 'TIMESTAMP DEFAULT NOW()')
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
            email TEXT,
            celular TEXT,
            data_nascimento DATE,
            is_first_access BOOLEAN DEFAULT FALSE,
            first_access_completed_at TIMESTAMP,
            email_confirmed_at TIMESTAMP,
            password_changed_at TIMESTAMP,
            password_reset_token_hash TEXT,
            password_reset_expires_at TIMESTAMP,
            password_reset_used_at TIMESTAMP,
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
        CREATE TABLE IF NOT EXISTS professional_registration_requests (
            id SERIAL PRIMARY KEY,
            full_name TEXT NOT NULL,
            cpf TEXT NOT NULL,
            data_nascimento DATE NOT NULL,
            email TEXT NOT NULL,
            celular TEXT NOT NULL,
            desired_username TEXT NOT NULL,
            requested_role TEXT NOT NULL,
            cns TEXT,
            cbo TEXT,
            cro TEXT,
            cro_uf TEXT,
            notes TEXT,
            truth_accepted BOOLEAN DEFAULT FALSE,
            lgpd_accepted BOOLEAN DEFAULT FALSE,
            status TEXT DEFAULT 'pending',
            review_notes TEXT,
            reviewed_by INTEGER,
            reviewed_at TIMESTAMP,
            created_user_id INTEGER,
            source_ip TEXT,
            user_agent TEXT,
            submitted_payload JSONB,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (created_user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS triagem_acoes (
            id SERIAL PRIMARY KEY,
            municipio_id INTEGER NOT NULL,
            data_acao DATE NOT NULL,
            local TEXT,
            execution_unit TEXT DEFAULT 'unidade_principal',
            observacoes TEXT,
            status TEXT DEFAULT 'Aberta',
            created_by INTEGER,
            criado_em TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (municipio_id) REFERENCES municipios(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS execution_units (
            id SERIAL PRIMARY KEY,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            cnes TEXT,
            address TEXT,
            notes TEXT,
            active BOOLEAN DEFAULT TRUE,
            is_default BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS territorial_locations (
            id SERIAL PRIMARY KEY,
            scope TEXT NOT NULL,
            municipio_id INTEGER,
            neighborhood TEXT,
            unit_name TEXT,
            triagem_acao_id INTEGER,
            latitude NUMERIC(10,7),
            longitude NUMERIC(10,7),
            source TEXT DEFAULT 'manual',
            accuracy TEXT,
            notes TEXT,
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (municipio_id) REFERENCES municipios(id) ON DELETE CASCADE,
            FOREIGN KEY (triagem_acao_id) REFERENCES triagem_acoes(id) ON DELETE CASCADE
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
        CREATE TABLE IF NOT EXISTS signature_events (
            id SERIAL PRIMARY KEY,
            document_type TEXT NOT NULL,
            document_id TEXT,
            patient_id INTEGER,
            patient_name TEXT,
            patient_cpf TEXT,
            signature_mode TEXT DEFAULT 'patient_canvas',
            document_hash TEXT NOT NULL,
            signed_by INTEGER,
            signer_username TEXT,
            signer_role TEXT,
            auth_method TEXT,
            source_ip TEXT,
            user_agent TEXT,
            declaration_text TEXT,
            witnesses JSONB,
            metadata JSONB,
            created_at TIMESTAMP DEFAULT NOW(),
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
            assinatura_modo TEXT DEFAULT 'patient_canvas',
            assinatura_event_id INTEGER,
            assinatura_document_hash TEXT,
            assinatura_auth_method TEXT,
            assinatura_source_ip TEXT,
            assinatura_user_agent TEXT,
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
            patient_id INTEGER,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            visual_category TEXT DEFAULT 'radiografia',
            caption TEXT,
            clinical_context TEXT,
            comparison_label TEXT DEFAULT 'diagnostico',
            comparison_group TEXT,
            taken_at TIMESTAMP,
            uploaded_by INTEGER,
            active BOOLEAN DEFAULT TRUE,
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
            assinatura_modo TEXT DEFAULT 'patient_canvas',
            assinatura_event_id INTEGER,
            assinatura_document_hash TEXT,
            assinatura_a_rogo_por INTEGER,
            assinatura_a_rogo_declaracao TEXT,
            assinatura_a_rogo_testemunhas JSONB,
            assinatura_auth_method TEXT,
            assinatura_source_ip TEXT,
            assinatura_user_agent TEXT,
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
            assinatura_modo TEXT DEFAULT 'patient_canvas',
            assinatura_event_id INTEGER,
            assinatura_document_hash TEXT,
            assinatura_auth_method TEXT,
            assinatura_source_ip TEXT,
            assinatura_user_agent TEXT,
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
            assinatura_modo TEXT DEFAULT 'patient_canvas',
            assinatura_event_id INTEGER,
            assinatura_document_hash TEXT,
            assinatura_auth_method TEXT,
            assinatura_source_ip TEXT,
            assinatura_user_agent TEXT,
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
            especialidade_sigtap TEXT,
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
        CREATE TABLE IF NOT EXISTS procedure_cost_references (
            id SERIAL PRIMARY KEY,
            sigtap_code TEXT NOT NULL UNIQUE,
            sigtap_name TEXT,
            public_cost NUMERIC(12, 2) DEFAULT 0,
            private_reference NUMERIC(12, 2) DEFAULT 0,
            reference_label TEXT DEFAULT 'Referência operacional interna',
            source TEXT DEFAULT 'manual',
            methodology_status TEXT DEFAULT 'draft',
            notes TEXT,
            validated_by INTEGER,
            validated_at TIMESTAMP,
            validation_notes TEXT,
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
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
            updated_at TIMESTAMP,
            cancelado_em TIMESTAMP,
            cancelado_por INTEGER,
            motivo_cancelamento TEXT,
            diagnostico_estruturado_status TEXT DEFAULT 'pendente',
            queixa_inicio TEXT,
            queixa_duracao TEXT,
            queixa_intensidade TEXT,
            queixa_localizacao TEXT,
            fatores_exacerbantes TEXT,
            fatores_alivio TEXT,
            queixa_descricao TEXT,
            linfadenopatia_cervical BOOLEAN DEFAULT FALSE,
            linfadenopatia_submandibular BOOLEAN DEFAULT FALSE,
            assimetria_facial BOOLEAN DEFAULT FALSE,
            edema_extraoral BOOLEAN DEFAULT FALSE,
            exame_extraoral_observacoes TEXT,
            edema_submucoso BOOLEAN DEFAULT FALSE,
            fistula_trajeto BOOLEAN DEFAULT FALSE,
            fistula_localizacao TEXT,
            carie_profunda BOOLEAN DEFAULT FALSE,
            restauracao_inadequada BOOLEAN DEFAULT FALSE,
            faceta_desgaste BOOLEAN DEFAULT FALSE,
            exame_intraoral_observacoes TEXT,
            mobilidade TEXT,
            sondagem_mesial_mm NUMERIC(5,2),
            sondagem_distal_mm NUMERIC(5,2),
            sondagem_vestibular_mm NUMERIC(5,2),
            sondagem_lingual_palatino_mm NUMERIC(5,2),
            tipo_lesao TEXT,
            diagnostico_pulpar TEXT,
            diagnostico_apical TEXT,
            cid10_sugerido TEXT,
            workflow_tipo TEXT DEFAULT 'tratamento',
            polpa_normal_justificativa TEXT,
            status_tratamento TEXT DEFAULT 'aguardando_inicio',
            sessoes_planejadas INTEGER,
            proxima_sessao_prevista DATE,
            janela_retorno_dias INTEGER,
            restauracao_definitiva_registrada BOOLEAN DEFAULT FALSE,
            restauracao_definitiva_data DATE,
            restauracao_definitiva_material TEXT,
            selamento_coronario_adequado BOOLEAN DEFAULT FALSE,
            restauracao_observacoes TEXT,
            lesao_periapical_extensa BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (patient_id) REFERENCES patients (id),
            FOREIGN KEY (aluno_id) REFERENCES users (id),
            FOREIGN KEY (cancelado_por) REFERENCES users (id)
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
            ponto_referencia_coronario TEXT,
            cri_mm NUMERIC(6,2),
            cai_mm NUMERIC(6,2),
            crd_mm NUMERIC(6,2),
            crt_sugerido_mm NUMERIC(6,2),
            crt_final_mm NUMERIC(6,2),
            crt_override_justificativa TEXT,
            localizador_apical_usado BOOLEAN DEFAULT FALSE,
            modelo_localizador TEXT,
            leitura_localizador NUMERIC(5,2),
            confirmacao_eletronica BOOLEAN DEFAULT FALSE,
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
            assinatura_modo TEXT DEFAULT 'patient_canvas',
            assinatura_event_id INTEGER,
            assinatura_document_hash TEXT,
            assinatura_auth_method TEXT,
            assinatura_source_ip TEXT,
            assinatura_user_agent TEXT,
            professor_id INTEGER,
            status TEXT DEFAULT 'Pendente',
            numero_sessao INTEGER,
            etapa_realizada TEXT,
            status_sessao TEXT DEFAULT 'realizada',
            proxima_sessao_prevista DATE,
            janela_retorno_dias INTEGER,
            observacao_clinica TEXT,
            lai_mm NUMERIC(5,2),
            tecnica_instrumentacao TEXT,
            sistema_instrumentacao TEXT,
            liga_instrumento TEXT,
            protocolo_observacoes TEXT,
            solucao_irrigadora TEXT,
            edta_usado BOOLEAN DEFAULT FALSE,
            tempo_irrigacao_min INTEGER,
            agitacao_irrigadora TEXT,
            volume_irrigacao_ml NUMERIC(6,2),
            irrigacao_observacoes TEXT,
            medicacao_intracanal TEXT,
            medicacao_intracanal_outra TEXT,
            medicacao_veiculo TEXT,
            medicacao_quantidade TEXT,
            selamento_provisorio TEXT,
            selamento_provisorio_outro TEXT,
            cone_principal_material TEXT,
            cone_principal_calibre TEXT,
            cone_principal_conicidade TEXT,
            prova_cone BOOLEAN DEFAULT FALSE,
            tug_back BOOLEAN DEFAULT FALSE,
            crt_confirmado_mm NUMERIC(5,2),
            cimento_obturador TEXT,
            cimento_classe TEXT,
            cimento_classe_outro TEXT,
            cimento_lote TEXT,
            cimento_validade DATE,
            tecnica_obturacao TEXT,
            tecnica_obturacao_outra TEXT,
            radiografia_final_aprovada BOOLEAN DEFAULT FALSE,
            radiografia_final_gaps BOOLEAN DEFAULT FALSE,
            radiografia_final_voids BOOLEAN DEFAULT FALSE,
            controle_qualidade_observacoes TEXT,
            restauracao_definitiva_registrada BOOLEAN DEFAULT FALSE,
            restauracao_definitiva_data DATE,
            restauracao_definitiva_material TEXT,
            selamento_coronario_adequado BOOLEAN DEFAULT FALSE,
            restauracao_observacoes TEXT,
            criado_em TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (endodontia_id) REFERENCES endodontia (id),
            FOREIGN KEY (professor_id) REFERENCES users (id)
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS endodontia_imagens (
            id SERIAL PRIMARY KEY,
            patient_id INTEGER NOT NULL,
            endodontia_id INTEGER NOT NULL,
            followup_id INTEGER,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            visual_category TEXT DEFAULT 'periapical_inicial',
            caption TEXT,
            clinical_context TEXT,
            comparison_label TEXT DEFAULT 'diagnostico',
            comparison_group TEXT,
            canal TEXT,
            equipamento TEXT,
            formato TEXT,
            taken_at TIMESTAMP,
            uploaded_by INTEGER,
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (patient_id) REFERENCES patients (id),
            FOREIGN KEY (endodontia_id) REFERENCES endodontia (id),
            FOREIGN KEY (followup_id) REFERENCES endodontia_followup (id),
            FOREIGN KEY (uploaded_by) REFERENCES users (id)
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS endodontia_proservacao (
            id SERIAL PRIMARY KEY,
            patient_id INTEGER NOT NULL,
            endodontia_id INTEGER NOT NULL,
            followup_id INTEGER,
            tipo_retorno TEXT NOT NULL,
            data_prevista DATE NOT NULL,
            status TEXT DEFAULT 'planejado',
            lembrete_dias INTEGER DEFAULT 7,
            data_realizada DATE,
            dente_funcao_mastigatoria BOOLEAN DEFAULT FALSE,
            ausencia_dor_percussao BOOLEAN DEFAULT FALSE,
            ausencia_dor_palpacao_apical BOOLEAN DEFAULT FALSE,
            ausencia_edema_mucosa BOOLEAN DEFAULT FALSE,
            ausencia_fistula BOOLEAN DEFAULT FALSE,
            clinica_observacoes TEXT,
            espaco_periodontal_normal BOOLEAN DEFAULT FALSE,
            lamina_dura_integra BOOLEAN DEFAULT FALSE,
            ausencia_lesao_radiolucida BOOLEAN DEFAULT FALSE,
            reducao_lesao_preexistente BOOLEAN DEFAULT FALSE,
            radiografica_observacoes TEXT,
            criterio_negativo_instavel BOOLEAN DEFAULT FALSE,
            resultado_strindberg TEXT,
            resultado_observacoes TEXT,
            restauracao_tipo TEXT,
            restauracao_selamento_adequado BOOLEAN DEFAULT FALSE,
            restauracao_data DATE,
            restauracao_cd_id INTEGER,
            restauracao_observacoes TEXT,
            criado_em TIMESTAMP DEFAULT NOW(),
            atualizado_em TIMESTAMP DEFAULT NOW(),
            UNIQUE (endodontia_id, tipo_retorno),
            FOREIGN KEY (patient_id) REFERENCES patients (id),
            FOREIGN KEY (endodontia_id) REFERENCES endodontia (id),
            FOREIGN KEY (followup_id) REFERENCES endodontia_followup (id),
            FOREIGN KEY (restauracao_cd_id) REFERENCES users (id)
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS endodontia_orcamento_items (
            id SERIAL PRIMARY KEY,
            patient_id INTEGER NOT NULL,
            endodontia_id INTEGER NOT NULL,
            dente_numero TEXT,
            canal_id TEXT,
            procedimento TEXT,
            codigo_tuss TEXT,
            codigo_sigtap TEXT,
            sigtap_name TEXT,
            codigo_cid10 TEXT,
            valor_unitario NUMERIC(12,2) DEFAULT 0,
            valor_publico_unitario NUMERIC(12,2) DEFAULT 0,
            economia_estimada_unitaria NUMERIC(12,2) DEFAULT 0,
            sessoes_previstas INTEGER,
            complexidade TEXT,
            grupo_dentario TEXT,
            multiplicador NUMERIC(5,2) DEFAULT 1,
            observacoes TEXT,
            status TEXT DEFAULT 'gerado',
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (patient_id) REFERENCES patients (id),
            FOREIGN KEY (endodontia_id) REFERENCES endodontia (id),
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS patient_tcle (
            id SERIAL PRIMARY KEY,
            patient_id INTEGER NOT NULL,
            aluno_id INTEGER NOT NULL,
            assinatura_base64 TEXT NOT NULL,
            assinatura_modo TEXT DEFAULT 'patient_canvas',
            assinatura_event_id INTEGER,
            assinatura_document_hash TEXT,
            assinatura_a_rogo_por INTEGER,
            assinatura_a_rogo_declaracao TEXT,
            assinatura_a_rogo_testemunhas JSONB,
            assinatura_auth_method TEXT,
            assinatura_source_ip TEXT,
            assinatura_user_agent TEXT,
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
            cancer_confirmed BOOLEAN DEFAULT FALSE,
            cancer_confirmed_at TIMESTAMP,
            diagnostico_confirmado TEXT,
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
            visual_category TEXT DEFAULT 'lesao',
            clinical_context TEXT,
            comparison_label TEXT DEFAULT 'evolucao',
            comparison_group TEXT,
            taken_at TIMESTAMP,
            uploaded_by INTEGER,
            active BOOLEAN DEFAULT TRUE,
            data_upload TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (estomatologia_id) REFERENCES estomatologia (id) ON DELETE CASCADE
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS inventory_suppliers (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            document TEXT,
            phone TEXT,
            email TEXT,
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS inventory_items (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'material',
            unit TEXT NOT NULL DEFAULT 'unidade',
            min_quantity NUMERIC(12, 3) DEFAULT 0,
            center_cost TEXT,
            notes TEXT,
            active BOOLEAN DEFAULT TRUE,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS inventory_lots (
            id SERIAL PRIMARY KEY,
            item_id INTEGER NOT NULL,
            supplier_id INTEGER,
            lot_number TEXT NOT NULL,
            expiration_date DATE,
            quantity_initial NUMERIC(12, 3) NOT NULL DEFAULT 0,
            quantity_current NUMERIC(12, 3) NOT NULL DEFAULT 0,
            unit_cost NUMERIC(12, 2) DEFAULT 0,
            received_at DATE DEFAULT CURRENT_DATE,
            center_cost TEXT,
            notes TEXT,
            active BOOLEAN DEFAULT TRUE,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (item_id) REFERENCES inventory_items(id) ON DELETE CASCADE,
            FOREIGN KEY (supplier_id) REFERENCES inventory_suppliers(id) ON DELETE SET NULL,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS inventory_usage (
            id SERIAL PRIMARY KEY,
            patient_id INTEGER NOT NULL,
            treatment_procedure_id INTEGER,
            atendimento_id INTEGER,
            item_id INTEGER NOT NULL,
            lot_id INTEGER NOT NULL,
            quantity NUMERIC(12, 3) NOT NULL DEFAULT 1,
            unit_cost_snapshot NUMERIC(12, 2) DEFAULT 0,
            usage_type TEXT DEFAULT 'consumo',
            used_at TIMESTAMP DEFAULT NOW(),
            professional_id INTEGER,
            notes TEXT,
            post_op_required BOOLEAN DEFAULT FALSE,
            post_op_due_date DATE,
            post_op_completed_at TIMESTAMP,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
            FOREIGN KEY (treatment_procedure_id) REFERENCES tratamento_procedimentos(id) ON DELETE SET NULL,
            FOREIGN KEY (atendimento_id) REFERENCES atendimentos(id) ON DELETE SET NULL,
            FOREIGN KEY (item_id) REFERENCES inventory_items(id) ON DELETE RESTRICT,
            FOREIGN KEY (lot_id) REFERENCES inventory_lots(id) ON DELETE RESTRICT,
            FOREIGN KEY (professional_id) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
        )
    ''')

    execute('''
        CREATE TABLE IF NOT EXISTS inventory_adjustments (
            id SERIAL PRIMARY KEY,
            item_id INTEGER NOT NULL,
            lot_id INTEGER NOT NULL,
            adjustment_type TEXT NOT NULL,
            quantity NUMERIC(12, 3) NOT NULL,
            previous_quantity NUMERIC(12, 3) NOT NULL,
            new_quantity NUMERIC(12, 3) NOT NULL,
            unit_cost_snapshot NUMERIC(12, 2) DEFAULT 0,
            reason TEXT NOT NULL,
            notes TEXT,
            adjusted_by INTEGER,
            authorized_by INTEGER,
            authorization_method TEXT DEFAULT 'password_confirmation',
            created_at TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (item_id) REFERENCES inventory_items(id) ON DELETE RESTRICT,
            FOREIGN KEY (lot_id) REFERENCES inventory_lots(id) ON DELETE RESTRICT,
            FOREIGN KEY (adjusted_by) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (authorized_by) REFERENCES users(id) ON DELETE SET NULL
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

    execute('''
        CREATE TABLE IF NOT EXISTS consultas (
            id SERIAL PRIMARY KEY,
            patient_id INTEGER NOT NULL,
            dentista_id INTEGER NOT NULL,
            data_consulta TIMESTAMP NOT NULL,
            duracao_minutos INTEGER DEFAULT 30,
            status TEXT DEFAULT 'Pendente',
            execution_unit TEXT DEFAULT 'unidade_principal',
            observacoes TEXT,
            created_by INTEGER NOT NULL,
            criado_em TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
            FOREIGN KEY (dentista_id) REFERENCES users(id) ON DELETE RESTRICT,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')

    # Colunas adicionadas em atualizações graduais (já incorporadas no DDL acima,
    # mas mantido para retrocompatibilidade caso o schema já exista)
    for table, cols in MIGRATIONS.items():
        _ensure_columns_exist(table, cols)

    _migrate_legacy_user_roles()

    # Normaliza valores legados gravados sem acento para o padrão exibido na UI.
    execute("UPDATE tratamento_procedimentos SET status = 'Concluído' WHERE status = 'Concluido'")
    execute("UPDATE atendimentos SET status = 'Concluído' WHERE status = 'Concluido'")
    execute("UPDATE triagem_acoes SET execution_unit = 'unidade_principal' WHERE execution_unit IS NULL OR execution_unit = ''")
    execute("UPDATE consultas SET execution_unit = 'unidade_principal' WHERE execution_unit IS NULL OR execution_unit = ''")
    _seed_execution_units()
    execute("""
        UPDATE exam_imagem_arquivos a
        SET patient_id = e.patient_id
        FROM exams e
        WHERE a.exam_id = e.id
          AND a.patient_id IS NULL
    """)
    execute("""
        UPDATE exam_imagem_arquivos
        SET visual_category = COALESCE(visual_category, 'radiografia'),
            comparison_label = COALESCE(comparison_label, 'diagnostico'),
            active = COALESCE(active, TRUE)
    """)
    execute("""
        UPDATE estomatologia_fotos
        SET visual_category = COALESCE(visual_category, 'lesao'),
            comparison_label = COALESCE(comparison_label, 'evolucao'),
            active = COALESCE(active, TRUE)
    """)
    execute("""
        UPDATE estomatologia e
        SET cancer_confirmed = TRUE,
            cancer_confirmed_at = COALESCE(e.cancer_confirmed_at, e.data_registro + INTERVAL '2 days'),
            diagnostico_confirmado = COALESCE(
                e.diagnostico_confirmado,
                'Carcinoma espinocelular confirmado em acompanhamento demo.'
            )
        FROM patients p
        WHERE p.id = e.patient_id
          AND p.is_demo = TRUE
          AND p.demo_profile = 'idoso_oncologico'
          AND e.cancer_confirmed = FALSE
    """)

    # === ÍNDICES DE PERFORMANCE ===
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_patients_nome ON patients(nome)",
        "CREATE INDEX IF NOT EXISTS idx_patients_cpf ON patients(cpf)",
        "CREATE INDEX IF NOT EXISTS idx_patients_cns ON patients(cns)",
        "CREATE INDEX IF NOT EXISTS idx_patients_is_demo ON patients(is_demo)",
        "CREATE INDEX IF NOT EXISTS idx_patients_demo_seed_run ON patients(demo_seed_run_id)",
        "CREATE INDEX IF NOT EXISTS idx_anamnesis_patient_id ON anamnesis(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_anamnesis_signature_event ON anamnesis(assinatura_event_id)",
        "CREATE INDEX IF NOT EXISTS idx_exams_patient_id ON exams(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_exam_imagem_arquivos_exam_id ON exam_imagem_arquivos(exam_id)",
        "CREATE INDEX IF NOT EXISTS idx_exam_imagem_arquivos_patient_id ON exam_imagem_arquivos(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_exam_imagem_arquivos_visual_category ON exam_imagem_arquivos(visual_category)",
        "CREATE INDEX IF NOT EXISTS idx_exam_imagem_arquivos_comparison_group ON exam_imagem_arquivos(comparison_group)",
        "CREATE INDEX IF NOT EXISTS idx_atendimentos_patient_id ON atendimentos(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_estomatologia_patient_id ON estomatologia(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_estomatologia_suspeita ON estomatologia(suspeita_neoplasia)",
        "CREATE INDEX IF NOT EXISTS idx_estomatologia_cancer_confirmed ON estomatologia(cancer_confirmed)",
        "CREATE INDEX IF NOT EXISTS idx_estomatologia_fotos_est_id ON estomatologia_fotos(estomatologia_id)",
        "CREATE INDEX IF NOT EXISTS idx_estomatologia_fotos_visual_category ON estomatologia_fotos(visual_category)",
        "CREATE INDEX IF NOT EXISTS idx_estomatologia_fotos_comparison_group ON estomatologia_fotos(comparison_group)",
        "CREATE INDEX IF NOT EXISTS idx_inventory_items_category ON inventory_items(category)",
        "CREATE INDEX IF NOT EXISTS idx_inventory_items_active ON inventory_items(active)",
        "CREATE INDEX IF NOT EXISTS idx_inventory_lots_item_id ON inventory_lots(item_id)",
        "CREATE INDEX IF NOT EXISTS idx_inventory_lots_expiration ON inventory_lots(expiration_date)",
        "CREATE INDEX IF NOT EXISTS idx_inventory_lots_current ON inventory_lots(quantity_current)",
        "CREATE INDEX IF NOT EXISTS idx_inventory_usage_patient_id ON inventory_usage(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_inventory_usage_treatment_id ON inventory_usage(treatment_procedure_id)",
        "CREATE INDEX IF NOT EXISTS idx_inventory_usage_lot_id ON inventory_usage(lot_id)",
        "CREATE INDEX IF NOT EXISTS idx_inventory_usage_postop ON inventory_usage(post_op_required, post_op_completed_at, post_op_due_date)",
        "CREATE INDEX IF NOT EXISTS idx_inventory_adjustments_lot_id ON inventory_adjustments(lot_id)",
        "CREATE INDEX IF NOT EXISTS idx_inventory_adjustments_type ON inventory_adjustments(adjustment_type)",
        "CREATE INDEX IF NOT EXISTS idx_inventory_adjustments_created_at ON inventory_adjustments(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_atendimentos_professor_id ON atendimentos(professor_id)",
        "CREATE INDEX IF NOT EXISTS idx_atendimentos_aluno_executor_id ON atendimentos(aluno_executor_id)",
        "CREATE INDEX IF NOT EXISTS idx_tratamento_patient_id ON tratamento_procedimentos(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_tratamento_status ON tratamento_procedimentos(status)",
        "CREATE INDEX IF NOT EXISTS idx_tratamento_sigtap_code ON tratamento_procedimentos(sigtap_code)",
        "CREATE INDEX IF NOT EXISTS idx_tratamento_esus_status ON tratamento_procedimentos(esus_export_status)",
        "CREATE INDEX IF NOT EXISTS idx_prosthesis_patient_id ON prosthesis(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_prosthesis_etapas_id ON prosthesis_etapas(prosthesis_id)",
        "CREATE INDEX IF NOT EXISTS idx_prosthesis_etapas_signature_event ON prosthesis_etapas(assinatura_event_id)",
        "CREATE INDEX IF NOT EXISTS idx_prosthesis_pag_id ON prosthesis_pagamentos(prosthesis_id)",
        "CREATE INDEX IF NOT EXISTS idx_prosthesis_pag_signature_event ON prosthesis_pagamentos(assinatura_event_id)",
        "CREATE INDEX IF NOT EXISTS idx_endodontia_patient_id ON endodontia(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_endodontia_status ON endodontia(status)",
        "CREATE INDEX IF NOT EXISTS idx_endodontia_status_tratamento ON endodontia(status_tratamento)",
        "CREATE INDEX IF NOT EXISTS idx_endodontia_proxima_sessao ON endodontia(proxima_sessao_prevista)",
        "CREATE INDEX IF NOT EXISTS idx_endodontia_cancelado_em ON endodontia(cancelado_em)",
        "CREATE INDEX IF NOT EXISTS idx_endodontia_canais_id ON endodontia_canais(endodontia_id)",
        "CREATE INDEX IF NOT EXISTS idx_endodontia_followup_id ON endodontia_followup(endodontia_id)",
        "CREATE INDEX IF NOT EXISTS idx_endodontia_followup_signature_event ON endodontia_followup(assinatura_event_id)",
        "CREATE INDEX IF NOT EXISTS idx_endodontia_followup_status_sessao ON endodontia_followup(status_sessao)",
        "CREATE INDEX IF NOT EXISTS idx_endodontia_followup_proxima_sessao ON endodontia_followup(proxima_sessao_prevista)",
        "CREATE INDEX IF NOT EXISTS idx_endodontia_imagens_patient_id ON endodontia_imagens(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_endodontia_imagens_endo_id ON endodontia_imagens(endodontia_id)",
        "CREATE INDEX IF NOT EXISTS idx_endodontia_imagens_followup_id ON endodontia_imagens(followup_id)",
        "CREATE INDEX IF NOT EXISTS idx_endodontia_imagens_visual_category ON endodontia_imagens(visual_category)",
        "CREATE INDEX IF NOT EXISTS idx_endodontia_imagens_comparison_group ON endodontia_imagens(comparison_group)",
        "CREATE INDEX IF NOT EXISTS idx_endodontia_proservacao_patient_id ON endodontia_proservacao(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_endodontia_proservacao_endo_id ON endodontia_proservacao(endodontia_id)",
        "CREATE INDEX IF NOT EXISTS idx_endodontia_proservacao_data_prevista ON endodontia_proservacao(data_prevista)",
        "CREATE INDEX IF NOT EXISTS idx_endodontia_proservacao_status ON endodontia_proservacao(status)",
        "CREATE INDEX IF NOT EXISTS idx_endodontia_orcamento_patient_id ON endodontia_orcamento_items(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_endodontia_orcamento_endo_id ON endodontia_orcamento_items(endodontia_id)",
        "CREATE INDEX IF NOT EXISTS idx_endodontia_orcamento_status ON endodontia_orcamento_items(status)",
        "CREATE INDEX IF NOT EXISTS idx_endodontia_orcamento_sigtap ON endodontia_orcamento_items(codigo_sigtap)",
        "CREATE INDEX IF NOT EXISTS idx_receituarios_patient_id ON receituarios(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_atestados_patient_id ON atestados(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_patient_tcle_patient_id ON patient_tcle(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_patient_tcle_signature_event ON patient_tcle(assinatura_event_id)",
        "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
        "CREATE INDEX IF NOT EXISTS idx_users_active ON users(active)",
        "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
        "CREATE INDEX IF NOT EXISTS idx_users_password_reset_hash ON users(password_reset_token_hash)",
        "CREATE INDEX IF NOT EXISTS idx_prof_reg_requests_status ON professional_registration_requests(status)",
        "CREATE INDEX IF NOT EXISTS idx_prof_reg_requests_cpf ON professional_registration_requests(cpf)",
        "CREATE INDEX IF NOT EXISTS idx_prof_reg_requests_email ON professional_registration_requests(email)",
        "CREATE INDEX IF NOT EXISTS idx_prof_reg_requests_role ON professional_registration_requests(requested_role)",
        "CREATE INDEX IF NOT EXISTS idx_prof_reg_requests_created_at ON professional_registration_requests(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_patient_id ON audit_logs(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action)",
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_module ON audit_logs(module)",
        "CREATE INDEX IF NOT EXISTS idx_patient_consents_patient_id ON patient_consents(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_patient_consents_status ON patient_consents(status)",
        "CREATE INDEX IF NOT EXISTS idx_digital_signatures_document ON digital_signatures(document_type, document_id)",
        "CREATE INDEX IF NOT EXISTS idx_digital_signatures_patient_id ON digital_signatures(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_signature_events_document ON signature_events(document_type, document_id)",
        "CREATE INDEX IF NOT EXISTS idx_signature_events_patient_id ON signature_events(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_signature_events_hash ON signature_events(document_hash)",
        "CREATE INDEX IF NOT EXISTS idx_signature_events_mode ON signature_events(signature_mode)",
        "CREATE INDEX IF NOT EXISTS idx_exam_fisico_exam_id ON exam_fisico(exam_id)",
        "CREATE INDEX IF NOT EXISTS idx_exam_odontograma_exam_id ON exam_odontograma(exam_id)",
        "CREATE INDEX IF NOT EXISTS idx_exam_placa_exam_id ON exam_controle_placa(exam_id)",
        "CREATE INDEX IF NOT EXISTS idx_exam_periograma_exam_id ON exam_periograma(exam_id)",
        "CREATE INDEX IF NOT EXISTS idx_triagem_senhas_codigo ON triagem_senhas(codigo)",
        "CREATE INDEX IF NOT EXISTS idx_triagem_senhas_patient_id ON triagem_senhas(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_triagem_senhas_mun_esp ON triagem_senhas(municipio_id, especialidade_id)",
        "CREATE INDEX IF NOT EXISTS idx_triagem_acoes_municipio ON triagem_acoes(municipio_id)",
        "CREATE INDEX IF NOT EXISTS idx_territorial_locations_scope ON territorial_locations(scope)",
        "CREATE INDEX IF NOT EXISTS idx_territorial_locations_municipio ON territorial_locations(municipio_id)",
        "CREATE INDEX IF NOT EXISTS idx_territorial_locations_neighborhood ON territorial_locations(neighborhood)",
        "CREATE INDEX IF NOT EXISTS idx_territorial_locations_triagem ON territorial_locations(triagem_acao_id)",
        "CREATE INDEX IF NOT EXISTS idx_generated_reports_type ON generated_reports(report_type)",
        "CREATE INDEX IF NOT EXISTS idx_generated_reports_period ON generated_reports(period_start, period_end)",
        "CREATE INDEX IF NOT EXISTS idx_generated_reports_status ON generated_reports(status)",
        "CREATE INDEX IF NOT EXISTS idx_generated_reports_scheduled_key ON generated_reports(scheduled_key)",
        "CREATE INDEX IF NOT EXISTS idx_generated_reports_signature_hash ON generated_reports(signature_hash)",
        "CREATE INDEX IF NOT EXISTS idx_sigtap_procedures_name ON sigtap_procedures(name)",
        "CREATE INDEX IF NOT EXISTS idx_sigtap_procedures_competence ON sigtap_procedures(competence)",
        "CREATE INDEX IF NOT EXISTS idx_procedure_cost_references_code ON procedure_cost_references(sigtap_code)",
        "CREATE INDEX IF NOT EXISTS idx_procedure_cost_references_active ON procedure_cost_references(active)",
        "CREATE INDEX IF NOT EXISTS idx_procedure_cost_references_methodology ON procedure_cost_references(methodology_status)",
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
            execution_unit TEXT DEFAULT 'unidade_principal',
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
    municipio_coordinates = [
        ('Água Branca', -9.262, -37.938),
        ('Anadia', -9.68489, -36.3078),
        ('Arapiraca', -9.75487, -36.6615),
        ('Atalaia', -9.5119, -36.0086),
        ('Barra de Santo Antônio', -9.4023, -35.5101),
        ('Barra de São Miguel', -9.83842, -35.9057),
        ('Batalha', -9.6742, -37.133),
        ('Belém', -9.57047, -36.4904),
        ('Belo Monte', -9.82272, -37.277),
        ('Boca da Mata', -9.64308, -36.2125),
        ('Branquinha', -9.23342, -36.0162),
        ('Cacimbinhas', -9.40121, -36.9911),
        ('Cajueiro', -9.3994, -36.1559),
        ('Campestre', -8.84723, -35.5685),
        ('Campo Alegre', -9.78451, -36.3525),
        ('Campo Grande', -9.95542, -36.7926),
        ('Canapi', -9.11932, -37.5967),
        ('Capela', -9.41504, -36.0826),
        ('Carneiros', -9.48476, -37.3773),
        ('Chã Preta', -9.2556, -36.2983),
        ('Coité do Nóia', -9.63348, -36.5845),
        ('Colônia Leopoldina', -8.91806, -35.7214),
        ('Coqueiro Seco', -9.63715, -35.7994),
        ('Coruripe', -10.1276, -36.1717),
        ('Craíbas', -9.6178, -36.7697),
        ('Delmiro Gouveia', -9.38534, -37.9987),
        ('Dois Riachos', -9.38465, -37.0965),
        ('Estrela de Alagoas', -9.39089, -36.7644),
        ('Feira Grande', -9.89859, -36.6815),
        ('Feliz Deserto', -10.2935, -36.3028),
        ('Flexeiras', -9.27281, -35.7139),
        ('Girau do Ponciano', -9.88404, -36.8316),
        ('Ibateguara', -8.97823, -35.9373),
        ('Igaci', -9.53768, -36.6372),
        ('Igreja Nova', -10.1235, -36.6597),
        ('Inhapi', -9.22594, -37.7509),
        ('Jacaré dos Homens', -9.63545, -37.2076),
        ('Jacuípe', -8.83951, -35.4591),
        ('Japaratinga', -9.08746, -35.2634),
        ('Jaramataia', -9.66224, -37.0046),
        ('Jequiá da Praia', -10.0133, -36.0142),
        ('Joaquim Gomes', -9.1328, -35.7474),
        ('Jundiá', -8.93297, -35.5669),
        ('Junqueiro', -9.90696, -36.4803),
        ('Lagoa da Canoa', -9.83291, -36.7413),
        ('Limoeiro de Anadia', -9.74098, -36.5121),
        ('Maceió', -9.66599, -35.735),
        ('Major Isidoro', -9.53009, -36.992),
        ('Mar Vermelho', -9.44739, -36.3881),
        ('Maragogi', -9.00744, -35.2267),
        ('Maravilha', -9.23045, -37.3524),
        ('Marechal Deodoro', -9.70971, -35.8967),
        ('Maribondo', -9.58353, -36.3045),
        ('Mata Grande', -9.11824, -37.7323),
        ('Matriz de Camaragibe', -9.15437, -35.5243),
        ('Messias', -9.39384, -35.8392),
        ('Minador do Negrão', -9.31236, -36.8696),
        ('Monteirópolis', -9.60357, -37.2505),
        ('Murici', -9.30682, -35.9428),
        ('Novo Lino', -8.94191, -35.664),
        ("Olho d'Água das Flores", -9.53686, -37.2971),
        ("Olho d'Água do Casado", -9.50357, -37.8301),
        ("Olho d'Água Grande", -10.0572, -36.8101),
        ('Olivença', -9.51954, -37.1954),
        ('Ouro Branco', -9.15884, -37.3556),
        ('Palestina', -9.67493, -37.339),
        ('Palmeira dos Índios', -9.40568, -36.6328),
        ('Pão de Açúcar', -9.74032, -37.4403),
        ('Pariconha', -9.25634, -37.9988),
        ('Paripueira', -9.46313, -35.552),
        ('Passo de Camaragibe', -9.24511, -35.4745),
        ('Paulo Jacinto', -9.36792, -36.3672),
        ('Penedo', -10.2874, -36.5819),
        ('Piaçabuçu', -10.406, -36.434),
        ('Pilar', -9.60135, -35.9543),
        ('Pindoba', -9.47382, -36.2918),
        ('Piranhas', -9.624, -37.757),
        ('Poço das Trincheiras', -9.30742, -37.2889),
        ('Porto Calvo', -9.05195, -35.3987),
        ('Porto de Pedras', -9.16006, -35.3049),
        ('Porto Real do Colégio', -10.1849, -36.8376),
        ('Quebrangulo', -9.32001, -36.4692),
        ('Rio Largo', -9.47783, -35.8394),
        ('Roteiro', -9.83503, -35.9782),
        ('Santa Luzia do Norte', -9.6037, -35.8232),
        ('Santana do Ipanema', -9.36999, -37.248),
        ('Santana do Mundaú', -9.17141, -36.2176),
        ('São Brás', -10.1141, -36.8522),
        ('São José da Laje', -9.01278, -36.0515),
        ('São José da Tapera', -9.55768, -37.3831),
        ('São Luís do Quitunde', -9.31816, -35.5606),
        ('São Miguel dos Campos', -9.78301, -36.0971),
        ('São Miguel dos Milagres', -9.26493, -35.3763),
        ('São Sebastião', -9.93043, -36.559),
        ('Satuba', -9.56911, -35.8227),
        ('Senador Rui Palmeira', -9.46986, -37.4576),
        ("Tanque d'Arca", -9.53379, -36.4366),
        ('Taquarana', -9.64529, -36.4928),
        ('Teotônio Vilela', -9.91656, -36.3492),
        ('Traipu', -9.96262, -37.0071),
        ('União dos Palmares', -9.15921, -36.0223),
        ('Viçosa', -9.36763, -36.2431),
    ]
    procedure_cost_references = [
        ('0101020040', 'AÇÃO COLETIVA DE EXAME BUCAL COM FINALIDADE EPIDEMIOLÓGICA', 12.00, 80.00),
        ('0101020066', 'APLICAÇÃO DE SELANTE (POR DENTE)', 18.00, 120.00),
        ('0101020074', 'APLICAÇÃO TÓPICA DE FLÚOR (INDIVIDUAL POR SESSÃO)', 15.00, 90.00),
        ('0101020090', 'SELAMENTO PROVISÓRIO DE CAVIDADE DENTÁRIA', 22.00, 140.00),
        ('0101020104', 'ORIENTAÇÃO DE HIGIENE BUCAL', 10.00, 70.00),
        ('0101020112', 'AÇÃO COLETIVA DE PREVENÇÃO DE CÂNCER BUCAL', 14.00, 100.00),
        ('0201010526', 'BIÓPSIA DOS TECIDOS MOLES DA BOCA', 120.00, 850.00),
        ('0307010015', 'CAPEAMENTO PULPAR', 45.00, 220.00),
        ('0307010031', 'RESTAURAÇÃO DE DENTE PERMANENTE ANTERIOR COM RESINA COMPOSTA', 80.00, 350.00),
        ('0307010074', 'TRATAMENTO RESTAURADOR ATRAUMÁTICO (TRA/ART)', 55.00, 260.00),
        ('0307010082', 'RESTAURAÇÃO DE DENTE DECÍDUO POSTERIOR COM RESINA COMPOSTA', 65.00, 280.00),
        ('0307010104', 'RESTAURAÇÃO DE DENTE DECÍDUO POSTERIOR COM IONÔMERO DE VIDRO', 60.00, 250.00),
        ('0307010120', 'RESTAURAÇÃO DE DENTE PERMANENTE POSTERIOR COM RESINA COMPOSTA', 90.00, 420.00),
        ('0307020010', 'ACESSO À POLPA DENTÁRIA E MEDICAÇÃO (POR DENTE)', 70.00, 300.00),
        ('0307020037', 'TRATAMENTO ENDODÔNTICO DE DENTE DECÍDUO', 120.00, 550.00),
        ('0307020045', 'TRATAMENTO ENDODÔNTICO DE DENTE PERMANENTE BIRRADICULAR', 180.00, 900.00),
        ('0307020053', 'TRATAMENTO ENDODÔNTICO DE DENTE PERMANENTE COM TRÊS OU MAIS RAÍZES', 220.00, 1200.00),
        ('0307020061', 'TRATAMENTO ENDODÔNTICO DE DENTE PERMANENTE UNIRRADICULAR', 150.00, 750.00),
        ('0307030024', 'RASPAGEM ALISAMENTO SUBGENGIVAIS (POR SEXTANTE)', 45.00, 220.00),
        ('0307030032', 'RASPAGEM CORONO-RADICULAR (POR SEXTANTE)', 50.00, 260.00),
        ('0307030040', 'PROFILAXIA / REMOÇÃO DA PLACA BACTERIANA', 35.00, 180.00),
        ('0307030059', 'RASPAGEM ALISAMENTO E POLIMENTO SUPRAGENGIVAIS (POR SEXTANTE)', 40.00, 200.00),
        ('0307030075', 'TRATAMENTO DE LESÕES DA MUCOSA ORAL', 70.00, 350.00),
        ('0307030083', 'TRATAMENTO DE PERICORONARITE', 65.00, 300.00),
        ('0307040070', 'MOLDAGEM DENTO-GENGIVAL P/ CONSTRUÇÃO DE PRÓTESE DENTÁRIA', 110.00, 650.00),
        ('0307040089', 'REEMBASAMENTO E CONSERTO DE PRÓTESE DENTÁRIA', 95.00, 450.00),
        ('0414020120', 'EXODONTIA DE DENTE DECÍDUO', 60.00, 250.00),
        ('0414020138', 'EXODONTIA DE DENTE PERMANENTE', 85.00, 380.00),
        ('0414020146', 'EXODONTIA MÚLTIPLA COM ALVEOLOPLASTIA POR SEXTANTE', 180.00, 900.00),
        ('0414020278', 'REMOÇÃO DE DENTE RETIDO (INCLUSO / IMPACTADO)', 220.00, 1400.00),
        ('0414020375', 'TRATAMENTO CIRÚRGICO PERIODONTAL (POR SEXTANTE)', 130.00, 700.00),
        ('0414020421', 'IMPLANTE DENTÁRIO OSTEOINTEGRADOR', 850.00, 3500.00),
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

    for code, name, public_cost, private_reference in procedure_cost_references:
        execute(
            """
            INSERT INTO procedure_cost_references (
                sigtap_code, sigtap_name, public_cost, private_reference,
                reference_label, source, methodology_status, notes
            )
            VALUES (
                %s, %s, %s, %s,
                'Referência operacional interna para demonstração',
                'demo_reference_internal',
                'draft',
                'Valores iniciais para demonstrar cálculo de economia; substituir após validação formal da gestão pública.'
            )
            ON CONFLICT (sigtap_code)
            DO UPDATE SET
                sigtap_name = EXCLUDED.sigtap_name,
                public_cost = CASE
                    WHEN procedure_cost_references.source = 'demo_reference_internal'
                    THEN EXCLUDED.public_cost
                    ELSE procedure_cost_references.public_cost
                END,
                private_reference = CASE
                    WHEN procedure_cost_references.source = 'demo_reference_internal'
                    THEN EXCLUDED.private_reference
                    ELSE procedure_cost_references.private_reference
                END,
                reference_label = CASE
                    WHEN procedure_cost_references.source = 'demo_reference_internal'
                    THEN EXCLUDED.reference_label
                    ELSE procedure_cost_references.reference_label
                END,
                notes = CASE
                    WHEN procedure_cost_references.source = 'demo_reference_internal'
                    THEN EXCLUDED.notes
                    ELSE procedure_cost_references.notes
                END,
                updated_at = NOW()
            """,
            (code, name, public_cost, private_reference)
        )

    for nome, latitude, longitude in municipio_coordinates:
        execute(
            """
            INSERT INTO territorial_locations (
                scope, municipio_id, latitude, longitude, source, accuracy, notes
            )
            SELECT 'municipio', m.id, %s, %s, 'kelvins/municipios-brasileiros',
                   'centroide municipal',
                   'Coordenada inicial de município para mapa epidemiológico; pode ser refinada manualmente.'
            FROM municipios m
            WHERE m.nome = %s
              AND NOT EXISTS (
                  SELECT 1
                  FROM territorial_locations tl
                  WHERE tl.scope = 'municipio'
                    AND tl.municipio_id = m.id
              )
            """,
            (latitude, longitude, nome)
        )
