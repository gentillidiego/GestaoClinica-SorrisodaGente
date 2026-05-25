# Documentação de Arquitetura e Engenharia: Gestão Saúde Oral (Sorriso da Gente)

Este documento centraliza as diretrizes arquiteturais, a mecânica da base de dados e os principais motores lógicos em execução no sistema. Ele é um guia definitivo para desenvolvedores e IAs assumirem a manutenção, o debug e a expansão responsável da aplicação.

---

## 1. Visão Geral da Arquitetura e Stack

A aplicação é monolítica, prioriza estabilidade e deploy simples via Docker Compose com Nginx reverso.

*   **Linguagem Core:** Python 3.11
*   **Web Framework:** Flask 3.x rodando sobre Gunicorn (WSGI, worker class `gevent`). O `app.py` implementa `ProxyFix` para lidar com proxies reversos do Nginx.
*   **Banco de Dados:** **PostgreSQL 16** (via `psycopg2` com pool de conexões `ThreadedConnectionPool`). **Não há ORM.** Todas as queries são RAW SQL através dos helpers de `database.py`. Placeholders usam o padrão psycopg2: `%s`.
*   **Tarefas Assíncronas:** **Celery** com broker **Redis 7**. Usado para geração de PDFs em background (WeasyPrint). A task está em `tasks/pdf_tasks.py`.
*   **Front-End:** Renderização _Server-Side_ (SSR) com **Jinja2**. Elementos interativos (Modais, Signatures de Canvas, Tabs) utilizam JavaScript Vanilla.
*   **Estilização:** CSS3 puro com variáveis nativas HSL no `:root`.
*   **Autenticação e Segurança:** `flask_login` + `Flask-WTF` (proteção CSRF) + `Flask-Limiter` (rate limiting via Redis).
*   **Geração de PDFs:** `WeasyPrint` — conversão de templates HTML para PDF A4. Rotas síncronas usam WeasyPrint direto; geração pesada usa a task Celery `generate_pdf_task`.

---

## 2. Variáveis de Ambiente Obrigatórias

Copie `.env.example` para `.env` e preencha antes de subir os containers:

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `SECRET_KEY` | ✅ | Chave secreta Flask para sessões e CSRF |
| `DATABASE_URL` | ✅ | URL PostgreSQL — `postgresql://clinica_user:SENHA@postgres:5432/clinica` |
| `POSTGRES_PASSWORD` | ✅ | Senha do PostgreSQL (usada pelo container `postgres`) |
| `REDIS_URL` | ✅ | URL Redis — `redis://redis:6379/0` |
| `ADMIN_USERNAME` | ⚠️ Para criação do admin | Usuário do admin inicial |
| `ADMIN_PASSWORD` | ⚠️ Para criação do admin | Senha do admin inicial |

> **Nota:** `.env` nunca deve ser commitado. O `.gitignore` já o exclui.

---

## 3. Arquitetura Docker (Containers)

| Container | Tecnologia | Função | Porta |
|-----------|-----------|--------|-------|
| `gestaosaudeoral-web` | Flask + Gunicorn (gevent) | Servidor web principal | `5003` (host) |
| `gestaosaudeoral-postgres` | PostgreSQL 16 | Banco de dados persistente | `5433` (host) |
| `gestaosaudeoral-redis` | Redis 7 | Broker Celery + Rate Limiting + Cache | — |
| `gestaosaudeoral-celery` | Celery Worker | Geração assíncrona de PDFs | — |

**Volumes compartilhados:**
- `pdf_temp_oral` — compartilhado entre `web` e `celery-worker`. O web grava o HTML source e o worker escreve o PDF gerado.
- `postgres_data_oral` — dados persistentes do PostgreSQL.
- `redis_data_oral` — AOF persistência do Redis.

**Healthchecks:** `redis` e `postgres` possuem healthchecks. O `web` e o `celery-worker` só sobem após ambos estarem saudáveis (`condition: service_healthy`).

### Comandos de Deploy

```bash
# Primeira execução / após mudanças de código, templates ou static:
docker compose up -d --build

# Criar admin inicial (execute após o primeiro up):
docker compose run --rm gestaoclinica python create_admin.py

# Ver logs do web:
docker logs gestaosaudeoral-web -f

# Ver logs do Celery:
docker logs gestaosaudeoral-celery -f

# Verificar saúde do ambiente:
docker compose run --rm gestaoclinica python scripts/check_env.py
```

> ⚠️ **Alterações em código Python, templates ou static exigem sempre `docker compose up -d --build`** para serem refletidas no container. Não há bind mount de código em produção.

---

## 4. Padrões de Banco de Dados (`database.py`)

A interação com o banco usa `psycopg2.pool.ThreadedConnectionPool` com `RealDictCursor` — todas as linhas retornam como dicionários Python (`row['campo']`).

### 4.1. Funções Core

*   `query(sql, params, one=False)` — SELECT. `one=True` retorna um único dict ou `None`.
*   `execute(sql, params)` — INSERT/UPDATE/DELETE. Retorna o `id` se o SQL incluir `RETURNING id`.
*   `execute_returning(sql, params)` — INSERT com `RETURNING id` automático.
*   `execute_transaction(statements)` — Lista de `(sql, params)` em uma única transação atômica.

