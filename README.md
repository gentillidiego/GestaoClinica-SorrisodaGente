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
- **Módulo de Triagem Municipal** — Criação de ações por município e geração de senhas por especialidade no formato `ARA-P-001`
- **Agenda Semanal** — Controle de consultas com badges de status e vinculação paciente/dentista
- **Dashboard Gerencial** — Métricas de produtividade e taxa de conclusão de agendamentos
- **Segurança** — Rate limiting integrado e isolamento de dados via PostgreSQL

## 🎫 Fluxo de Triagem Municipal

O módulo de triagem organiza as grandes ações realizadas nos municípios de Alagoas e cria senhas físicas para iniciar o atendimento especializado em Maceió.

### Dinâmica operacional
1. A equipe cria uma **Ação de Triagem** informando município, data, local e observações.
2. Dentro da ação, o operador seleciona uma especialidade e gera **uma senha por vez**.
3. A senha entregue ao paciente usa o formato `MUN-ESP-000`.
4. Após gerar, o sistema exibe um popup grande com a senha para o operador anotar e entregar ao paciente.
5. No cadastro do paciente, a primeira informação é a **Senha de Triagem**, mas o campo é opcional.
6. Quando preenchida, a senha fica vinculada ao prontuário e a especialidade aparece em destaque no cabeçalho do paciente.
7. Quando o paciente é cadastrado sem senha, o sistema exibe um aviso relevante informando que a senha e a especialidade de encaminhamento não constarão no prontuário.

### Exemplos de senhas
| Senha | Origem | Especialidade |
|---|---|---|
| `ARA-P-001` | Arapiraca | Prótese Dentária |
| `PEN-END-001` | Penedo | Endodontia |
| `MCZ-I-001` | Maceió | Implantodontia |
| `UDP-ORT-001` | União dos Palmares | Ortodontia |

### Especialidades cadastradas
- Prótese Dentária (`P`)
- Implantodontia (`I`)
- Dentística (`D`)
- Ortodontia (`ORT`)
- Endodontia (`END`)
- Periodontia (`PER`)
- Cirurgia e Traumatologia Buco-Maxilo-Facial (`CTBMF`)
- Odontopediatria (`ODP`)
- Estética (`EST`)

### Regra de numeração
A sequência é única por **município + especialidade**. Assim, `ARA-P-001` identifica uma senha de prótese de Arapiraca, enquanto `PEN-P-001` identifica uma senha de prótese de Penedo, sem conflito operacional.

## 🔧 Comandos Úteis

### Iniciar o sistema
```bash
docker compose up -d
```

### Rebuild completo
> ⚠️ **Obrigatório após alterações em código Python ou dependências.**
> Em desenvolvimento via `docker-compose.yml`, `templates/` e `static/` são montados como volumes e normalmente atualizam sem rebuild.
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
