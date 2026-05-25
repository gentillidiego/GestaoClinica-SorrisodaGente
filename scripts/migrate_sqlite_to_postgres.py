"""
Script de migração único: SQLite → PostgreSQL
Execute APENAS uma vez, com PostgreSQL vazio e aplicação parada.

Pré-requisitos:
    - DATABASE_PATH apontando para o clinica.db
    - DATABASE_URL apontando para o PostgreSQL (ex: postgresql://clinica_user:senha@localhost:5432/clinica)
    - PostgreSQL rodando e schema já criado (rode init_db() antes ou use este script completo)

Uso:
    cd /home/diego/projetos/GestaoClinica
    python scripts/migrate_sqlite_to_postgres.py
"""
import sqlite3
import psycopg2
import os
import sys
from dotenv import load_dotenv

load_dotenv()

SQLITE_PATH = os.getenv('DATABASE_PATH', 'clinica.db')
POSTGRES_URL = os.getenv('DATABASE_URL')

if not POSTGRES_URL:
    print("❌ DATABASE_URL não definida no .env")
    sys.exit(1)

if not os.path.exists(SQLITE_PATH):
    print(f"❌ Arquivo SQLite não encontrado: {SQLITE_PATH}")
    sys.exit(1)

# Ordem correta respeitando chaves estrangeiras
TABLES_ORDER = [
    'users',
    'patients',
    'anamnesis',
    'exams',
    'exam_fisico',
    'exam_odontograma',
    'exam_controle_placa',
    'exam_periograma',
    'atendimentos',
    'planos_tratamento',
    'tratamento_procedimentos',
    'prosthesis',
    'prosthesis_etapas',
    'prosthesis_pagamentos',
    'endodontia',
    'endodontia_canais',
    'endodontia_followup',
    'receituarios',
    'atestados',
    'patient_tcle',
]

def migrate():
    print("=== Migração SQLite → PostgreSQL ===\n")

    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    pg_conn = psycopg2.connect(POSTGRES_URL)

    total_migrated = 0

    for table in TABLES_ORDER:
        try:
            rows = sqlite_conn.execute(f"SELECT * FROM {table}").fetchall()
        except sqlite3.OperationalError:
            print(f"[SKIP] {table}: tabela não existe no SQLite")
            continue

        if not rows:
            print(f"[SKIP] {table}: sem registros")
            continue

        cols = list(rows[0].keys())
        col_names = ', '.join(cols)
        placeholders = ', '.join(['%s'] * len(cols))

        with pg_conn.cursor() as cur:
            count = 0
            for row in rows:
                try:
                    cur.execute(
                        f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
                        [row[c] for c in cols]
                    )
                    count += 1
                except Exception as e:
                    pg_conn.rollback()
                    print(f"  ⚠️  Erro ao inserir em {table}: {e}")
                    break
            else:
                pg_conn.commit()
        print(f"[OK] {table}: {count} registros migrados")
        total_migrated += count

    # Resetar sequences do PostgreSQL após migração (crítico!)
    print("\nResetando sequences de auto-increment...")
    with pg_conn.cursor() as cur:
        for table in TABLES_ORDER:
            try:
                cur.execute(f"""
                    SELECT setval(
                        pg_get_serial_sequence('{table}', 'id'),
                        COALESCE((SELECT MAX(id) FROM {table}), 1)
                    )
                """)
            except Exception as e:
                print(f"  ⚠️  Sequence de {table}: {e}")
    pg_conn.commit()

    sqlite_conn.close()
    pg_conn.close()

    print(f"\n✅ Migração concluída! Total: {total_migrated} registros migrados.")
    print("PRÓXIMO PASSO: Adicione DATABASE_URL ao .env e faça 'docker compose up -d --build'")

if __name__ == '__main__':
    migrate()