### 4.2. Placeholders

Usar **sempre `%s`** como placeholder (padrão psycopg2). **Nunca usar `?`** (SQLite).

```python
# ✅ Correto
query("SELECT * FROM patients WHERE id = %s", (patient_id,))

# ❌ Errado (SQLite)
query("SELECT * FROM patients WHERE id = ?", (patient_id,))
```

### 4.3. Datas PostgreSQL

PostgreSQL retorna campos `TIMESTAMP` como objetos `datetime.datetime` Python — **não como strings**. Templates Jinja devem usar filtros para formatação:

```jinja2
{# ✅ Correto #}
{{ consulta.data_consulta | format_datetime }}
{{ consulta.data_consulta.strftime('%d/%m/%Y') }}

{# ❌ Errado — quebra com datetime objects #}
{{ data[:10] }}
{{ data.split('-')[0] }}
```

### 4.4. NoSQL Dinâmico no SQL

Para estruturas transientes (lista de remédios, Odontograma de 32 dentes), campos são `TEXT` com `json.dumps()`/`json.loads()`. Templates usam `name="campo[]"` resolvidos com `request.form.getlist('campo[]')`.

---

## 5. Topologia dos Módulos (Blueprints)

| Blueprint | Função |
|-----------|--------|
| `auth.py` | Login, logout, gestão de sessão |
| `admin.py` | RBAC, cadastro de usuários |
| `patients.py` | Rota principal `/view/<id>` — carrega todos os dados do paciente |
| `exams.py` | Sub-exames (Físico, Placa, Odontograma, Periograma) |
| `prosthesis.py` | Fluxo de próteses (etapas, pagamentos) |
| `documents.py` | Exportação PDF (WeasyPrint + Celery) |
| `agenda.py` | Agenda semanal de consultas |

---

## 6. Motores Lógicos e Regras de Negócio Cruciais

### 6.1. Bloqueio Obrigatório de TCLE
Nenhum aluno ou professor pode iniciar triagem sem que a tabela `patient_tcle` esteja preenchida para o paciente. A `/view/<id>` verifica isso e desabilita funcionalidades no DOM caso o TCLE esteja ausente.

### 6.2. Autorização de Nível de Professor (Trancamento de Laudo)
Operações de peso pericial ficam como rascunho até um `professor` ou `admin` clicar em **"Validar"**, confirmando com senha. O `timestamp` de `data_validacao` bloqueia edições posteriores.

### 6.3. Regras do Plano de Tratamento e Evolução Clínica
1. Sessões numeradas sequencialmente por `criado_em`.
2. Ao assinar, professor importa o procedimento para Evolução Clínica com status `Concluido`.
3. **Tríplice Assinatura** na Evolução: Aluno + Paciente (signature_pad) + Professor.
4. Data do atendimento só é gerada na última assinatura.

### 6.4. Motor de Diagnóstico Periodontal (AAP 2018)
- Detecção de Periodontite por PIC >= 1mm em qualquer sítio interproximal.
- Estadiamento (I–IV) por pior PIC interproximal + modificadores de complexidade.
- Extensão: Localizada < 30% / Generalizada >= 30% dos dentes afetados.
- Grau (A/B/C): determinado por Regex na Anamnese (diabetes, tabagismo).

### 6.5. Geração de PDF (WeasyPrint)
*   **Regra de Solidez:** Todo PDF em `templates/pdfs` deve usar `display: table`, margens rígidas e fontes seguras do sistema (Arial, Helvetica). Evitar Flexbox avançado e web-fonts externas.
*   **Exceção Periograma:** Usa `html2pdf.js` client-side para preservar os CSS Sprites do diagrama periodontal.
*   **Geração Assíncrona:** `tasks.pdf_tasks.generate_pdf_task` gera PDF via Celery e salva em `/app/pdf_temp/`.

---

## 7. RBAC — Hierarquia de Papéis

| Role | Capacidades |
|------|------------|
| `admin` | Acesso total, cadastros, remoções, validações |
| `professor` | Valida laudos, fecha diagnósticos, autoriza procedimentos |
| `aluno` | Inserção clínica operacional, sem encerramento |
| `atendimento` | Edição cadastral parcial, sem histórico restrito |

---

## 8. Práticas para Manutenção

1. **Migrações de Schema:** Não há Alembic. Para novos campos, usar `_ensure_columns_exist()` em `database.py` — ela verifica antes de executar o `ALTER TABLE`, evitando erro em produção.
2. **Mutações JavaScript:** O Odontograma armazena estados de cores em inputs ocultos via JS. Alterações no template exigem atenção à sincronização JS ↔ Form.
3. **Datas em Templates:** Sempre usar `datetime.strftime()` ou filtro Jinja antes de manipular. PostgreSQL retorna `datetime`, não `str`.
4. **Diagnóstico do Ambiente:** Executar `scripts/check_env.py` após qualquer mudança de configuração.
