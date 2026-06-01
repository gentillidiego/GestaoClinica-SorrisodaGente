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

O sistema opera em uma arquitetura moderna e resiliente de microsserviços via Docker Compose, utilizando volumes nomeados dedicados para isolamento e segurança máxima (LGPD-compliant), livre de permissões de bind mounts locais do host:

| Container | Tecnologia | Função | Porta |
|---|---|---|---|
| `gestaosaudeoral-web` | Flask + Gevent | Servidor web principal | `5003` |
| `gestaosaudeoral-postgres` | PostgreSQL 16 | Banco de dados persistente | `5433` (host) |
| `gestaosaudeoral-redis` | Redis 7 | Broker de mensagens + Rate Limiting | — |
| `gestaosaudeoral-celery` | Celery Worker | Geração assíncrona de PDFs | — |

### Volumes Nomeados Persistentes
* `redis_data_oral` — Cache, sessões rápidas de usuários e broker de tarefas Celery.
* `pdf_temp_oral` — Diretório isolado para processamento temporário de PDFs gerados pelo WeasyPrint.
* `postgres_data_oral` — Base PostgreSQL isolada (incluindo prontuários e triagem).
* `logs_oral` — Histórico estruturado de logs do servidor web e worker.
* `uploads_oral` — Armazenamento seguro de exames radiológicos e fotos clínicas de lesões bucais (Módulo de Estomatologia).
* `backups_oral` — Retenção local dos backups operacionais gerados pelo script de contingência.

> ⚠️ **Importante:** Os templates e arquivos estáticos fazem parte da **imagem Docker** (não há bind mount). Qualquer alteração em `templates/` ou `static/` exige rebuild obrigatório com `docker compose up -d --build`.

## 🌟 Funcionalidades Clínicas (Painel Administrativo)

Acessível via `/dashboard` após login:

- **Módulo de Exames de Imagem** — Galeria com upload em lote e visualização em tela cheia
- **Módulo de Triagem Municipal** — Criação de ações por município e geração de senhas por especialidade no formato `ARA-P-001`
- **Agenda Semanal** — Controle de consultas com badges de status e vinculação paciente/dentista
- **Dashboard Gerencial** — Métricas de produtividade e taxa de conclusão de agendamentos
- **Central de Comando** — Painel operacional em `/command-center` com pacientes do dia, fila inteligente, alertas, bairros, especialidades e produção
- **Epidemiologia** — Painel inicial em `/epidemiologia` com indicadores por bairro, lesões, suspeitas oncológicas, absenteísmo, demanda reprimida e perfil demográfico
- **BI Executivo** — Painel em `/bi` com produção, filas, impacto social, metas automáticas, comparativos mensais e rankings executivos
- **Relatórios Institucionais** — Prévia, geração assíncrona de PDF, histórico e recortes Institucional/SSA/SMS em `/reports/institutional`
- **Linha do Tempo do Paciente** — Rastreabilidade inicial por prontuário reunindo cadastro, triagem, agenda, exames, procedimentos, documentos, estomatologia, fotos clínicas e auditoria
- **Auditoria Administrativa** — Tela com filtros de logs por usuário, módulo, ação, paciente e status
- **Segurança** — Rate limiting integrado (20 logins/hora por IP) e isolamento de dados via PostgreSQL
- **🚨 Módulo de Estomatologia (Câncer de Boca)** — Ficha clínica especializada, evolução fotográfica de lesões, Fila Vermelha de regulação oncológica e Encaminhamento Expresso em PDF
- **Dados Demonstrativos (CLI)** — Rotina técnica sem frontend para criar pacientes fictícios completos, com anamnese, TCLE, exames, plano de tratamento, agenda, estomatologia, prótese e produção SIGTAP/e-SUS pronta para demonstrações.

## 🚨 Módulo de Estomatologia — Câncer de Boca

Módulo clínico dedicado ao rastreamento, documentação e regulação prioritária de casos suspeitos de neoplasia bucal. Acessível na aba **"🚨 Estomatologia"** dentro de cada prontuário.

### Funcionalidades

**Ficha Clínica Especializada**
- Localização anatômica da lesão, tamanho estimado, características clínicas detalhadas
- Hábitos de risco do paciente (tabagismo, etilismo), tempo de evolução
- Hipótese diagnóstica e conduta clínica adotada
- Checkbox de encaminhamento formal para biópsia/cirurgia

**Alerta Vermelho (🚨 Suspeita de Neoplasia)**
- Ao ativar, o paciente é imediatamente sinalizado em vermelho em todas as listas do sistema
- Entrada automática na **Fila Vermelha de Regulação** (`/patients/red-alerts`)
- O dashboard exibe o contador de casos ativos e acesso direto à fila

**Evolução Fotográfica de Lesões**
- Upload de fotos com legenda e categorização temporal ("Antes do tratamento", "Evolução 2 semanas", etc.)
- Galeria visual tipo grade com modal de zoom em tela cheia
- Exclusão individual de fotos com confirmação

**Encaminhamento Expresso (PDF)**
- Gerado via WeasyPrint + Celery com processamento assíncrono (~0.5s)
- Inclui: banner de ALERTA VERMELHO, dados do paciente, dados clínicos da lesão, município de origem (via senha de triagem) e campo de assinatura da responsável clínica
- Botão disponível diretamente na ficha clínica do prontuário

### Rotas disponíveis

| Rota | Método | Descrição |
|---|---|---|
| `/patients/<id>/estomatologia/save` | POST | Salva ou atualiza a ficha clínica |
| `/patients/<id>/estomatologia/photo/upload` | POST | Upload de foto da lesão (JPG/PNG/WEBP) |
| `/patients/<id>/estomatologia/photo/<photo_id>/delete` | POST | Exclusão de foto |
| `/patients/red-alerts` | GET | Fila Vermelha de regulação oncológica |
| `/documents/<patient_id>/estomatologia/<est_id>/pdf` | GET | Geração do PDF de encaminhamento |

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
> ⚠️ **Obrigatório após qualquer alteração em código Python, templates HTML ou arquivos estáticos.**
```bash
docker compose up -d --build
```

### Criar o admin inicial
```bash
# Defina ADMIN_USERNAME e ADMIN_PASSWORD no .env antes de executar
ADMIN_USERNAME=admin ADMIN_PASSWORD=senha_segura docker compose run --rm gestaoclinica python create_admin.py
```

### Diagnóstico do ambiente
```bash
docker compose run --rm gestaoclinica python scripts/check_env.py
```

### Verificar saúde do sistema
```bash
curl http://localhost:5003/health
# Esperado: {"status": "healthy", "database": "ok", ...}
```

### Povoar dados fictícios para demonstração
```bash
# Cria até 100 pacientes fictícios por execução.
# Todos ficam marcados com is_demo=TRUE e a execução é registrada em demo_seed_runs.
docker compose exec -T gestaoclinica flask --app app:app seed-demo-data --count 100 --label "Demonstração institucional"
```

### Visualizar logs
```bash
docker logs gestaosaudeoral-web -f
docker logs gestaosaudeoral-celery -f
```

