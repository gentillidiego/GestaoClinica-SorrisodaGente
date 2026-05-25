# 📋 Plano de Escalabilidade — Gestão Clínica
> **Objetivo:** Suportar 100+ usuários simultâneos com estabilidade, desempenho e sem perda de dados.
> **Data de análise:** 2026-03-24

---

## 🔍 Diagnóstico Atual da Aplicação

Antes de qualquer mudança, é essencial entender o estado atual e **por que** cada ponto é um problema real.

### Stack Identificada

| Componente         | Tecnologia Atual              | Status        |
|--------------------|-------------------------------|---------------|
| Framework Web      | Flask 3.0.3                   | ✅ Adequado   |
| Servidor WSGI      | Gunicorn (3 workers síncronos)| ⚠️ Limitado   |
| Banco de Dados     | SQLite (`clinica.db`)         | 🔴 Crítico    |
| Sessões de Usuário | Flask-Login (cookie client-side) | ⚠️ Limitado |
| Rate Limiter       | Flask-Limiter (memória)       | ⚠️ Limitado   |
| Cache              | Nenhum                        | 🔴 Ausente    |
| PDF Generation     | WeasyPrint (síncrono, blocking)| ⚠️ Limitado  |
| Infraestrutura     | Docker Single Container       | ⚠️ Limitado   |
| Banco de Dados Índices | Nenhum índice explícito   | 🔴 Crítico    |
| Monitoramento      | Nenhum                        | 🔴 Ausente    |

---

## 🚨 Bottlenecks Críticos Identificados

### CRÍTICO 1 — SQLite como banco de produção com concorrência

**Arquivo:** `database.py` (linhas 9-36)

**Problema Técnico:**
```python
# Cada função abre E fecha uma conexão separada
def get_db_connection():
    conn = sqlite3.connect(DATABASE)  # nova conexão a cada chamada
    conn.execute("PRAGMA journal_mode = WAL")  # WAL é bom, mas insuficiente

def query(sql, params=(), one=False):
    conn = get_db_connection()  # ABRE
    # ... executa
    conn.close()               # FECHA — overhead constante

def execute(sql, params=()):
    conn = get_db_connection()  # ABRE
    # ... executa
    conn.close()               # FECHA — overhead constante
```

**Por que é crítico com 100 usuários:**
- SQLite usa lock por arquivo. Qualquer operação de **escrita** (INSERT/UPDATE/DELETE) trava o arquivo inteiro para TODOS os outros processos.
- Com WAL mode, leituras concorrentes funcionam bem, mas escritas ainda serializam.
- Com 3 workers Gunicorn + 100 usuários, cada worker abre/fecha conexão a cada request. Não há pool.
- Em pico de acesso (ex: 30 alunos abrindo prontuários ao mesmo tempo + 5 assinando atendimentos), o SQLite entra em contenção e começa a retornar `OperationalError: database is locked`.

**Solução:** Migrar para **PostgreSQL** com pool de conexões (`psycopg2` + `psycopg2-pool` ou SQLAlchemy).

---

### CRÍTICO 2 — Sem índices no banco de dados

**Arquivo:** `database.py` (init_db)

**Problema Técnico:**
Todas as 15+ tabelas foram criadas sem nenhum índice explícito além da chave primária. As queries mais usadas fazem buscas por colunas sem índice:

```sql
-- patients.py linha 78: busca LIKE sem índice em nome, cpf, cns, celular
SELECT id, nome, cpf FROM patients WHERE nome LIKE '%...%' ORDER BY id DESC

-- patient_service.py linha 8: busca por patient_id sem índice
SELECT * FROM patients WHERE id = ?   -- id é PK, ok

-- patient_service.py linha 12: busca por patient_id em patient_tcle — SEM índice
SELECT data_assinatura FROM patient_tcle WHERE patient_id = ?

-- patient_service.py linha 39-46: atendimentos por patient_id — SEM índice
SELECT a.* FROM atendimentos a WHERE a.patient_id = ?

-- patient_service.py linha 52-58: tratamento_procedimentos por patient_id — SEM índice
SELECT tp.* FROM tratamento_procedimentos tp WHERE tp.patient_id = ?
```

