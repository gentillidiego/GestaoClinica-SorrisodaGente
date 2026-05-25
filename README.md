# Gestão Saúde Oral - Programa Sorriso da Gente

Plataforma de gestão clínica e acompanhamento de saúde bucal, integrando um sistema administrativo robusto com uma Landing Page institucional moderna voltada ao programa "Sorriso da Gente". Utiliza Python/Flask, PostgreSQL e Celery para oferecer agendamento, prontuários digitais e geração de documentos clínicos.

## 🌐 Landing Page Institucional

Página pública disponível em [https://sorrisodagentealagoas.com](https://sorrisodagentealagoas.com), servindo como vitrine do programa com design moderno, responsivo e animado.

### Seções
- **Hero** — Tagline institucional, call-to-action e card com logo do programa animado
- **Estatísticas** — +50 mil pacientes, 9 etapas, 100% gratuito, +20 procedimentos
- **Sobre o Programa** — Missão, citação institucional e destaques do programa
- **Como Funciona** — 9 etapas do fluxo de atendimento (da UBS à alta com dignidade)
- **Serviços** — Atenção Básica, Diagnóstico Avançado e Clínica Restauradora
- **CTA** — Acesso direto ao sistema de gestão
- **Rodapé** — Navegação, contato e suporte técnico

### Design e UX
- Identidade visual com paleta oficial: azul `#002D73`, laranja `#FF6A00`, amarelo `#FFC124`
- Totalmente responsivo: mobile (480px), tablet (768px) e desktop
- Menu hamburguer para dispositivos móveis
- Navegação com efeito glassmorphism ao scrollar
- Animações de entrada via IntersectionObserver (fade + slide-up)
- Orbs animados no hero com gradiente dinâmico
- Card da logo com efeito flutuante
- Hover interativo nos cards de etapas e serviços

## 🐳 Arquitetura e Deploy (Docker)

O sistema opera em uma arquitetura de microsserviços via Docker Compose:

| Container | Tecnologia | Função | Porta |
|---|---|---|---|
| `gestaosaudeoral-web` | Flask + Gevent | Servidor web principal | `5003` |
| `gestaosaudeoral-postgres` | PostgreSQL 16 | Banco de dados persistente | `5433` (host) |
| `gestaosaudeoral-redis` | Redis 7 | Broker de mensagens + Rate Limiting | — |
| `gestaosaudeoral-celery` | Celery Worker | Geração assíncrona de PDFs | — |

## 🌟 Funcionalidades Clínicas (Painel Administrativo)

Acessível via `/dashboard` após login:

- **Módulo de Exames de Imagem** — Galeria com upload em lote e visualização em tela cheia
- **Agenda Semanal** — Controle de consultas com badges de status e vinculação paciente/dentista
- **Dashboard Gerencial** — Métricas de produtividade e taxa de conclusão de agendamentos
- **Segurança** — Rate limiting integrado e isolamento de dados via PostgreSQL

## 🔧 Comandos Úteis

### Iniciar o sistema
```bash
docker compose up -d
```

### Rebuild completo
> ⚠️ **Obrigatório após qualquer alteração em código Python, templates ou static.**
```bash
docker compose up -d --build
```

### Criar o admin inicial
```bash
# Defina ADMIN_USERNAME e ADMIN_PASSWORD no .env antes de executar
docker compose run --rm gestaoclinica python create_admin.py
```

### Diagnóstico do ambiente
```bash
docker compose run --rm gestaoclinica python scripts/check_env.py
```

### Visualizar logs
```bash
docker logs gestaosaudeoral-web -f
docker logs gestaosaudeoral-celery -f
```

## ⚙️ Variáveis de Ambiente Obrigatórias

Copie `.env.example` para `.env` e preencha antes de subir:

| Variável | Descrição |
|----------|-----------|
| `SECRET_KEY` | Chave secreta Flask — gere com `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | URL PostgreSQL — `postgresql://clinica_user:SENHA@postgres:5432/clinica` |
| `POSTGRES_PASSWORD` | Senha do PostgreSQL |
| `REDIS_URL` | URL Redis — `redis://redis:6379/0` |
| `ADMIN_USERNAME` | Usuário do admin (para `create_admin.py`) |
| `ADMIN_PASSWORD` | Senha do admin (para `create_admin.py`) |

## 📝 Acessos

- **Landing Page:** [https://sorrisodagentealagoas.com](https://sorrisodagentealagoas.com)
- **Painel Administrativo:** `/dashboard`
- **Banco de Dados (host):** porta `5433`

---
&copy; 2026 Programa Sorriso da Gente. Todos os direitos reservados.