### Backup operacional
```bash
docker compose run --rm gestaoclinica python scripts/backup_postgres.py
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
| `BACKUP_DIR` | Diretório de saída dos backups operacionais |
| `BACKUP_RETENTION_DAYS` | Dias de retenção dos backups locais |

## 📌 Regra Permanente de Documentação do Projeto

Este `README.md` é a **fonte primária do projeto**. Ele deve funcionar ao mesmo tempo como:

- guia de desenvolvimento;
- guia de implantação;
- memória técnica das decisões tomadas;
- base para a futura documentação institucional;
- base para os manuais de uso por perfil: recepção, triagem, clínica, auditoria, BI, gestão e demais módulos.

### Instrução obrigatória para encerramento de fase ou sessão

Sempre que uma **fase for concluída**, uma **sessão de desenvolvimento for terminada** ou uma entrega relevante for validada, este README deve ser atualizado antes do encerramento do trabalho.

O registro deve conter, no mínimo:

- data da atualização;
- fase afetada;
- objetivo da sessão ou entrega;
- funcionalidades implementadas;
- arquivos, rotas, serviços, tabelas ou templates impactados;
- testes executados e resultado;
- validações manuais realizadas;
- pendências, riscos e próximos passos;
- observações úteis para construção futura de documentação e manuais de uso;
- decisões de produto, regra de negócio ou segurança tomadas durante a sessão.

### Como registrar

- Marcar itens do roadmap como `[x]` apenas quando estiverem implementados e testados.
- Usar `🟡` ou texto de "parcial" quando a base técnica existir, mas ainda faltar hardening, cobertura completa ou integração externa.
- Nunca registrar senhas, chaves, tokens, dados sensíveis reais de pacientes ou credenciais.
- Quando uma funcionalidade tiver impacto no treinamento da equipe, adicionar uma observação de manual, explicando o que o usuário final precisará aprender.
- Quando houver teste, registrar o comando e o resultado esperado.
- Quando houver pendência, registrar de forma objetiva o que falta para encerrar o requisito.

## 🚀 Roadmap de Expansão & Acompanhamento de Status

Acompanhe abaixo o progresso do desenvolvimento da expansão tecnológica acordada para o ecossistema do **Sorriso da Gente**.

---

### **Fase 0: MVP de Alta Urgência — 🟢 CONCLUÍDO E VALIDADO** *(Entregue em 29/05/2026)*

> ✅ **Todos os itens implementados, testados e validados em ambiente de produção (Docker).**
> Validação técnica realizada em 29/05/2026 com testes de integração end-to-end.

- [x] **Módulo Clínico de Estomatologia (Câncer de Boca):**
  - [x] Prontuário focado em lesões bucais (localização anatômica, tamanho, características clínicas, hábitos de risco e tempo de evolução).
  - [x] Tabelas `estomatologia` e `estomatologia_fotos` criadas no PostgreSQL com índices de busca otimizados.
  - [x] Aba "🚨 Estomatologia" integrada ao prontuário com lazy loading e TCLE como pré-requisito.
- [x] **Evolução Fotográfica (Lesões):**
  - [x] Upload seguro de fotos com validação de extensão (JPG/PNG/WEBP) e armazenamento no volume `uploads_oral`.
  - [x] Galeria visual com legenda, data, modal de zoom em tela cheia e exclusão individual por foto.
- [x] **Fila de Prioridade Clínica (Alerta Vermelho):**
  - [x] Checkbox "Suspeita de Neoplasia" ativa o alerta imediatamente na listagem geral de pacientes.
  - [x] Tela dedicada `/patients/red-alerts` com tabela priorizada por data de registro.
  - [x] Dashboard exibe contador de casos ativos e link direto para a fila.
- [x] **Encaminhamento Expresso (PDF):**
  - [x] Geração assíncrona via Celery + WeasyPrint com tempo médio de ~0.5s.
  - [x] Documento inclui banner de ALERTA VERMELHO, dados clínicos completos e campo de assinatura.
  - [x] Botão de geração disponível diretamente na ficha clínica do prontuário.

---

### **Fase 1: Segurança, LGPD, Perfis de Acesso, Logs e Continuidade — 🟡 BASE IMPLEMENTADA / HARDENING PENDENTE** *(Revisada em 30/05/2026)*

> Objetivo: preparar a base jurídica, operacional e técnica antes da expansão dos módulos clínicos e gerenciais.
> Status atual: base funcional entregue e validada por testes automatizados. Ainda existem pendências de criptografia forte, assinatura digital formal, política avançada de retenção e redundância em nuvem.

#### Entregas implementadas

- [x] **Matriz de perfis de acesso**
  - [x] Papéis definidos em `constants.py`: recepção, triagem, clínica geral, dentista, endodontia, cirurgia, implantes, estomatologia, radiologia, laboratório, financeiro, auditoria, epidemiologia, BI, comunicação, mutirão móvel, TSB/ASB, atendente legado e administrador.
  - [x] Permissões estruturadas por módulo: pacientes, triagem, agenda, exames, documentos, estomatologia, radiologia, laboratório, financeiro, relatórios, BI, epidemiologia, auditoria, usuários e Central de Comando.
  - [x] Helper `current_user.can(...)` disponível para menus, botões e ações condicionais.
  - [x] Decorator `permission_required(...)` disponível para proteger rotas sensíveis.
- [x] **Auditoria operacional inicial**
  - [x] Serviço `services/security_service.py` com `audit_log(...)`, captura de usuário, papel, ação, módulo, entidade, paciente, IP, user-agent, método, rota, status e detalhes em JSON.
  - [x] Tabela `audit_logs` criada na inicialização do banco.
  - [x] Registro de login, logout, falhas de login, acesso negado, criação/edição/exclusão de usuários e eventos de agenda.
  - [x] Tela administrativa de auditoria com filtros por usuário, módulo, ação, paciente e status.
- [x] **Continuidade e backup operacional**
  - [x] Script `scripts/backup_postgres.py` para dump PostgreSQL em formato custom.
  - [x] Backup complementar do diretório `uploads`, quando existente.
  - [x] Retenção local configurável por `BACKUP_RETENTION_DAYS`.
  - [x] Volume Docker `backups_oral` previsto para armazenamento local dos backups.
- [x] **Validação técnica da fase**
  - [x] Pytest instalado no ambiente de desenvolvimento.
  - [x] Testes automatizados cobrindo permissões, auditoria e base de segurança.

#### Pendências da Fase 1

- [ ] **LGPD Ready completo**
  - [ ] Criptografia robusta para dados sensíveis em repouso, incluindo prontuários, exames, fotos clínicas, laudos e documentos.
  - [ ] Política formal de retenção e descarte de uploads clínicos.
  - [ ] Bloqueio completo de acesso direto a arquivos sem autenticação e autorização por perfil.
  - [ ] Registro estruturado de consentimento com versionamento de termo, aceite, revogação e responsável.
- [ ] **Auditoria plena**
  - [ ] Ampliar cobertura para todos os módulos clínicos: prontuário, fotos, exames, laudos, documentos, triagem, filas, relatórios, alterações de prioridade e alta clínica.
  - [ ] Incluir filtro por período, IP e severidade na tela administrativa.
  - [ ] Registrar eventos de visualização sensível, não apenas alterações.
- [ ] **Assinatura digital**
  - [ ] Implementar assinatura eletrônica/digital para prontuários, laudos, consentimentos, relatórios, auditorias e documentos institucionais.
  - [ ] Definir integração ICP-Brasil/A3/Nuvem, Gov.br ou alternativa institucional aceita.
  - [ ] Registrar hash do documento assinado, carimbo de data/hora e autoria.
- [ ] **Recuperação rápida**
  - [ ] Automatizar rotina diária de backup.
  - [ ] Replicar backups em nuvem com redundância e criptografia.
  - [ ] Documentar e testar procedimento de restauração, com meta de RPO/RTO.

#### Observações para manuais futuros

- Manual de administração deve explicar criação de usuários, escolha de perfil, impacto de permissões e consulta à auditoria.
- Manual LGPD deve explicar que todo acesso sensível será rastreado, incluindo usuário, IP, data/hora e módulo.
- Manual técnico deve documentar o comando de backup, local de retenção e procedimento de restauração.

---

### **Fase 2: Operação Clínica, Fila Inteligente, Alertas e Rastreabilidade — 🟢 PRIMEIRA VERSÃO CONCLUÍDA E VALIDADA** *(Revisada em 30/05/2026)*

> Objetivo: criar a primeira base operacional para gestão diária da clínica, priorização automática da fila, alertas críticos e rastreabilidade do paciente.
> Status atual: primeira versão implementada, revisada e validada com testes automatizados e renderização autenticada em Docker.

#### Entregas implementadas

- [x] **Central de Comando Operacional**
  - [x] Rota `/command-center` protegida por permissão `command_center:view`.
  - [x] Cards de pacientes do dia, produção diária/mensal, status da agenda, alerta vermelho, tratamentos pendentes e alertas críticos.
  - [x] Painéis de bairros atendidos, fila por especialidade, agenda do dia e ranking de prioridade.
  - [x] Menu e acesso condicionados por perfil.
- [x] **Inteligência de Fila do SUS**
  - [x] Primeira versão do algoritmo de prioridade automática para pacientes oncológicos, idosos, faltosos, tratamentos pendentes e lesões suspeitas sem retorno.
  - [x] Ranking inicial de urgência na Central de Comando (`/command-center`) com pontuação, nível de risco e motivos clínicos.
  - [x] Revisão técnica contra contagem duplicada de faltas e tratamentos pendentes em joins SQL.
  - [x] Uso da ficha mais recente de estomatologia para cálculo do risco atual.
  - [x] Lesão suspeita sem retorno considera retorno somente após a data do registro da lesão.
- [x] **Sistema de alertas operacionais**
  - [x] Alertas para paciente com 2 faltas, lesão suspeita sem retorno, fila crítica, alerta vermelho oncológico e tratamentos pendentes.
  - [x] Alertas da Central de Comando calculados sobre a fila completa, mesmo quando a tela exibe apenas o top 12.
  - [x] Indicador de faltas integrado ao status `Faltou` da agenda.
- [x] **Agenda com falta operacional**
  - [x] Status `Faltou` disponível na criação/edição/filtro visual da agenda.
  - [x] Ação rápida para marcar falta em consulta pendente ou confirmada.
  - [x] Proteção contra atualização de status em consulta inexistente.
  - [x] Auditoria de criação, edição, cancelamento e mudança de status da consulta.
- [x] **Rastreabilidade total do paciente**
  - [x] Linha do tempo inicial do acolhimento até a alta consolidando cadastro, triagem, consentimento, agenda, faltas, atendimentos, exames, tratamentos, prótese, endodontia, documentos, estomatologia, fotos clínicas e auditoria.
  - [x] Aba `Linha do Tempo` no prontuário do paciente.
  - [x] Parser de datas reforçado para formatos ISO completos e formatos brasileiros.
  - [x] Eventos de auditoria aparecem como parte da rastreabilidade do paciente.
- [x] **Validação técnica da fase**
  - [x] Testes unitários da fila, pontuação, alertas, permissões, parser de datas e rota de agenda.
  - [x] Renderização autenticada validada em Docker para `/command-center`, `/agenda/` e aba de linha do tempo.
  - [x] Health check validado em `http://localhost:5003/health`.