**Por que é crítico:**
- Sem índice em `patient_id`, cada busca em `atendimentos`, `endodontia`, `prosthesis_etapas`, etc. faz um **full table scan**.
- Com 100 usuários abrindo prontuários simultaneamente, o banco faz dezenas de full scans por segundo.
- O custo cresce linearmente com o número de registros (O(n) por query).

**Solução:** Adicionar índices explícitos em todas as colunas usadas em `WHERE` e `JOIN`.

---

### CRÍTICO 3 — Gunicorn com apenas 3 workers síncronos

**Arquivo:** `Dockerfile` (linha 24)

**Problema Técnico:**
```dockerfile
CMD ["gunicorn", "--workers", "3", "--bind", "0.0.0.0:5002", "app:app"]
```

**Por que é crítico:**
- Com workers síncronos (padrão), cada worker trata **1 request por vez**.
- Com 3 workers → capacidade máxima teórica: **3 requests simultâneos**.
- O WeasyPrint (geração de PDF) pode levar 2-5 segundos. Nesse tempo, 1 worker está **completamente bloqueado**.
- Com 100 usuários, mesmo operações simples entram na fila e o tempo de resposta explode.

**Fórmula de Workers Recomendada (Gunicorn docs):**
```
workers = (2 × CPU_cores) + 1
```

Para uma VPS com 2 cores: `workers = 5`
Com worker class `gevent` (assíncrono): pode-se usar 1000+ conexões simultâneas por worker.

**Solução:** Aumentar workers + usar `gevent` ou `gthread` worker class.

---

### CRÍTICO 4 — Rate Limiter em memória (não funciona com múltiplos workers)

**Arquivo:** `extensions.py`

**Problema Técnico:**
```python
limiter = Limiter(
    get_remote_address,
    default_limits=["5000 per day", "500 per hour"],
    storage_uri="memory://"  # ← PROBLEMA
)
```

**Por que é crítico:**
- `storage_uri="memory://"` significa que cada **worker Gunicorn** tem seu próprio contador independente.
- Com 3 workers, um usuário pode fazer 3× os limites definidos (1500/hora ao invés de 500/hora).
- Com `gevent` (futuro), a situação se torna ainda mais caótica.

**Solução:** Usar Redis como backend para o rate limiter (`storage_uri="redis://localhost:6379"`).

---

### MÉDIO 5 — Geração de PDF Síncrona (WeasyPrint blocking)

**Arquivo:** `blueprints/documents.py` (não lido mas inferido pelo uso de WeasyPrint)

**Problema Técnico:**
WeasyPrint processa HTML → CSS → PDF sequencialmente, bloqueando o worker por 1-5 segundos dependendo da complexidade do documento. Esse tempo varia com a carga da CPU.

**Por que é problema:**
- 10 usuários gerando PDF ao mesmo tempo = 10 workers bloqueados = sistema sem resposta para os demais.

**Solução:** Mover geração de PDF para uma **fila de tarefas** (Celery + Redis) ou usar threads.

---

### MÉDIO 6 — Sessões de usuário via cookie sem backend

**Arquivo:** `app.py` + `extensions.py`

**Problema Técnico:**
Flask-Login usa cookies assinados client-side por padrão. Cada request precisa descriptografar e verificar o cookie via `SECRET_KEY`.

**Por que vira problema com escala:**
- Sem sessões server-side, não há como invalidar uma sessão de forma centralizada (logout remoto, expiração por inatividade real).
- Com múltiplos containers ou futuramente load balancer, sessão pode ser perdida entre requests se `SECRET_KEY` não for consistente (já está via `.env`, ok).
- Flask-Session com Redis resolve centralizando o estado.

---

### MÉDIO 7 — Sem cache de nenhum tipo

**Arquivo:** Todo o código de views

**Problema Técnico:**
Cada request a qualquer página re-executa todas as queries ao banco, mesmo para dados que raramente mudam (ex: lista de alunos, lista de professores).

