"""
Script de diagnóstico do ambiente — GestaoSaudeOral.
Valida variáveis obrigatórias, conexão PostgreSQL, conexão Redis
e permissão de escrita no diretório pdf_temp.

Uso:
    python scripts/check_env.py
    # ou dentro do container:
    docker compose run --rm gestaoclinica python scripts/check_env.py
"""
import os
import sys

# ─── Carrega .env se existir ────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

errors = []
warnings = []

print("=" * 60)
print("  Diagnóstico de Ambiente — GestaoSaudeOral")
print("=" * 60)

# ─── 1. Variáveis obrigatórias ──────────────────────────────────────────
REQUIRED = ["SECRET_KEY", "DATABASE_URL", "REDIS_URL", "POSTGRES_PASSWORD"]
OPTIONAL = ["ADMIN_USERNAME", "ADMIN_PASSWORD"]

print("\n[1] Variáveis de Ambiente")
for var in REQUIRED:
    val = os.getenv(var)
    if val:
        masked = val[:6] + "***" if len(val) > 6 else "***"
        print(f"  ✅ {var} = {masked}")
    else:
        print(f"  ❌ {var} — NÃO DEFINIDA")
        errors.append(f"{var} não definida")

for var in OPTIONAL:
    val = os.getenv(var)
    if val:
        print(f"  ✅ {var} = ***")
    else:
        print(f"  ⚠️  {var} — não definida (necessária para create_admin.py)")
        warnings.append(f"{var} não definida")

# ─── 2. Conexão PostgreSQL ──────────────────────────────────────────────
print("\n[2] Conexão PostgreSQL")
db_url = os.getenv("DATABASE_URL")
if db_url:
    try:
        import psycopg2
        conn = psycopg2.connect(db_url, connect_timeout=5)
        cur = conn.cursor()
        cur.execute("SELECT version()")
        version = cur.fetchone()[0]
        cur.close()
        conn.close()
        print(f"  ✅ Conectado — {version[:50]}...")
    except Exception as e:
        print(f"  ❌ Falha na conexão: {e}")
        errors.append(f"PostgreSQL: {e}")
else:
    print("  ⏭️  Pulando — DATABASE_URL não definida")

# ─── 3. Conexão Redis ───────────────────────────────────────────────────
print("\n[3] Conexão Redis")
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
try:
    import redis
    r = redis.from_url(redis_url, socket_connect_timeout=5)
    pong = r.ping()
    print(f"  ✅ Redis respondeu PONG ({redis_url})")
except Exception as e:
    print(f"  ❌ Falha na conexão: {e}")
    errors.append(f"Redis: {e}")

# ─── 4. Diretório pdf_temp ──────────────────────────────────────────────
print("\n[4] Diretório pdf_temp")
pdf_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pdf_temp")
if not os.path.exists(pdf_dir):
    print(f"  ⚠️  Diretório não existe: {pdf_dir}")
    warnings.append("pdf_temp não existe")
else:
    test_file = os.path.join(pdf_dir, ".write_test")
    try:
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        print(f"  ✅ Escrita OK em {pdf_dir}")
    except Exception as e:
        print(f"  ❌ Sem permissão de escrita: {e}")
        errors.append(f"pdf_temp não gravável: {e}")

# ─── Resultado Final ────────────────────────────────────────────────────
print("\n" + "=" * 60)
if errors:
    print(f"  ❌ FALHOU — {len(errors)} erro(s) encontrado(s):")
    for err in errors:
        print(f"     • {err}")
    if warnings:
        print(f"\n  ⚠️  {len(warnings)} aviso(s):")
        for w in warnings:
            print(f"     • {w}")
    print("=" * 60)
    sys.exit(1)
else:
    if warnings:
        print(f"  ⚠️  OK com {len(warnings)} aviso(s):")
        for w in warnings:
            print(f"     • {w}")
    else:
        print("  ✅ Ambiente 100% saudável!")
    print("=" * 60)
    sys.exit(0)