#### Testes executados na revisão de 30/05/2026

```bash
.venv/bin/python -m pytest -q
# Resultado: 20 passed

.venv/bin/python -m compileall services/command_center_service.py services/traceability_service.py blueprints/agenda.py
# Resultado: compilação sem erro

git diff --check
# Resultado: sem erros de whitespace

docker compose up -d --build
curl http://localhost:5003/health
# Resultado: HTTP 200, database ok
```

Validações autenticadas em Docker:

| Rota | Resultado |
|---|---|
| `/command-center` | HTTP 200 |
| `/agenda/` | HTTP 200 |
| `/patients/view/<id>/tab/tab-linha-tempo` | HTTP 200 |

#### Pendências da Fase 2

- [ ] **Evolução do algoritmo de fila**
  - [ ] Incluir diabéticos, casos agudos de dor, vulnerabilidade socioeconômica e tempo de espera por especialidade.
  - [ ] Prever demanda por especialidade, bairro, município, período e mutirão.
  - [ ] Medir redução de tempo de espera, gargalos de agenda e pacientes sem retorno.
- [ ] **Central de Comando avançada**
  - [ ] Visão por unidade, município, profissional, especialidade e período.
  - [ ] Metas automáticas por produção clínica, comparecimento, conclusão de tratamento e fila reduzida.
  - [ ] Exportação ou impressão de resumo operacional diário.
- [ ] **Alertas pendentes**
  - [ ] Implante sem pós-operatório.
  - [ ] Exame pendente.
  - [ ] Documento sem assinatura.
  - [ ] Estoque baixo, material vencendo, material vencido e perdas operacionais.
  - [ ] Centralização dos alertas também no prontuário e nos módulos responsáveis.
- [ ] **Rastreabilidade avançada**
  - [ ] Associação ao prontuário de instrumental utilizado, implante, prótese, lote, validade, fornecedor e profissional responsável.
  - [ ] Registro do pós-operatório, intercorrências, conduta e alta clínica.
  - [ ] Rastreabilidade por paciente, procedimento, material, lote, profissional e data.
- [ ] **Módulo de fotos, radiografias e rastreamento visual**
  - [ ] Organização padronizada por categoria: antes/depois, evolução, lesões, radiografias, intraoral, extraoral e documentos complementares.
  - [ ] Comparativo visual lado a lado, linha do tempo e legenda obrigatória.
  - [ ] Segurança LGPD aplicada aos arquivos, com permissão por perfil e registro de acesso.
- [ ] **Módulo Financeiro e Logístico Operacional**
  - [ ] Controle de custo por procedimento, especialidade, profissional, município e tipo de material.
  - [ ] Produtividade por equipe, cadeira, especialidade e período.
  - [ ] Estoque com entrada, saída, perdas, validade, lote, fornecedor, centro de custo e alerta automático.
  - [ ] Relatórios operacionais de perdas, consumo médio e previsão de reposição.
- [ ] **Treinamento e Implantação**
  - [ ] Capacitação da equipe operacional por meio de videoaulas, manuais rápidos em PDF e apoio presencial/híbrido.

#### Observações para manuais futuros

- Manual da recepção deve explicar como criar consulta, confirmar, marcar `Faltou`, cancelar e interpretar filtros da agenda.
- Manual da coordenação deve explicar leitura da Central de Comando: fila prioritária, motivos da pontuação, alertas críticos e produção do dia.
- Manual clínico deve explicar a Linha do Tempo como visão consolidada do histórico do paciente.
- Manual de auditoria deve explicar que mudanças de agenda e eventos relevantes aparecem na linha do tempo e nos logs administrativos.

---

### **Fase 3: Inteligência Epidemiológica, Painel Executivo (BI) e Integrações — 🟡 INICIADA** *(Sessões registradas em 30/05/2026 e 01/06/2026)*

> Objetivo: transformar os dados clínicos e operacionais já capturados pelo sistema em inteligência epidemiológica, painéis executivos e relatórios institucionais.
> Status atual: Mapa Epidemiológico v1, BI Executivo v1 e Relatórios Institucionais/SSA/SMS com automação mensal v1 implementados e validados. O painel epidemiológico ainda é territorial/tabular por bairro, sem georreferenciamento cartográfico avançado.

#### Entregas implementadas em 30/05/2026

- [x] **Mapa Epidemiológico v1**
  - [x] Rota `/epidemiologia` protegida por permissão `epidemiologia:view`.
  - [x] Menu lateral exibido apenas para perfis com acesso epidemiológico.
  - [x] Filtros por período e bairro.
  - [x] Indicadores por bairro: pacientes, lesões, suspeitas oncológicas, faltas, taxa de absenteísmo, necessidade protética e demanda reprimida.
  - [x] Síntese clínica do período: novos cadastros, lesões registradas, pacientes com lesão, suspeitas oncológicas, encaminhamentos para biópsia, necessidade protética e demanda reprimida.
  - [x] Ranking de localização anatômica das lesões.
  - [x] Demanda por especialidade com destaque para demanda reprimida.
  - [x] Perfil demográfico básico por faixa etária, gênero e profissão.
- [x] **Base técnica da epidemiologia**
  - [x] Serviço `services/epidemiology_service.py` criado para centralizar os cálculos.
  - [x] Métricas derivadas de dados reais existentes: `patients`, `estomatologia`, `consultas`, `triagem_senhas`, `especialidades` e `prosthesis`.
  - [x] Funções auxiliares para período, percentual, normalização de bairro e agrupamento demográfico.