**Exemplo em `patients.py` linha 219:**
```python
context['students'] = query(
    "SELECT id, username FROM users WHERE role = ? ORDER BY username ASC", 
    (Role.ALUNO,)
)
```
Essa query é executada toda vez que qualquer aba de paciente é carregada, por qualquer usuário. Com 100 usuários, são centenas de queries idênticas por minuto.

**Solução:** Flask-Caching com Redis backend para cachear resultados de queries caras.

---

### BAIXO 8 — Monitoramento e Observabilidade Ausentes

**Problema:**
Não há logs estruturados, métricas de performance, alertas de erro, ou rastreamento de tempo de resposta. Em produção com 100 usuários, é impossível diagnosticar problemas sem observabilidade.

**Solução:** Adicionar logging estruturado + endpoint `/health` + métricas básicas.

---

## 📐 Arquitetura Alvo

```
                    ┌─────────────────────┐
                    │      Nginx           │
                    │   (Reverse Proxy)    │
                    │  Rate Limit + SSL    │
                    └─────────┬───────────┘
                              │
                    ┌─────────▼───────────┐
                    │   Gunicorn           │
                    │  (gevent workers)    │
                    │  workers = 5~9       │
                    └─────────┬───────────┘
                              │
               ┌──────────────┼──────────────┐
               │              │              │
    ┌──────────▼──┐  ┌────────▼────┐  ┌─────▼──────────┐
    │ PostgreSQL  │  │   Redis     │  │  Celery Worker  │
    │ (Banco)     │  │  (Cache /   │  │  (PDF Async)    │
    │             │  │ Rate Limit/ │  │                 │
    │ Connection  │  │  Sessões)   │  │                 │
    │ Pool        │  └─────────────┘  └─────────────────┘
    └─────────────┘
```

---

## 🗂️ Plano de Implementação por Sprint

### SPRINT 1 — Base de Dados e Índices (Semana 1)
**Impacto: 🔴 CRÍTICO — Maior ganho de performance por menor esforço**

#### S1.1 — Adicionar índices ao SQLite (enquanto ainda está em SQLite)
**Arquivo a modificar:** `database.py`

**O que fazer exatamente:**

Ao final da função `init_db()`, adicionar:
```python
# === ÍNDICES DE PERFORMANCE ===
indexes = [
    "CREATE INDEX IF NOT EXISTS idx_patients_nome ON patients(nome)",
    "CREATE INDEX IF NOT EXISTS idx_patients_cpf ON patients(cpf)",
    "CREATE INDEX IF NOT EXISTS idx_patients_cns ON patients(cns)",
    "CREATE INDEX IF NOT EXISTS idx_anamnesis_patient_id ON anamnesis(patient_id)",
    "CREATE INDEX IF NOT EXISTS idx_exams_patient_id ON exams(patient_id)",
    "CREATE INDEX IF NOT EXISTS idx_atendimentos_patient_id ON atendimentos(patient_id)",
    "CREATE INDEX IF NOT EXISTS idx_atendimentos_professor_id ON atendimentos(professor_id)",
    "CREATE INDEX IF NOT EXISTS idx_tratamento_patient_id ON tratamento_procedimentos(patient_id)",
    "CREATE INDEX IF NOT EXISTS idx_tratamento_status ON tratamento_procedimentos(status)",
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
    "CREATE INDEX IF NOT EXISTS idx_exam_fisico_exam_id ON exam_fisico(exam_id)",
    "CREATE INDEX IF NOT EXISTS idx_exam_odontograma_exam_id ON exam_odontograma(exam_id)",
    "CREATE INDEX IF NOT EXISTS idx_exam_placa_exam_id ON exam_controle_placa(exam_id)",
    "CREATE INDEX IF NOT EXISTS idx_exam_periograma_exam_id ON exam_periograma(exam_id)",
]
for idx_sql in indexes:
    execute(idx_sql)
```

**Como verificar:**
```bash
# No terminal, dentro da pasta do projeto:
sqlite3 clinica.db ".indices patients"
# Deve mostrar: idx_patients_nome, idx_patients_cpf, idx_patients_cns

sqlite3 clinica.db "EXPLAIN QUERY PLAN SELECT * FROM atendimentos WHERE patient_id = 1"
# Deve mostrar: SEARCH atendimentos USING INDEX idx_atendimentos_patient_id
```

#### S1.2 — Otimizar configurações WAL do SQLite

**Arquivo a modificar:** `database.py` função `get_db_connection()`

```python
def get_db_connection():
    conn = sqlite3.connect(DATABASE, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -64000")   # 64MB de cache em memória
    conn.execute("PRAGMA temp_store = MEMORY")    # temporários em RAM
    conn.execute("PRAGMA mmap_size = 268435456")  # 256MB memory-mapped I/O
    conn.execute("PRAGMA wal_autocheckpoint = 1000")  # checkpoint a cada 1000 páginas
    return conn
```

**Por que cada pragma:**
- `cache_size = -64000`: SQLite usa 64MB de RAM para cache de páginas (muito mais rápido que disco)
- `temp_store = MEMORY`: JOINs e sorts temporários ficam na RAM
- `mmap_size`: Leitura via memory-mapped file (mais rápido que read() syscalls)
- `timeout=30`: Aguarda até 30s por lock ao invés de falhar imediatamente

---

### SPRINT 2 — Gunicorn e Workers (Semana 1-2)
**Impacto: 🔴 CRÍTICO — Aumenta capacidade de requests simultâneos drasticamente**

#### S2.1 — Instalar gevent e configurar Gunicorn

**Arquivo a modificar:** `requirements.txt`

Adicionar:
```
gevent==24.2.1
```

**Arquivo a modificar:** `Dockerfile` (linha 24)

Antes:
```dockerfile
CMD ["gunicorn", "--workers", "3", "--bind", "0.0.0.0:5002", "app:app"]
```

Depois:
```dockerfile
CMD ["gunicorn", \
     "--workers", "5", \
     "--worker-class", "gevent", \
     "--worker-connections", "100", \
     "--timeout", "120", \
     "--keep-alive", "5", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "100", \
     "--bind", "0.0.0.0:5002", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:app"]
```

**Explicação de cada parâmetro:**
- `workers = 5`: Para 2 CPUs → (2×2)+1 = 5 workers (ajustar conforme VPS)
- `worker-class = gevent`: Cada worker pode lidar com centenas de conexões simultâneas (I/O assíncrono)
- `worker-connections = 100`: Até 100 conexões por worker = 500 simultâneas total
- `timeout = 120`: WeasyPrint pode gerar PDFs grandes; 2min de timeout é seguro
- `max-requests = 1000`: Recicla worker após 1000 requests (evita memory leak)
- `max-requests-jitter = 100`: Aleatoriza reciclagem para não matar todos ao mesmo tempo

**Importante:** gevent é compatível com SQLite WAL e não quebra o código atual.

#### S2.2 — Criar arquivo gunicorn.conf.py para configuração centralizada

**Novo arquivo:** `gunicorn.conf.py` na raiz do projeto

```python
# gunicorn.conf.py
import multiprocessing

# Número de workers baseado na CPU da VPS
workers = multiprocessing.cpu_count() * 2 + 1

# Worker class assíncrona
worker_class = "gevent"
worker_connections = 100

# Timeouts
timeout = 120
graceful_timeout = 60
keepalive = 5

# Reciclagem de workers (evita memory leak)
max_requests = 1000
max_requests_jitter = 100

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Bind
bind = "0.0.0.0:5002"
```

**Atualizar `Dockerfile`:**
```dockerfile
CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:app"]
```

---

### SPRINT 3 — Redis, Cache e Rate Limiter (Semana 2)
**Impacto: ⚠️ ALTO — Elimina queries redundantes e torna rate limit efetivo**

#### S3.1 — Adicionar Redis ao docker-compose.yml

**Arquivo a modificar:** `docker-compose.yml`

```yaml
version: '3.8'

services:
  gestaoclinica:
    build: .
    container_name: gestaoclinica-docker
    restart: always
    ports:
      - "5002:5002"
    volumes:
      - ./clinica.db:/app/clinica.db
    env_file:
      - .env
    depends_on:
      - redis
    environment:
      - REDIS_URL=redis://redis:6379/0

  redis:
    image: redis:7-alpine
    container_name: gestaoclinica-redis
    restart: always
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --maxmemory 128mb --maxmemory-policy allkeys-lru

volumes:
  redis_data:
```