- [x] **Validação técnica da sessão**
  - [x] Testes automatizados adicionados em `tests/test_phase3_epidemiology.py`.
  - [x] Renderização autenticada da rota `/epidemiologia` validada em Docker.
  - [x] Health check validado após rebuild.

#### Testes executados na sessão de 30/05/2026

```bash
.venv/bin/python -m pytest -q
# Resultado: 25 passed

.venv/bin/python -m compileall services/epidemiology_service.py blueprints/main.py tests/test_phase3_epidemiology.py
# Resultado: compilação sem erro

git diff --check
# Resultado: sem erros de whitespace

docker compose up -d --build
curl http://localhost:5003/health
# Resultado: HTTP 200, database ok
```

Validações autenticadas em Docker:

| Rota | Resultado |
|---|---|
| `/epidemiologia` | HTTP 200 |
| `/epidemiologia?inicio=2026-05-01&fim=2026-05-30` | HTTP 200 |

#### Entregas implementadas em 30/05/2026 — BI Executivo v1

- [x] **Serviço de BI executivo**
  - [x] Serviço `services/executive_bi_service.py` criado para centralizar os cálculos executivos.
  - [x] Resumo de produção, consultas, filas, impacto social e financeiro operacional.
  - [x] Comparação com mês anterior e cálculo de crescimento.
  - [x] Metas automáticas iniciais para produção, comparecimento e fila encaminhada.
  - [x] Comparativo mensal de seis meses.
  - [x] Rankings por profissional, bairro e especialidade.
- [x] **Tela de BI**
  - [x] Template `templates/bi_dashboard.html`.
  - [x] Rota `/bi` protegida por `bi:view`.
  - [x] Menu lateral exibido apenas para perfis autorizados.
  - [x] Filtro por período.
- [x] **Validação técnica da sessão**
  - [x] Testes automatizados adicionados em `tests/test_phase3_executive_bi.py`.
  - [x] Renderização autenticada da rota `/bi` validada em Docker.
  - [x] Health check validado após rebuild.

#### Testes executados após BI Executivo v1

```bash
.venv/bin/python -m pytest -q
# Resultado: 30 passed

.venv/bin/python -m compileall services/executive_bi_service.py blueprints/main.py tests/test_phase3_executive_bi.py
# Resultado: compilação sem erro

git diff --check
# Resultado: sem erros de whitespace

docker compose up -d --build
curl http://localhost:5003/health
# Resultado: HTTP 200, database ok
```

Validações autenticadas em Docker:

| Rota | Resultado |
|---|---|
| `/bi` | HTTP 200 |
| `/bi?inicio=2026-05-01&fim=2026-05-30` | HTTP 200 |

#### Entregas implementadas em 30/05/2026 — Relatórios Institucionais v1

- [x] **Serviço de relatório institucional**
  - [x] Serviço `services/institutional_report_service.py` criado para compor dados do BI Executivo e da Epidemiologia.
  - [x] Perfis de relatório: Institucional, SSA e SMS.
  - [x] Destaques executivos consolidados: produção, pacientes atendidos, fila encaminhada, suspeitas oncológicas, absenteísmo e bairros alcançados.
  - [x] Recomendações automáticas para demanda reprimida, absenteísmo, fila oncológica, necessidade protética, biópsias e busca ativa municipal.
  - [x] Observações institucionais sobre limitações de métricas proxy, suspeita oncológica e georreferenciamento v1.
- [x] **Prévia e PDF institucional**
  - [x] Rota `/reports/institutional` com filtros por período.
  - [x] Filtro por perfil de relatório: Institucional, SSA e SMS.
  - [x] Rota `/reports/institutional/export` para geração assíncrona via Celery + WeasyPrint.
  - [x] Template `templates/reports/institutional.html` para prévia operacional.
  - [x] Template `templates/pdfs/relatorio_institucional_pdf.html` para PDF institucional.
  - [x] Link de acesso a partir de Relatórios Gerenciais.
  - [x] Acesso de relatórios ajustado para permissão `reports:view`, não apenas `admin`.
- [x] **Histórico e automação mensal**
  - [x] Tabela `generated_reports` criada para registrar tipo, título, período, arquivo, task, usuário, status, detalhes e conclusão.
  - [x] `generate_pdf_task` atualiza o status do relatório gerado para `success` ou `failed`.
  - [x] Histórico dos PDFs gerados exibido na tela de relatório institucional.
  - [x] Script `scripts/generate_monthly_reports.py` criado para geração mensal agendável por cron/orquestrador.
  - [x] Script suporta `--type institucional`, `--type ssa`, `--type sms` e `--type all`.
- [x] **Validação técnica da sessão**
  - [x] Testes automatizados adicionados em `tests/test_phase3_institutional_report.py`.
  - [x] Prévia autenticada validada em Docker.
  - [x] POST de exportação validado com CSRF.
  - [x] Arquivo PDF gerado no volume `pdf_temp`.
  - [x] Geração mensal automatizada simulada por script.

#### Testes executados após Relatório Institucional v1

```bash
.venv/bin/python -m pytest -q
# Resultado: 36 passed

.venv/bin/python -m compileall services/institutional_report_service.py tasks/pdf_tasks.py scripts/generate_monthly_reports.py blueprints/reports_bp.py tests/test_phase3_institutional_report.py
# Resultado: compilação sem erro

git diff --check
# Resultado: sem erros de whitespace

docker compose up -d --build
curl http://localhost:5003/health
# Resultado: HTTP 200, database ok

docker compose exec -T gestaoclinica python scripts/generate_monthly_reports.py --type sms --month 2026-05
# Resultado: relatorio_sms_20260501_20260531_auto.pdf gerado com sucesso
```

Validações autenticadas em Docker:

| Rota/Ação | Resultado |
|---|---|
| `GET /reports/institutional` | HTTP 200 |
| `GET /reports/institutional?inicio=2026-05-01&fim=2026-05-30` | HTTP 200 |
| `GET /reports/institutional?tipo=ssa&inicio=2026-05-01&fim=2026-05-30` | HTTP 200 |
| `GET /reports/institutional?tipo=sms&inicio=2026-05-01&fim=2026-05-30` | HTTP 200 |
| `POST /reports/institutional/export` com tipo `ssa` | HTTP 302 para `/documents/status/...` |
| `pdf_temp/relatorio_institucional_20260501_20260530_8.pdf` | PDF gerado com sucesso |
| `pdf_temp/relatorio_ssa_20260501_20260530_8.pdf` | PDF gerado com sucesso |
| `pdf_temp/relatorio_sms_20260501_20260531_auto.pdf` | PDF automático gerado com sucesso |
| `generated_reports` | Registros `ssa` e `sms` com status `success` |

#### Entregas implementadas em 01/06/2026 — Automação Governamental de Relatórios v1

- [x] **Agendamento mensal em produção**
  - [x] Task `tasks.report_tasks.generate_monthly_reports_task` criada para gerar relatórios mensais em background.
  - [x] Celery configurado com `beat_schedule` para execução mensal automática.
  - [x] Serviço `celery-beat` adicionado ao `docker-compose.yml`, com volume persistente `celerybeat_oral`.
  - [x] Variáveis de ambiente documentadas em `.env.example`: `REPORTS_SCHEDULER_ENABLED`, `REPORTS_SCHEDULE_DAY`, `REPORTS_SCHEDULE_HOUR`, `REPORTS_SCHEDULE_MINUTE`, `REPORTS_SCHEDULE_TYPES`, `REPORTS_OUTPUT_DIR` e `TZ`.
  - [x] Script `scripts/generate_monthly_reports.py` reaproveita o mesmo serviço de geração e aceita `--force` para reprocessamento controlado.
- [x] **Serviço centralizado de geração**
  - [x] Serviço `services/report_generation_service.py` criado para consolidar parsing de mês, tipos de relatório, chave agendada, geração PDF, idempotência e retorno operacional.
  - [x] Geração automática evita duplicar relatório mensal já concluído quando executada pelo scheduler.
  - [x] Relatórios gerados ficam disponíveis no histórico seguro do painel institucional.
- [x] **Assinatura técnica e rastreabilidade do PDF**
  - [x] `generated_reports` ampliada com `signature_hash`, `signature_status`, `signed_at`, `scheduled_key` e `delivery_channel`.
  - [x] Hash SHA-256 do PDF calculado após a gravação do arquivo.
  - [x] Registro formal criado também em `digital_signatures` com `document_type='generated_report'`.
  - [x] Histórico da tela institucional exibe a assinatura/hash resumida do arquivo.
- [x] **Acesso por público/perfil governamental**
  - [x] Perfis `prefeitura`, `ssa` e `sms` adicionados à matriz de papéis.
  - [x] Prefeitura acessa relatório institucional; SSA acessa relatório SSA; SMS acessa relatório SMS.
  - [x] Perfis internos de BI, auditoria, epidemiologia e administração mantêm visão ampla conforme governança interna.
  - [x] Download de PDFs institucionais passa a validar permissão `reports:view` e o tipo de relatório registrado.
- [x] **Gráficos no PDF**
  - [x] PDF institucional recebeu gráficos renderizados por barras para produção mensal, bairros alcançados, demanda reprimida e lesões por localização.
  - [x] Gráficos usam os dados já consolidados pelo BI Executivo e Epidemiologia, sem dependência externa adicional.
- [x] **Validação técnica da sessão**
  - [x] Testes automatizados ampliados para 40 casos.
  - [x] Compilação dos módulos alterados validada.
  - [x] Checagem de whitespace validada por `git diff --check`.

#### Testes executados após Automação Governamental v1

```bash
.venv/bin/python -m pytest -q
# Resultado: 40 passed

.venv/bin/python -m compileall constants.py database.py celery_app.py services/institutional_report_service.py services/report_generation_service.py tasks/pdf_tasks.py tasks/report_tasks.py scripts/generate_monthly_reports.py blueprints/reports_bp.py blueprints/documents.py tests/test_phase3_institutional_report.py
# Resultado: compilação sem erro

git diff --check
# Resultado: sem erros de whitespace

docker compose up -d --build
curl http://localhost:5003/health
# Resultado: serviços web, worker e beat ativos; HTTP 200, database ok

docker compose exec -T gestaoclinica python scripts/generate_monthly_reports.py --type institucional --month 2026-05 --force
# Resultado: relatorio_institucional_20260501_20260531_auto.pdf gerado com hash SHA-256 registrado
```

Validações em Docker:

| Ação | Resultado |
|---|---|
| `docker compose ps` | `gestaoclinica`, `celery-worker`, `celery-beat`, `redis` e `postgres` ativos |
| `docker compose logs --tail=80 celery-beat` | Beat iniciado com sucesso |
| `generated_reports` | Registro `institucional` com `status=success`, `signature_status=hash_internal` e `delivery_channel=painel_seguro` |
| `digital_signatures` | Registro `generated_report` com provedor `sha256-internal` |
| Reexecução sem `--force` | Relatório existente detectado e não duplicado |

#### Entregas implementadas em 01/06/2026 — Prontidão SIGTAP/DataSUS e e-SUS APS

- [x] **Pesquisa técnica oficial**
  - [x] Confirmado que a Tabela de Procedimentos, Medicamentos e OPM do SUS é a referência oficial para codificação de procedimentos.
  - [x] Confirmado que o procedimento SIGTAP usa identificador numérico de 10 dígitos, estruturado por grupo, subgrupo e forma de organização.
  - [x] Confirmado que a integração futura com e-SUS APS deve seguir o LEDI APS, camada que define as informações e formatos aceitos no envio de dados de sistemas próprios para o PEC e-SUS APS.
  - [x] Fontes oficiais para documentação futura:
    - `https://sigtap.datasus.gov.br/tabela-unificada/app/download.jsp`
    - `https://wiki.datasus.gov.br/sigtap/index.php/Procedimento`
    - `https://datasus.saude.gov.br/interoperabilidade-catalogo-de-servicos/`
    - `https://integracao.esusaps.bridge.ufsc.tech/ledi/index.html`
- [x] **Catálogo local SIGTAP**
  - [x] Tabela `sigtap_procedures` criada com código, competência, nome, grupo, subgrupo, forma de organização, origem, status e data de importação.
  - [x] Pré-carga odontológica inicial criada em `services/sigtap_service.py` para permitir uso imediato enquanto a competência oficial da prefeitura não for homologada.
  - [x] `SIGTAP_DEFAULT_COMPETENCE` documentado no `.env.example`.
  - [x] Importador oficial criado em `scripts/import_sigtap.py`.
  - [x] Importador aceita ZIP oficial SIGTAP ou `TB_PROCEDIMENTO.TXT` extraído.
  - [x] Importador permite recorte odontológico por padrão ou carga completa com `--all-procedures`.
- [x] **Vínculo do procedimento clínico ao código SUS**
  - [x] Tabela `tratamento_procedimentos` ampliada com `sigtap_code`, `sigtap_competence`, `sigtap_name`, `esus_export_status`, `esus_exported_at` e `esus_export_batch_id`.
  - [x] Aba Plano de Tratamento recebeu seleção de código SUS/SIGTAP ao adicionar ou editar procedimento.
  - [x] Procedimento assinado/concluído passa a marcar prontidão de exportação e sinaliza `missing_sigtap` quando estiver sem código.
  - [x] Evolução importada após assinatura inclui referência SIGTAP quando disponível.
- [x] **Base de espera para e-SUS APS**
  - [x] Tabela `esus_integration_settings` criada para guardar dados futuros da prefeitura: ambiente, URL base, instalação, client id e status de credencial.
  - [x] Tabela `esus_export_batches` criada para lotes de exportação preliminares.
  - [x] Serviço `services/esus_export_service.py` criado para apurar produção concluída, separar registros prontos de registros sem SIGTAP e montar payload preliminar.
  - [x] Script `scripts/build_esus_payload.py` criado para gerar JSON preliminar e/ou registrar lote draft.
- [x] **Validação técnica da sessão**
  - [x] Testes automatizados adicionados em `tests/test_phase3_sigtap_esus.py`.
  - [x] Suíte total validada com 45 testes.

#### Comandos operacionais SIGTAP/e-SUS

```bash
# Carregar apenas a pré-carga odontológica local para uma competência
docker compose exec -T gestaoclinica python scripts/import_sigtap.py --competence 202603 --seed-only

# Importar ZIP oficial SIGTAP/DataSUS quando a competência for baixada
docker compose exec -T gestaoclinica python scripts/import_sigtap.py --competence AAAAMM --zip /app/uploads/sigtap/SIGTAP_AAAAMM.zip

# Importar arquivo TB_PROCEDIMENTO.TXT extraído
docker compose exec -T gestaoclinica python scripts/import_sigtap.py --competence AAAAMM --tb-procedimento /app/uploads/sigtap/TB_PROCEDIMENTO.TXT

# Gerar payload preliminar de produção para validação antes da integração real com a prefeitura
docker compose exec -T gestaoclinica python scripts/build_esus_payload.py --month 2026-05 --register
```

#### Testes executados após prontidão SIGTAP/e-SUS

```bash
.venv/bin/python -m pytest -q
# Resultado: 45 passed

.venv/bin/python -m pytest tests/test_phase3_sigtap_esus.py tests/test_phase3_institutional_report.py -q
# Resultado: 15 passed

.venv/bin/python -m compileall app.py database.py blueprints/patients.py services/sigtap_service.py services/esus_export_service.py scripts/import_sigtap.py scripts/build_esus_payload.py tests/test_phase3_sigtap_esus.py
# Resultado: compilação sem erro

docker compose up -d --build
curl http://localhost:5003/health
# Resultado: HTTP 200, database ok

docker compose exec -T postgres psql -U clinica_user -d clinica -c "SELECT COUNT(*) AS sigtap_seed FROM sigtap_procedures;"
# Resultado: 32 procedimentos odontológicos na pré-carga inicial

docker compose exec -T gestaoclinica python scripts/build_esus_payload.py --month 2026-05 --register
# Resultado: lote draft registrado em esus_export_batches aguardando credenciais/endpoint da prefeitura
```