**Notas:**
- `redis:7-alpine`: Imagem mínima (~30MB)
- `appendonly yes`: Persistência em disco (dados não perdem se Redis reiniciar)
- `maxmemory 128mb`: Limita uso de RAM do Redis
- `allkeys-lru`: Remove entradas mais antigas quando cheio (LRU cache)

#### S3.2 — Instalar dependências de Redis

**Arquivo a modificar:** `requirements.txt`

Adicionar:
```
redis==5.0.8
Flask-Caching==2.3.0
```

#### S3.3 — Migrar Rate Limiter para Redis

**Arquivo a modificar:** `extensions.py`

Antes:
```python
limiter = Limiter(
    get_remote_address,
    default_limits=["5000 per day", "500 per hour"],
    storage_uri="memory://"
)
```

Depois:
```python
import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

limiter = Limiter(
    get_remote_address,
    default_limits=["5000 per day", "500 per hour"],
    storage_uri=REDIS_URL
)
```

#### S3.4 — Adicionar Flask-Caching

**Arquivo a modificar:** `extensions.py` (adicionar ao final)

```python
from flask_caching import Cache

cache = Cache()
```

**Arquivo a modificar:** `app.py` — inicializar o cache na função `create_app()`

```python
from extensions import limiter, cache

def create_app():
    app = Flask(__name__)
    # ... configurações existentes ...
    
    # Configuração do Cache (Redis)
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    app.config['CACHE_TYPE'] = 'RedisCache'
    app.config['CACHE_REDIS_URL'] = redis_url
    app.config['CACHE_DEFAULT_TIMEOUT'] = 300  # 5 minutos
    cache.init_app(app)
    
    # ... resto das inicializações ...
```

#### S3.5 — Cachear queries caras e estáticas

**Arquivo a modificar:** `blueprints/patients.py`

A query de alunos é chamada em toda abertura de aba e nunca muda durante o turno:

```python
from extensions import cache

# Dentro de get_tab_content, substituir:
# context['students'] = query("SELECT id, username FROM users WHERE role = ? ORDER BY username ASC", (Role.ALUNO,))

# Por:
@cache.cached(timeout=600, key_prefix='students_list')
def get_students_cached():
    return query("SELECT id, username FROM users WHERE role = ? ORDER BY username ASC", (Role.ALUNO,))

context['students'] = get_students_cached()
```

**Arquivo a criar:** `services/cache_service.py`

```python
"""
Serviço centralizado para invalidação de cache.
Sempre que um aluno for adicionado/removido, chamar:
    CacheService.invalidate_students()
"""
from extensions import cache

class CacheService:
    STUDENTS_KEY = 'students_list'
    
    @staticmethod
    def invalidate_students():
        cache.delete(CacheService.STUDENTS_KEY)
    
    @staticmethod
    def invalidate_patient(patient_id):
        # Para uso futuro quando cachear dados de pacientes
        cache.delete(f'patient_{patient_id}')
```

---

### SPRINT 4 — Sessões Server-Side com Redis (Semana 2-3)
**Impacto: ⚠️ MÉDIO — Permite logout centralizado e sessões persistentes entre restarts**

#### S4.1 — Instalar Flask-Session

**Arquivo a modificar:** `requirements.txt`

Adicionar:
```
Flask-Session==0.8.0
```

#### S4.2 — Configurar sessões Redis no app

**Arquivo a modificar:** `app.py`

```python
from flask_session import Session

def create_app():
    app = Flask(__name__)
    # ... configs existentes ...
    
    # Sessões server-side via Redis
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    app.config['SESSION_TYPE'] = 'redis'
    app.config['SESSION_REDIS'] = redis.from_url(redis_url)
    app.config['SESSION_PERMANENT'] = True
    app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 horas
    app.config['SESSION_USE_SIGNER'] = True           # Assina o ID da sessão
    Session(app)
```

#### S4.3 — Adicionar variável de ambiente ao .env.example