#### Entregas implementadas em 01/06/2026 — Painel Operacional SIGTAP/e-SUS APS

- [x] **Tela administrativa de integração**
  - [x] Rota `/admin/integrations/esus` criada para acompanhamento operacional da preparação e-SUS APS.
  - [x] Menu lateral atualizado com item `SIGTAP/e-SUS` para perfis autorizados.
  - [x] Permissões `integrations:view` e `integrations:write` adicionadas à matriz de acesso.
  - [x] Administrador pode visualizar e operar; auditoria e BI visualizam sem permissão de escrita.
- [x] **Painel de prontidão da produção**
  - [x] Cards de procedimentos concluídos, prontos para lote, sem SIGTAP e com dados pendentes.
  - [x] Filtro por competência de produção.
  - [x] Listagem de procedimentos sem código SIGTAP.
  - [x] Listagem de pendências de envio por registro: SIGTAP, competência, CNS/CPF, profissional, CRO, CNES e INE/equipe.
  - [x] Histórico dos lotes draft gerados.
- [x] **Correção operacional de procedimentos**
  - [x] Vinculação/alteração de código SIGTAP diretamente pelo painel.
  - [x] Procedimento corrigido volta para `esus_export_status='pending'` quando já estiver concluído.
  - [x] Auditoria registra alteração de código SIGTAP em `audit_logs`.
- [x] **Configuração de espera da prefeitura**
  - [x] Formulário para ambiente, URL PEC/e-SUS, versão PEC, versão LEDI, CNES, INE/equipe, instalação, client id, status de credenciais e observações.
  - [x] Tabela `esus_integration_settings` ampliada com `pec_version`, `ledi_version`, `cnes` e `ine`.
  - [x] Auditoria registra atualização da configuração.
- [x] **Geração de lote pela interface**
  - [x] Botão `Gerar Lote Draft` cria lote em `esus_export_batches` para conferência.
  - [x] Serviço `services/esus_export_service.py` centraliza dashboard, pendências, configuração, correção e criação de lote.
- [x] **Validação técnica da sessão**
  - [x] Testes automatizados ampliados para 49 casos.
  - [x] Renderização autenticada da rota `/admin/integrations/esus` validada em Docker.
  - [x] Migração das colunas `pec_version`, `ledi_version`, `cnes` e `ine` validada no PostgreSQL.

#### Testes executados após Painel Operacional SIGTAP/e-SUS

```bash
.venv/bin/python -m pytest -q
# Resultado: 49 passed

.venv/bin/python -m pytest tests/test_phase3_sigtap_esus.py -q
# Resultado: 9 passed

.venv/bin/python -m compileall blueprints/admin.py constants.py database.py services/esus_export_service.py services/sigtap_service.py tests/test_phase3_sigtap_esus.py
# Resultado: compilação sem erro

git diff --check
# Resultado: sem erros de whitespace

docker compose up -d --build
curl http://localhost:5003/health
# Resultado: HTTP 200, database ok
```

Validações em Docker:

| Ação | Resultado |
|---|---|
| `GET /admin/integrations/esus?month=2026-05` autenticado como admin | HTTP 200 |
| Conteúdo da tela | `SIGTAP / e-SUS APS` renderizado |
| `information_schema.columns` | Colunas `cnes`, `ine`, `ledi_version` e `pec_version` presentes |

#### Entregas implementadas em 01/06/2026 — Checklist de Homologação e Dados Obrigatórios e-SUS

- [x] **Dados obrigatórios no cadastro de pacientes**
  - [x] `CNS` e `CPF` tornados obrigatórios no cadastro de paciente.
  - [x] `CNS` e `CPF` tornados obrigatórios na edição de paciente.
  - [x] Validação de backend adicionada em `blueprints/patients.py`, além do `required` no HTML.
- [x] **Dados obrigatórios no cadastro de profissionais**
  - [x] Tabela `users` ampliada com `cns`, `cbo`, `cnes` e `ine`.
  - [x] Perfis profissionais passam a exigir CNS profissional, CBO, CNES e INE/equipe.
  - [x] Perfis odontológicos passam a exigir também CRO e CRO-UF.
  - [x] Cadastro e edição de usuário bloqueiam gravação quando o perfil profissional está incompleto.
  - [x] `utils.User` e login atualizados para carregar os novos campos profissionais.
- [x] **Validador de prontidão para homologação**
  - [x] Painel `/admin/integrations/esus` agora mostra bloco `Homologação`.
  - [x] Checklist indica se a integração está pronta para homologação: sim/não.
  - [x] Checklist avalia ambiente, URL PEC/e-SUS, versão PEC, versão LEDI, credenciais, CNES, INE, catálogo SIGTAP, pacientes, profissionais e bloqueios de produção.
  - [x] Painel lista profissionais com dados obrigatórios pendentes e link para correção.
  - [x] Serviço `services/esus_export_service.py` ampliado com apuração de pacientes sem CNS/CPF, profissionais incompletos e bloqueadores de homologação.
- [x] **Validação técnica da sessão**
  - [x] Testes automatizados ampliados para 51 casos.
  - [x] Renderização autenticada da rota `/admin/integrations/esus` validada em Docker com os blocos `Homologação` e `Profissionais com Dados Pendentes`.
  - [x] Migração das colunas `cns`, `cbo`, `cnes` e `ine` em `users` validada no PostgreSQL.

#### Testes executados após Checklist de Homologação

```bash
.venv/bin/python -m pytest -q
# Resultado: 51 passed

.venv/bin/python -m pytest tests/test_phase3_sigtap_esus.py tests/test_phase1_security.py -q
# Resultado: 17 passed

.venv/bin/python -m compileall constants.py database.py utils.py blueprints/auth.py blueprints/admin.py blueprints/patients.py services/esus_export_service.py templates/admin/add_user.html templates/admin/edit_user.html templates/admin/esus_integration.html templates/patients/register.html templates/patients/edit.html tests/test_phase3_sigtap_esus.py
# Resultado: compilação sem erro

git diff --check
# Resultado: sem erros de whitespace

docker compose up -d --build
curl http://localhost:5003/health
# Resultado: HTTP 200, database ok
```

Validações em Docker:

| Ação | Resultado |
|---|---|
| `information_schema.columns` em `users` | Colunas `cns`, `cbo`, `cnes` e `ine` presentes |
| `GET /admin/integrations/esus?month=2026-05` autenticado como admin | HTTP 200 |
| Conteúdo da tela | Blocos `Homologação` e `Profissionais com Dados Pendentes` renderizados |

#### Entregas implementadas em 01/06/2026 — Dados Demonstrativos para Apresentação

- [x] **Rotina de povoamento sem frontend**
  - [x] Comando Flask CLI `seed-demo-data` registrado em `app.py`.
  - [x] Execução via Docker: `docker compose exec -T gestaoclinica flask --app app:app seed-demo-data --count 100 --label "Demonstração institucional"`.
  - [x] Limite operacional de 1 a 100 pacientes por execução para evitar carga acidental excessiva.
  - [x] Cada execução fica registrada na tabela `demo_seed_runs`, com label, quantidade solicitada, quantidade criada, status, data e detalhes.
  - [x] Pacientes fictícios ficam marcados em `patients.is_demo=TRUE`, com `demo_profile` e `demo_seed_run_id`.
- [x] **Perfis clínicos fictícios**
  - [x] Oito perfis iniciais: idoso com necessidade protética, diabético periodontal, criança com cárie ativa, tabagista com lesão suspeita, dor endodôntica, reabilitação com implante, gestante em preventivo e paciente oncológico em acompanhamento.
  - [x] Dados pessoais fictícios com CPF formatado e dígitos verificadores válidos para demonstração, CNS fictício, telefone, endereço, profissão, gênero e data de nascimento.
  - [x] Municípios de Alagoas reaproveitados da base de referência e bairros/áreas de atendimento distribuídos para alimentar indicadores territoriais.