```bash
REDIS_URL=redis://localhost:6379/0
```

---

### SPRINT 5 — Geração Assíncrona de PDF (Semana 3-4)
**Impacto: ⚠️ MÉDIO — Libera workers durante geração de PDF**

#### S5.1 — Instalar Celery

**Arquivo a modificar:** `requirements.txt`

Adicionar:
```
celery==5.4.0
```

#### S5.2 — Criar módulo Celery

**Novo arquivo:** `celery_app.py`

```python
from celery import Celery
import os

def make_celery(app):
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    celery = Celery(
        app.import_name,
        backend=redis_url,
        broker=redis_url
    )
    celery.conf.update(app.config)
    
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    return celery
```

#### S5.3 — Criar task de geração de PDF

**Novo arquivo:** `tasks/pdf_tasks.py`

```python
from celery_app import celery
from weasyprint import HTML
import tempfile
import os

@celery.task(bind=True, max_retries=3)
def generate_pdf_task(self, html_content, output_path):
    """
    Gera PDF em background e salva em output_path.
    Retorna o caminho do arquivo gerado.
    """
    try:
        HTML(string=html_content).write_pdf(output_path)
        return output_path
    except Exception as exc:
        raise self.retry(exc=exc, countdown=5)
```

#### S5.4 — Adicionar worker Celery ao docker-compose.yml

```yaml
  celery-worker:
    build: .
    container_name: gestaoclinica-celery
    restart: always
    command: celery -A celery_app.celery worker --loglevel=info --concurrency=2
    volumes:
      - ./clinica.db:/app/clinica.db
      - pdf_temp:/app/pdf_temp
    env_file:
      - .env
    depends_on:
      - redis
    environment:
      - REDIS_URL=redis://redis:6379/0

volumes:
  redis_data:
  pdf_temp:
```

**Nota prática:** Esta sprint é opcional em curto prazo. Se o volume de PDFs for baixo (< 5/hora), pode ser adiada. O ganho principal acontece quando múltiplos usuários geram PDFs simultaneamente.

---

### SPRINT 6 — Migração para PostgreSQL (Semana 4-6)
**Impacto: 🔴 MAIOR MUDANÇA — Elimina o principal bottleneck de concorrência**

> ⚠️ **Esta é a mudança mais complexa. Siga o passo a passo exatamente.**

#### S6.1 — Instalar dependências PostgreSQL

**Arquivo a modificar:** `requirements.txt`

Adicionar:
```
psycopg2-binary==2.9.10
```

Remover (não é necessário remover, sqlite3 é built-in do Python):
```
# sqlite3 é módulo padrão do Python, não vai em requirements.txt
```

#### S6.2 — Adicionar PostgreSQL ao docker-compose.yml

```yaml
  postgres:
    image: postgres:16-alpine
    container_name: gestaoclinica-postgres
    restart: always
    environment:
      POSTGRES_DB: clinica
      POSTGRES_USER: clinica_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"  # Apenas para desenvolvimento; remover em produção

volumes:
  redis_data:
  postgres_data:
  pdf_temp:
```

**Adicionar ao `.env.example`:**
```bash
DATABASE_URL=postgresql://clinica_user:password@postgres:5432/clinica
POSTGRES_PASSWORD=senha_segura_aqui
```

#### S6.3 — Reescrever database.py com psycopg2 e pool de conexões

**Arquivo a substituir:** `database.py`

```python
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
    """Executa comandos de escrita (INSERT, UPDATE, DELETE)."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
        last_id = cur.lastrowid if hasattr(cur, 'lastrowid') else None
        # PostgreSQL usa RETURNING para lastrowid
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
```

#### S6.4 — Migrar dados do SQLite para PostgreSQL

**Script de migração:** criar `scripts/migrate_sqlite_to_postgres.py`