- [x] **Prontuário completo para demonstração**
  - [x] TCLE fictício assinado.
  - [x] Anamnese completa com condições variáveis: hipertensão, diabetes, tabagismo, gestação, suspeita/risco oncológico, dor e perfil infantil.
  - [x] Exames físico, odontograma e periograma.
  - [x] Plano de tratamento com procedimentos vinculados ao catálogo SIGTAP odontológico.
  - [x] Atendimentos/evoluções clínicas iniciais assinadas.
  - [x] Agenda com consultas em estados variados, incluindo faltas para alimentar absenteísmo.
  - [x] Casos de estomatologia com lesão suspeita, foto fictícia e encaminhamento para biópsia.
  - [x] Casos de prótese/reabilitação com etapa de moldagem.
  - [x] Alguns receituários e atestados fictícios para compor a linha do tempo do paciente.
- [x] **Base de demonstração gerada no Docker local**
  - [x] Carga final validada com 100 pacientes demo.
  - [x] Distribuição validada em 8 perfis clínicos.
  - [x] Registros validados: 100 anamneses, 300 exames, 200 procedimentos, 25 registros de lesão/estomatologia e 24 registros de prótese.
  - [x] Dados já alimentam Epidemiologia, BI, Central de Comando, prontuário, linha do tempo, absenteísmo, demanda reprimida e preparação SIGTAP/e-SUS.
- [x] **Validação técnica da sessão**
  - [x] Serviço `services/demo_data_service.py` criado.
  - [x] Testes automatizados adicionados em `tests/test_demo_data_service.py`.
  - [x] Sem tela administrativa e sem item de menu, conforme decisão de produto desta sessão.

#### Testes executados após Dados Demonstrativos

```bash
.venv/bin/python -m pytest -q
# Resultado: 55 passed

.venv/bin/python -m compileall app.py database.py services/demo_data_service.py tests/test_demo_data_service.py
# Resultado: compilação sem erro

git diff --check
# Resultado: sem erros de whitespace

docker compose up -d --build
curl http://localhost:5003/health
# Resultado: HTTP 200, database ok

docker compose exec -T gestaoclinica flask --app app:app seed-demo-data --count 1 --label "Smoke demo Codex"
# Resultado: 1 paciente demo criado com prontuário completo

docker compose exec -T gestaoclinica flask --app app:app seed-demo-data --count 99 --label "Carga demo inicial 100 pacientes"
# Resultado: 99 pacientes demo criados; total local validado: 100 pacientes demo
```

Validações em Docker:

| Ação | Resultado |
|---|---|
| `patients WHERE is_demo = TRUE` | 100 pacientes |
| `demo_seed_runs` | Execuções `success` com 1 e 99 pacientes |
| `anamnesis` vinculada a pacientes demo | 100 registros |
| `exams` vinculados a pacientes demo | 300 registros |
| `tratamento_procedimentos` vinculados a pacientes demo | 200 registros |
| `estomatologia` vinculada a pacientes demo | 25 registros |
| `prosthesis` vinculada a pacientes demo | 24 registros |

#### Entregas implementadas em 01/06/2026 — Conferência de Lote Draft e-SUS APS

- [x] **Tela de detalhe do lote draft**
  - [x] Rota `/admin/integrations/esus/batches/<id>` criada para abrir um lote específico.
  - [x] Tela exibe competência, status, totais apurados, registros incluídos, pendências, gerador, validador e hash SHA-256 do payload.
  - [x] Histórico de lotes no painel `/admin/integrations/esus` agora possui link direto para abrir cada lote.
- [x] **Snapshot e download de JSON de conferência**
  - [x] `esus_export_batches` ampliada com `payload_json`, `records_incomplete`, `validated_by`, `validated_at` e `validation_notes`.
  - [x] A geração do lote passou a salvar snapshot JSON do payload, além do hash.
  - [x] Rota `/admin/integrations/esus/batches/<id>/download` criada para baixar o JSON draft.
  - [x] O payload inclui paciente, profissional, procedimento, SIGTAP, competência, dente e data do procedimento.
- [x] **Validação interna**
  - [x] Rota `POST /admin/integrations/esus/batches/<id>/validate` criada para marcar lote como `validated_internally`.
  - [x] Validação registra usuário, horário e observação interna.
  - [x] Lote validado preserva o hash e o snapshot de conferência.
  - [x] Alteração de SIGTAP é bloqueada quando o procedimento já está incluído em lote validado internamente.
- [x] **Auditoria completa do fluxo**
  - [x] Geração registra `esus_batch_created`.
  - [x] Abertura registra `esus_batch_opened`.
  - [x] Download registra `esus_batch_downloaded`.
  - [x] Validação registra `esus_batch_validated_internally`.
- [x] **Validação técnica da sessão**
  - [x] Testes automatizados ampliados para 60 casos.
  - [x] Renderização da tela de detalhe validada no Docker.
  - [x] Download JSON validado no Docker.
  - [x] Validação interna e bloqueio de edição pós-validação confirmados no Docker.

#### Testes executados após Conferência de Lote e-SUS

```bash
.venv/bin/python -m pytest -q
# Resultado: 60 passed

.venv/bin/python -m pytest -q tests/test_phase3_sigtap_esus.py
# Resultado: 16 passed

.venv/bin/python -m compileall database.py services/esus_export_service.py blueprints/admin.py tests/test_phase3_sigtap_esus.py
# Resultado: compilação sem erro

git diff --check
# Resultado: sem erros de whitespace

docker compose up -d --build
curl http://localhost:5003/health
# Resultado: HTTP 200, database ok
```

Validações em Docker:

| Ação | Resultado |
|---|---|
| Colunas novas em `esus_export_batches` | `payload_json`, `records_incomplete`, `validated_by`, `validated_at`, `validation_notes` presentes |
| `GET /admin/integrations/esus?month=2026-06` autenticado | HTTP 200 |
| `POST /admin/integrations/esus/batches` | HTTP 302 para detalhe do lote |
| `GET /admin/integrations/esus/batches/<id>` | HTTP 200 com registros incluídos e hash |
| `GET /admin/integrations/esus/batches/<id>/download` | HTTP 200, JSON com `local_procedure_id` |
| `POST /admin/integrations/esus/batches/<id>/validate` | Lote marcado como `validated_internally` |
| Auditoria do lote | `created`, `opened`, `downloaded` e `validated_internally` registrados |
| Bloqueio pós-validação | Alteração de SIGTAP bloqueada para procedimento incluído no lote validado |

#### Entregas implementadas em 01/06/2026 — Pré-envio Simulado e-SUS APS

- [x] **Estados de fechamento do lote**
  - [x] Fluxo de status formalizado para `draft`, `validated_internally`, `ready_to_send`, `sent` e `failed`.
  - [x] Lote validado internamente pode passar por pré-envio simulado antes de qualquer transmissão real.
  - [x] Quando a simulação local é aprovada, o lote muda para `ready_to_send`.
  - [x] Transmissão real permanece desativada até a prefeitura fornecer conector/endpoint/credenciais homologados.
- [x] **Histórico de tentativas**
  - [x] Tabela `esus_transmission_attempts` criada.
  - [x] Cada tentativa registra lote, modo (`simulation`), status, endpoint, HTTP simulado, hash do payload, resposta, erro, usuário e horário.
  - [x] Tela do lote exibe o histórico de tentativas.
- [x] **Pré-envio simulado**
  - [x] Rota `POST /admin/integrations/esus/batches/<id>/preflight` criada.
  - [x] Simulação valida status do lote, hash, existência de registros, ambiente, URL PEC/e-SUS, credenciais, CNES, INE/equipe e integração ativa.
  - [x] Simulação bloqueada grava tentativa com `status='blocked'` e HTTP simulado `428`.
  - [x] Simulação aprovada grava tentativa com `status='success'`, HTTP simulado `200` e marca o lote como `ready_to_send`.
- [x] **Preparação do botão de envio real**
  - [x] Tela do lote mostra a seção `Pré-envio e-SUS`.
  - [x] Botão `Simular Pré-envio` disponível para lotes `validated_internally` ou `ready_to_send`.
  - [x] Botão `Enviar para e-SUS APS` aparece desabilitado, deixando claro que a chamada real ainda depende da homologação externa.
  - [x] Quando houver bloqueio, a tela lista exatamente quais requisitos impedem o envio real.
- [x] **Auditoria**
  - [x] Pré-envio simulado registra `esus_batch_preflight_simulated`.
  - [x] Auditoria diferencia tentativa aprovada (`success`) e bloqueada (`blocked`).

#### Testes executados após Pré-envio Simulado e-SUS

```bash
.venv/bin/python -m pytest -q
# Resultado: 64 passed

.venv/bin/python -m pytest -q tests/test_phase3_sigtap_esus.py
# Resultado: 20 passed

.venv/bin/python -m compileall database.py services/esus_export_service.py blueprints/admin.py templates/admin/esus_batch_detail.html tests/test_phase3_sigtap_esus.py
# Resultado: compilação sem erro

git diff --check
# Resultado: sem erros de whitespace

docker compose up -d --build
curl http://localhost:5003/health
# Resultado: HTTP 200, database ok
```

Validações em Docker:

| Ação | Resultado |
|---|---|
| Tabela `esus_transmission_attempts` | 12 colunas criadas e indexadas |
| `GET /admin/integrations/esus?month=2026-06` autenticado | HTTP 200 |
| `POST /admin/integrations/esus/batches/<id>/preflight` sem configuração completa | Tentativa `blocked`, HTTP simulado `428`, lote permanece `validated_internally` |
| `POST /admin/integrations/esus/batches/<id>/preflight` com configuração simulada completa | Tentativa `success`, HTTP simulado `200`, lote marcado `ready_to_send` |
| Histórico de tentativas | Registros de simulação bloqueada e aprovada persistidos |
| Auditoria do pré-envio | `esus_batch_preflight_simulated` registrado com status `blocked` e `success` |

#### Pendências da Fase 3

- [ ] **Mapa Epidemiológico em Tempo Real avançado**
  - [ ] Painel georreferenciado real por bairro, município, unidade e ação de triagem.
  - [ ] Inclusão de perda dentária quando o odontograma estiver estruturado para esse indicador.
  - [ ] Indicador formal de diagnóstico confirmado de câncer de boca, além da suspeita oncológica.
  - [ ] Filtros por faixa etária, sexo, especialidade, profissional, município e status do tratamento.
  - [ ] Identificação automática de áreas críticas para mutirões móveis e ações preventivas.
- [ ] **Dashboard Executivo (BI) Governamental**
  - [x] Rota `/bi` protegida por permissão `bi:view`.
  - [x] Cards executivos de produção clínica, pacientes atendidos, fila encaminhada e absenteísmo.
  - [x] Indicadores de impacto social: pacientes alcançados, bairros atendidos, municípios vinculados e comparecimento.
  - [x] Indicadores de fila SUS: demanda triada, encaminhada/atendida, reprimida e taxa de encaminhamento.
  - [x] Indicadores financeiros operacionais v1: valor estimado em planos, valor aprovado e taxa de conversão.
  - [x] Metas automáticas v1 baseadas no mês anterior e meta fixa de comparecimento.
  - [x] Comparativo mensal de produção, atendimentos, cadastros, faltas e suspeitas oncológicas.
  - [x] Rankings de produção por profissional, bairros com maior alcance e especialidades críticas por demanda reprimida.
  - [ ] Economia gerada formal com metodologia validada pela gestão pública.
  - [ ] Visões específicas separadas para Prefeitura, SSA, SMS, coordenação clínica e auditoria.
- [ ] **Relatórios automáticos e PDFs institucionais**
  - [x] PDF institucional v1 com síntese executiva, epidemiológica e operacional.
  - [x] Recortes SSA e SMS.
  - [x] Geração assíncrona por Celery + WeasyPrint.
  - [x] Prévia filtrável por período.
  - [x] Script agendável para geração mensal automática.
  - [x] Histórico inicial de geração.
  - [x] Serviço de scheduler interno configurado com Celery Beat no ambiente Docker.
  - [x] Gráficos renderizados no PDF.
  - [x] Assinatura técnica com hash SHA-256 e histórico formal em `digital_signatures`.
  - [x] Disponibilização segura no painel executivo/institucional com controle por perfil.
  - [ ] Assinatura digital ICP-Brasil/Gov.br ou provedor institucional homologado.
  - [ ] Agendamento de envio por e-mail institucional.
- [ ] **Integração Governamental (API do SUS)**
  - [x] Catálogo local SIGTAP/DataSUS para procedimentos odontológicos.
  - [x] Importador para competência oficial SIGTAP por ZIP/TXT.
  - [x] Vínculo de procedimentos clínicos com código, competência e nome SIGTAP.
  - [x] Payload preliminar e lotes draft para e-SUS APS.
  - [x] Estrutura de configuração aguardando URL, credenciais, instalação e ambiente da prefeitura.
  - [x] Painel operacional para correção de SIGTAP, conferência de pendências e geração de lote draft.
  - [x] Checklist de homologação e dados obrigatórios de pacientes/profissionais.
  - [x] Tela de detalhe, download JSON, validação interna e auditoria do lote draft e-SUS.
  - [x] Pré-envio simulado, status `ready_to_send` e histórico de tentativas.
  - [ ] Validar versão do PEC/e-SUS APS instalada na prefeitura e compatibilidade LEDI.
  - [ ] Implementar transmissão real quando a prefeitura fornecer endpoint, HTTPS, autenticação, CNES/INE e regras de homologação.
  - [ ] Validar campos obrigatórios finais: CNS/CPF, profissional, CBO, CNES, equipe/INE, data de atendimento, procedimento SIGTAP e compatibilidades.

#### Observações para manuais futuros

- Manual da epidemiologia deve explicar leitura dos filtros de período e bairro, diferença entre lesão registrada e suspeita oncológica, e interpretação da taxa de absenteísmo.
- Manual da gestão deve reforçar que o v1 é territorial por bairro, não um mapa cartográfico georreferenciado.
- Manual do BI deve explicar metas automáticas, crescimento contra mês anterior, ranking de produção e diferença entre valor estimado/aprovado e economia pública formal.
- Manual de relatórios deve explicar como gerar a prévia institucional, aplicar período, exportar PDF e interpretar recomendações automáticas.
- Manual de relatórios deve explicar a rotina automática mensal, horário configurado, tipos de relatório, reprocessamento com `--force`, status no histórico, hash SHA-256 e regras de acesso por Prefeitura/SSA/SMS.
- Manual de integração deve explicar como atualizar a competência SIGTAP, como escolher código SUS/SIGTAP no plano de tratamento, como localizar procedimentos sem código e como gerar lote draft para validação da prefeitura.
- Manual de integração deve explicar a tela `/admin/integrations/esus`, permissões de visualização/escrita, configuração da prefeitura, leitura dos cards e correção de pendências por registro.
- Manual de cadastro deve reforçar que CNS/CPF do paciente e CNS/CBO/CNES/INE do profissional são obrigatórios para prontidão e-SUS; perfis odontológicos também exigem CRO/CRO-UF.
- Manual técnico deve documentar a origem de cada indicador para evitar uso institucional de métricas proxy sem explicação.

---

## 📝 Acessos

- **Landing Page:** [https://sorrisodagentealagoas.com](https://sorrisodagentealagoas.com)
- **Painel Administrativo:** `/dashboard`
- **Fila Vermelha (Oncologia):** `/patients/red-alerts`
- **Epidemiologia:** `/epidemiologia`
- **BI Executivo:** `/bi`
- **Relatórios Institucionais:** `/reports/institutional`
- **SIGTAP/e-SUS APS:** `/admin/integrations/esus`
- **Health Check:** `/health`
- **Banco de Dados (host):** porta `5433`

---
&copy; 2026 Programa Sorriso da Gente. Todos os direitos reservados.