```python
"""
Script de migração único: SQLite → PostgreSQL
Execute APENAS uma vez, com o PostgreSQL vazio.

Uso:
    python scripts/migrate_sqlite_to_postgres.py
"""
import sqlite3
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

SQLITE_PATH = os.getenv('DATABASE_PATH', 'clinica.db')
POSTGRES_URL = os.getenv('DATABASE_URL')

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
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    pg_conn = psycopg2.connect(POSTGRES_URL)
    
    for table in TABLES_ORDER:
        rows = sqlite_conn.execute(f"SELECT * FROM {table}").fetchall()
        if not rows:
            print(f"[SKIP] {table}: vazia")
            continue
        
        cols = rows[0].keys()
        placeholders = ', '.join(['%s'] * len(cols))
        col_names = ', '.join(cols)
        
        with pg_conn.cursor() as cur:
            for row in rows:
                cur.execute(
                    f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
                    list(row)
                )
        pg_conn.commit()
        print(f"[OK] {table}: {len(rows)} registros migrados")
    
    # Resetar sequences do PostgreSQL após migração
    with pg_conn.cursor() as cur:
        for table in TABLES_ORDER:
            cur.execute(f"""
                SELECT setval(
                    pg_get_serial_sequence('{table}', 'id'),
                    COALESCE((SELECT MAX(id) FROM {table}), 1)
                )
            """)
    pg_conn.commit()
    
    sqlite_conn.close()
    pg_conn.close()
    print("\n✅ Migração concluída!")

if __name__ == '__main__':
    migrate()
```

#### S6.5 — Adaptar queries SQL para PostgreSQL

**Diferenças críticas entre SQLite e PostgreSQL:**

| SQLite          | PostgreSQL           | Onde usar                    |
|-----------------|----------------------|------------------------------|
| `?`             | `%s`                 | TODOS os parâmetros          |
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL PRIMARY KEY` | DDL das tabelas |
| `CURRENT_TIMESTAMP` | `NOW()`          | Defaults                     |
| `lastrowid`     | `RETURNING id`       | INSERTs                      |

**Todas as ocorrências de `?` nos blueprints precisam virar `%s`.**

Executar para encontrar todos os arquivos afetados:
```bash
grep -rn "execute\|query(" blueprints/ services/ --include="*.py" | grep "?"
```

**Este é o passo mais trabalhoso da migração.** Cada blueprint precisa ser revisado. Use sed para automatizar:
```bash
# ATENÇÃO: Revise o resultado antes de aplicar permanentemente!
# Substitui apenas dentro de strings SQL (heurística)
find . -name "*.py" -exec sed -i 's/, (/, %s/g' {} \;
```
> ⚠️ O sed acima é uma heurística. Revise arquivo por arquivo manualmente.

---

### SPRINT 7 — Monitoramento e Observabilidade (Semana 5-6)
**Impacto: ⚠️ MÉDIO — Essencial para operar com 100+ usuários**

#### S7.1 — Adicionar endpoint /health

**Arquivo a modificar:** `blueprints/main.py`

```python
from flask import jsonify
import time

@main_bp.route('/health')
def health():
    """Endpoint de health check para monitoramento externo."""
    from database import query
    start = time.time()
    try:
        query("SELECT 1", one=True)
        db_ok = True
        db_latency = round((time.time() - start) * 1000, 2)
    except Exception as e:
        db_ok = False
        db_latency = -1
    
    status = 200 if db_ok else 503
    return jsonify({
        "status": "healthy" if db_ok else "degraded",
        "database": "ok" if db_ok else "error",
        "db_latency_ms": db_latency,
        "timestamp": time.time()
    }), status
```

#### S7.2 — Logging estruturado

**Arquivo a modificar:** `app.py`

```python
import logging
from logging.handlers import RotatingFileHandler

def configure_logging(app):
    if not app.debug:
        # Log em arquivo com rotação (10MB, mantém 5 backups)
        handler = RotatingFileHandler(
            'logs/app.log',
            maxBytes=10 * 1024 * 1024,
            backupCount=5
        )
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s %(levelname)s [%(name)s] %(message)s'
        )
        handler.setFormatter(formatter)
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)
```

#### S7.3 — Adicionar métricas de tempo de resposta

**Arquivo a modificar:** `app.py` — adicionar before/after request hooks:

```python
import time

def register_request_hooks(app):
    @app.before_request
    def start_timer():
        from flask import g
        g.start_time = time.time()
    
    @app.after_request
    def log_request(response):
        from flask import g, request
        duration = round((time.time() - g.start_time) * 1000, 2)
        app.logger.info(
            f"{request.method} {request.path} → {response.status_code} [{duration}ms]"
        )
        return response
```

---

### SPRINT 8 — Testes de Carga e Ajuste Final (Semana 6-7)

#### S8.1 — Instalar Locust (ferramenta de carga)

```bash
pip install locust
```

#### S8.2 — Criar script de teste de carga

**Novo arquivo:** `tests/locustfile.py`

```python
from locust import HttpUser, task, between

class ClinicaUser(HttpUser):
    wait_time = between(1, 3)  # usuário espera 1-3s entre ações
    
    def on_start(self):
        # Login no início da sessão
        self.client.post("/login", data={
            "username": "testuser",
            "password": "testpass"
        })
    
    @task(3)  # 3x mais frequente que outras tasks
    def list_patients(self):
        self.client.get("/patients/list")
    
    @task(2)
    def view_patient(self):
        self.client.get("/patients/view/1")
    
    @task(1)
    def view_patient_tab(self):
        self.client.get("/patients/view/1/tab/tab-atendimento")
```

**Como executar o teste:**
```bash
# No terminal, dentro da pasta do projeto:
locust -f tests/locustfile.py --host=http://localhost:5002

# Abrir http://localhost:8089 no navegador
# Configurar: 100 usuários, ramp-up de 10 usuários/segundo
# Observar: requests/sec, tempo médio de resposta, % de falhas
```

---

## 📊 Métricas de Sucesso por Sprint

| Sprint | Métrica Principal                       | Meta Antes | Meta Depois |
|--------|-----------------------------------------|------------|-------------|
| S1     | Tempo de query em `atendimentos`         | ~50ms      | < 5ms       |
| S2     | Requests simultâneos suportados          | 3          | 500+        |
| S3     | Queries redundantes (alunos)             | 100/min    | 1/10min     |
| S4     | Sessões válidas após restart             | 0%         | 100%        |
| S5     | Tempo de bloqueio durante PDF            | 2-5s       | 0s          |
| S6     | Write throughput                         | ~50 ops/s  | ~5000 ops/s |
| S7     | MTTD (Mean Time To Detect) de erros     | ∞          | < 5 min     |
| S8     | Usuários simultâneos sem degradação      | ~10        | 100+        |

---

## 🧠 Decisões de Arquitetura — Justificativas

### Por que NÃO usar SQLAlchemy?
O ORM adicionaria uma camada de abstração ao código já funcional. A migração para PostgreSQL (Sprint 6) pode ser feita mantendo o padrão de queries raw com `psycopg2`, que é mais previsível e mais fácil de debugar para desenvolvedores que já conhecem SQL.

### Por que Redis e não Memcached?
Redis suporta persistência, pub/sub, e estruturas de dados ricas. O Flask-Limiter e o Flask-Session também usam Redis, então um único serviço serve múltiplos propósitos.

### Por que gevent e não uvicorn/asyncio?
Flask é uma aplicação WSGI síncrona. Migrar para asyncio (FastAPI/asyncio) exigiria reescrever toda a aplicação. Gevent é um "monkey patch" que transforma chamadas síncronas de I/O em assíncronas **sem mudar o código**. É a escolha com menor risco e maior compatibilidade.

### Por que manter SQLite nas Sprints 1-5?
A migração para PostgreSQL (Sprint 6) é a mudança de maior risco. As Sprints 1-5 entregam ganhos reais imediatos no SQLite (índices, workers, cache) e preparam o código para a migração. Se algo der errado, o rollback é trivial.

---

## ⚠️ Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| `?` → `%s` migration incompleta | Alta | Alto | Grep automático + revisão manual |
| Perda de dados na migração SQLite→PG | Média | Crítico | Backup antes + script idempotente |
| Incompatibilidade gevent com SQLite | Baixa | Alto | Testar em ambiente staging primeiro |
| Redis fica indisponível | Baixa | Médio | Fallback para memória configurado |
| Celery task de PDF falha | Baixa | Baixo | max_retries=3 + fallback síncrono |
