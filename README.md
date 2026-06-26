# Gestão Saúde Oral — Programa Sorriso da Gente

Versão de produção: **4.0.0**

Atualização: **25/06/2026**

Status: **GO — produção plena aprovada**

Plataforma clínica, operacional e institucional de saúde bucal. Reúne triagem
municipal, agenda, prontuário odontológico, exames, Estomatologia, estoque,
Central de Comando, BI, Epidemiologia, relatórios, SIGTAP e preparação para
integração e-SUS APS.

Este `README.md` é a fonte única de estado, operação, produção e evolução do
projeto. Os arquivos em `docs/` preservam evidências, políticas e manuais
detalhados.

## Estado executivo

A aplicação e a infraestrutura passaram pelo QA técnico de 21/06/2026:

- `285` testes aprovados localmente e na imagem Docker com PostgreSQL isolado;
- dependências diretas, transitivas e instaladas sem vulnerabilidades
  conhecidas;
- rebuild Docker, `/health`, Celery e smoke tests aprovados;
- PostgreSQL e Redis sem publicação externa;
- somente TCP `22`, `80` e `443` públicos no IPv4 e IPv6 entre as portas
  testadas;
- backup local e externo validado com `0 differences`;
- restore isolado aprovado com `54` tabelas;
- OAuth/rclone renovado e persistido por substituição atômica;
- base operacional com `0` pacientes, `0` atendimentos e dois administradores.

Decisão atual: **GO para produção plena com ampliação de pacientes reais**,
registrada em 25/06/2026 por **Diego (perfil Administrador)** — todos os
itens do [Checklist Go/No-Go](#checklist-go-no-go) foram concluídos antes da
decisão. Tag de produção: `v4.0.0`.

Resolvido em 25/06/2026:

- token temporário da API Hostinger **revogado no hPanel e arquivo local
  removido** (`secrets/hostinger-api-token` não existe mais);
- aceite formal da política de governança pela Dra. Cibely **registrado como
  concluído**;
- responsável técnica/clínica indicada: **Vanessa Mikaene Silva e Lima — CRO
  10160 PB** (o aspecto jurídico não se aplica a esta indicação);
- homologação do fluxo ponta a ponta e aprovação da entrada assistida
  **registradas como concluídas** (ver detalhe em
  [Aprovação da coordenação](#aprovação-da-coordenação-para-entrada-assistida),
  abaixo);
- e-mails críticos validados em Gmail e Outlook, e manuais/treinamento por
  perfil entregues (ver detalhe em
  [Validação de e-mails críticos](#validação-de-e-mails-críticos-25062026),
  abaixo).

Despriorizado em 25/06/2026 (deixou de ser bloqueador de entrada, mas
continua como pendência documentada — ver
[Google Drive](#google-drive) abaixo): confirmação de 2FA, recuperação e
custodiantes da conta Google institucional.

A versão `v4.0.0` é a primeira tag de produção plena, após decisão **GO** de
25/06/2026. Ela não substitui homologação municipal nem aceite jurídico, que
seguem como responsabilidades institucionais separadas.

Evidência: [`docs/auditoria_go_no_go_2026-06-21.md`](docs/auditoria_go_no_go_2026-06-21.md).

### Aprovação da coordenação para entrada assistida

"Entrada assistida" é a fase em que o sistema passa a ser usado com pacientes
e equipe reais, mas sob acompanhamento ativo (P1 do roadmap, ver
[Evolução durante a produção](#p1--entrada-e-operação-assistida)) — não é um
corte único e definitivo, é uma rampa supervisionada.

A "aprovação da coordenação" é o registro formal de que o fluxo ponta a ponta
que vai ser usado no dia a dia (agenda, triagem, recepção, relatórios) foi
efetivamente testado e está de acordo para operar assim.

Registro de homologação — **concluído em 25/06/2026**:

- responsável pelo teste: **Diego, perfil Administrador**;
- ambientes: produção e desenvolvimento;
- fluxo percorrido: criar paciente, triar, agendar, atender, gerar relatório;
- resultado: fluxo aprovado, sem bloqueios encontrados.

Observação: o teste foi realizado pelo perfil Administrador, não pelo perfil
Coordenação propriamente. Se a Coordenação operacional (Recepção/Clínicos)
quiser fazer sua própria homologação por perfil mais adiante, durante o P1
(ver [Evolução durante a produção](#p1--entrada-e-operação-assistida)), o
resultado pode ser registrado aqui como complemento.

## Escopo congelado da candidata

Incluído:

- triagem vinculada ao paciente;
- agenda por unidade e profissional;
- prontuário, anamnese, tratamento e evolução;
- Estomatologia e alerta de suspeita de neoplasia;
- exames odontológicos, de imagem e clínico-laboratoriais;
- documentos clínicos, consentimentos e assinatura probatória;
- atestados odontológicos e declarações de comparecimento em PDF;
- catálogo selecionável de CID-10 odontológico, com descrição e autorização
  obrigatória do paciente antes da inclusão no atestado;
- estoque e materiais;
- Central de Comando, Epidemiologia, BI e relatórios institucionais;
- SIGTAP e exportação XML LEDI e-SUS em modo controlado;
- pré-cadastro profissional, primeiro acesso e recuperação de senha;
- auditoria, RBAC/IDOR, proteção de arquivos e segurança web;
- backup diário e cópia externa.

Fora do escopo de evolução até a entrada assistida:

- novas funcionalidades de Endodontia e Prótese;
- Portal do Paciente;
- redesign ou novas métricas de BI;
- novos canais de WhatsApp/SMS;
- ampliação de integrações externas.

Endodontia e Prótese continuam no código, protegidas no backend e ocultas da
navegação por decisão operacional. Não foram removidas.

## Arquitetura

Stack:

- Python 3.11, Flask e Gunicorn/gevent;
- PostgreSQL 16;
- Redis;
- Celery worker e Celery Beat;
- WeasyPrint;
- Nginx no host;
- Docker Compose;
- Google Drive institucional via rclone;
- Postfix e OpenDKIM para e-mail transacional.

Serviços:

| Serviço | Finalidade | Exposição |
|---|---|---|
| `gestaosaudeoral-web` | Aplicação Flask/Gunicorn | `127.0.0.1:5003` |
| `gestaosaudeoral-postgres` | Banco PostgreSQL | rede Docker |
| `gestaosaudeoral-redis` | sessões, cache, fila e rate limit | rede Docker |
| `gestaosaudeoral-celery` | tarefas assíncronas | rede Docker |
| `gestaosaudeoral-beat` | agendamentos Celery | rede Docker |
| `gestaosaudeoral-mail` | SMTP interno/Postfix/OpenDKIM | rede Docker |
| `gestaosaudeoral-backup` | backup, integridade e cópia externa | rede Docker |

Volumes e dados persistentes:

- `postgres_data_oral`: banco;
- `redis_data_oral`: Redis;
- `pdf_temp_oral`: PDFs temporários;
- `logs_oral`: logs;
- `backups_oral`: backups locais;
- `celerybeat_oral`: agenda persistente;
- `/srv/gestaosaudeoral/uploads`: staging, cache e derivados protegidos.

Decisões aceitas:

- a VPS é compartilhada com outras aplicações;
- a aplicação permanece isolada em Docker;
- Nginx é a única entrada HTTP/HTTPS;
- PostgreSQL, Redis e SMTP não são publicados;
- originais clínicos usam Google Drive institucional;
- staging, cache e derivados permanecem sensíveis enquanto estiverem na VPS;
- sincronização com Drive não substitui backup.

## Infraestrutura e borda

VPS:

- hostname: `srv1403247.hstgr.cloud`;
- projeto: `/home/diego/projetos/GestaoSaudeOral`;
- usuário operacional: `diego`;
- domínio: `https://sorrisodagentealagoas.com`;
- firewall Hostinger: `srv1403247-producao-minimo-20260620`, ID `315250`;
- regras públicas: TCP `22/80/443` e UDP `41641`.

Acesso:

```bash
ssh diego@srv1403247.hstgr.cloud
cd /home/diego/projetos/GestaoSaudeOral
```

SSH por senha deve permanecer desativado. Antes de alterar SSH, firewall ou
Tailscale, confirme um acesso administrativo alternativo.

Painéis administrativos:

- Portainer: `https://100.79.5.76:9443`;
- Uptime Kuma: `http://100.79.5.76:3025`;
- OpenGravity: `100.79.5.76:3333`.

Esses serviços devem responder somente pela Tailscale. Cockpit e Webmin foram
desinstalados.

A aplicação legada permanece isolada em `127.0.0.1:5002`, com PostgreSQL sem
porta publicada. Migração, arquivamento ou desligamento definitivo exigem
decisão separada.

## Instalação e execução

Pré-requisitos:

- Docker Engine com Compose;
- `.env` real fora do Git;
- diretório persistente de uploads;
- credenciais Google em `secrets/`;
- diretório rclone gravável.

Preparação:

```bash
cp .env.example .env
mkdir -p secrets/rclone
chmod 700 secrets secrets/rclone
chmod 600 secrets/rclone/rclone.conf
docker compose config --quiet
docker compose up -d --build
```

Status e saúde:

```bash
docker compose ps
curl --fail http://127.0.0.1:5003/health
curl --fail https://sorrisodagentealagoas.com/health
```

O `/health` retorna estado do banco, latência e versão:

```json
{
  "status": "healthy",
  "version": "4.0.0-rc.1",
  "database": "ok"
}
```

Logs:

```bash
docker compose logs --since 15m \
  gestaoclinica celery-worker celery-beat postgres redis mail backup
```

Não execute `flask run` ou `python app.py` em produção. O caminho oficial é
Gunicorn pelo Docker Compose. Quando executado diretamente, o debug permanece
desativado por padrão e só é habilitado com `FLASK_DEBUG=true`.

## Configuração

Variáveis essenciais:

| Variável | Finalidade |
|---|---|
| `APP_VERSION` | versão exibida no `/health` |
| `SECRET_KEY` | assinatura de sessão Flask |
| `DATABASE_URL` | conexão PostgreSQL |
| `POSTGRES_PASSWORD` | senha do serviço PostgreSQL |
| `REDIS_URL` | sessões, cache, Celery e rate limit |
| `APP_BASE_URL` | URL pública usada em links |
| `UPLOADS_HOST_PATH` | persistência de uploads no host |
| `RCLONE_CONFIG_HOST_DIR` | diretório OAuth gravável montado no Docker |
| `BACKUP_RETENTION_DAYS` | retenção local |
| `BACKUP_OFFSITE_RETENTION_DAYS` | retenção externa |
| `WHATSAPP_ACCESS_TOKEN` / `WHATSAPP_PHONE_NUMBER_ID` | habilitam o canal WhatsApp do módulo Comunicação (ausentes = canal desabilitado) |
| `APPOINTMENT_REMINDERS_ENABLED` | liga os lembretes automáticos de consulta |

Nunca registre `.env`, tokens, senhas, refresh tokens, JSON da Service Account,
chaves DKIM, dumps ou dados de pacientes no Git.

## Perfis e autorização

Perfis ativos:

- Administrador;
- Coordenação;
- Recepção;
- Clínicos;
- CME;
- Radiologia;
- Análises Clínicas;
- Comunicação;
- SSA/SMS;
- Auditoria.

O backend aplica uma política central rota × método × permissão. URLs diretas,
IDs previsíveis ou menus ocultos não ampliam acesso.

Controles principais:

- paciente, anamnese, tratamento e atendimento validam perfil e vínculo;
- exames odontológicos e laboratório possuem escopos separados;
- arquivo, miniatura, prévia e original exigem permissão da origem;
- PDFs e documentos validam documento + paciente;
- assinaturas exigem perfil clínico e permissão específica;
- Endodontia e Prótese continuam protegidas mesmo ocultas;
- negações autenticadas retornam HTTP `403` e geram auditoria;
- contas desligadas são inativadas, não apagadas quando possuem histórico.

Matriz completa:
[`docs/matriz_rbac_rotas_2026-06-20.md`](docs/matriz_rbac_rotas_2026-06-20.md).

## Fluxo operacional

1. Recepção cadastra ou localiza o paciente.
2. Triagem registra ação de campo e vincula uma ou mais senhas.
3. A unidade de execução é definida no agendamento, nunca pela triagem.
4. Agenda associa paciente, profissional, unidade, data e duração.
5. Clínico registra anamnese, exames, plano, evolução e documentos.
6. Central de Comando acompanha demanda, fila e alertas.
7. Coordenação acompanha indicadores e relatórios.

Regras permanentes:

- triagem não define unidade;
- Recepção visualiza a agenda de todos os Clínicos e pode cadastrar, editar,
  remanejar, cancelar e alterar o status das consultas;
- Clínicos veem na Agenda apenas o próprio recorte;
- estoque não pode bloquear registro clínico;
- economia no BI permanece estimativa até homologação;
- XML e-SUS não pode ser anunciado como homologado antes de importação aceita
  no PEC municipal;
- TCLE aceita assinatura a rogo exclusivamente para paciente não
  alfabetizado e exige autenticação do CD responsável;
- Anamnese e Atendimento/Evolução não exigem mais assinatura do paciente:
  a confirmação é sempre do clínico responsável (login e senha), e a
  produção/e-SUS só passam a contar depois que o Profissional Executor
  confirma a execução no Atendimento.

## Módulos

### Triagem e Agenda

- ações de triagem e geração de senhas;
- associação de senha a paciente já cadastrado;
- Agenda por unidade, profissional, status e duração;
- rastreabilidade de mudanças;
- Central de Comando respeitando o recorte da Agenda.

### Prontuário

- identificação e endereço estruturado;
- anamnese;
- plano de tratamento e procedimentos;
- evoluções e atendimentos;
- TCLE e confirmações;
- documentos clínicos;
- auditoria e linha do tempo.

### Exames e Biblioteca Visual

- exames físico, odontograma, placa e periograma;
- imagem odontológica e DICOM;
- exames clínico-laboratoriais;
- visualizador dedicado;
- thumbnails e prévias protegidas;
- originais entregues somente após autorização.

### Estomatologia

- ficha especializada;
- evolução fotográfica;
- suspeita de neoplasia com alerta vermelho;
- encaminhamento expresso em PDF.

### Gestão

- estoque por abas (Visão Geral, Entrada de Mercadoria, Materiais, Lotes e
  Saldo, Ajustes e Perdas, Notas Fiscais, Fornecedores), materiais e
  implantes;
- entrada de mercadoria com três caminhos para a mesma tela de conciliação:
  importação automática de XML da NF-e (leitura `lxml`, com chave de acesso e
  proteção contra reimportação duplicada), importação de melhor esforço de
  PDF/DANFE (`pdfplumber`, chave de acesso decodificada quando o dígito
  verificador confere) e lançamento manual de nota ou compra avulsa
  (digitando todos os dados) — nenhum dos três afeta o saldo sem confirmação
  explícita do material, quantidade, custo e validade de cada lote;
- cadastro de fornecedor com CNPJ validado (dígito verificador) para
  rastreabilidade fiscal, sem apuração de impostos;
- Central de Comando;
- Epidemiologia;
- BI executivo;
- referências SIGTAP e custos estimados;
- relatórios institucionais;
- preparação de remessas e-SUS APS.

### Comunicação

- campanhas em massa por e-mail (ativo, reaproveita o módulo de e-mail
  transacional) e por WhatsApp Business Cloud API (integração direta com a
  Meta, fica desabilitada automaticamente até as credenciais serem
  configuradas);
- segmentação de público por município, bairro, gênero e faixa etária, com
  contagem de destinatários antes do envio;
- lembretes automáticos de consulta (Celery Beat, desligado por padrão via
  `APPOINTMENT_REMINDERS_ENABLED`);
- preferências de contato por paciente (opt-in/opt-out por canal) e webhook
  de opt-out automático via WhatsApp (palavra-chave "PARAR"/"SAIR");
- perfil Comunicação só acessa nome, contato e dados geográficos do
  paciente — sem acesso ao prontuário clínico.

## Uploads clínicos

Uploads são identificados pelos bytes reais, não pela extensão ou MIME do
navegador:

- Pillow decodifica JPG, PNG, WEBP e TIFF;
- pydicom valida DICOM;
- pypdf valida a estrutura de PDFs.

Política padrão, configurável:

- até `300 MB` por arquivo;
- até `320 MB` por requisição;
- até `50.000 × 50.000` por eixo;
- até `150 milhões` de pixels por quadro;
- até `512` quadros;
- até `10.000` páginas PDF.

Os valores são contenção contra abuso, não uma meta de redução. Arquivos
legítimos com extensão errada são normalizados. O original clínico é preservado
sem recompressão; somente thumbnails e prévias usam WebP sem perda.

Arquivos falsos, vazios, truncados, corrompidos ou com descompressão abusiva são
rejeitados antes da sincronização.

## Google Drive

Conta proprietária institucional:
`sorrisodagentealagoas@gmail.com`.

Arquitetura:

- Service Account para metadados e pastas;
- OAuth institucional via rclone para armazenamento em “Meu Drive”;
- diretório `secrets/rclone` compartilhado entre web, worker e backup;
- `rclone.conf` renovado por substituição atômica.

Verificação segura:

```bash
docker compose exec -T gestaoclinica \
  python scripts/check_rclone_oauth.py
```

Pendência de segurança da conta (despriorizada em 25/06/2026 — deixou de
bloquear a entrada em operação, mas continua como lembrete a fazer, sem data
definida ainda):

- confirmar 2FA;
- confirmar dois meios/custodiantes de recuperação;
- armazenar códigos de recuperação fora da VPS e do Git;
- revisar dispositivos, sessões, apps OAuth e compartilhamentos.

## Backup e restauração

Política:

- backup diário de PostgreSQL e uploads;
- manifesto SHA-256;
- retenção local de 30 dias;
- retenção externa de 90 dias;
- cópia externa via rclone;
- RPO inicial de 24 horas;
- RTO inicial de 8 horas;
- restore isolado trimestral e antes de cada Go/No-Go.

Criar e validar backup:

```bash
scripts/docker_backup_postgres.sh
```

Validar restore:

```bash
scripts/docker_restore_verify.sh
```

Última evidência:

- backup `20260621_090722`;
- cópia externa com `0 differences`;
- restore de `54` tabelas;
- `0` pacientes no baseline.

Nunca teste restauração sobre o banco operacional.

## Testes e qualidade

Ambiente local:

```bash
.venv/bin/pytest -q
git diff --check
```

Para uma validação de release, use PostgreSQL temporário e isolado. Não herde a
`DATABASE_URL` operacional ao executar a suíte dentro do Compose.

Validações da candidata:

- suíte local: `285 passed`;
- suíte na imagem com banco isolado: `285 passed`;
- `pip-audit` direto, transitivo e da imagem: sem vulnerabilidades conhecidas;
- `pip check`: nenhuma dependência quebrada;
- rebuild Docker aprovado;
- health local e HTTPS aprovados;
- Celery respondeu `pong`;
- smoke de login e rotas protegidas aprovado.

## Segurança e governança

Controles implementados:

- cookies `Secure`, `HttpOnly` e `SameSite=Lax`;
- HSTS, CSP, proteção contra iframe e demais headers;
- logout por POST com CSRF;
- sessão regenerada no login;
- mensagens de erro públicas neutralizadas;
- rate limiting;
- RBAC e proteção contra IDOR;
- arquivos sensíveis fora do Git;
- Nginx com rota interna para arquivos protegidos;
- trilha de auditoria.

Responsáveis definidos:

| Função | Titular |
|---|---|
| Autoridade institucional e aprovadora de acessos | Dra. Cibely Candido |
| Ponto de contato de privacidade/incidentes | Dra. Cibely Candido |
| Custodiante técnico | Diego |
| Backup e restauração | Diego |
| Revisão independente | Perfil Auditoria ou pessoa indicada |
| Responsável técnica/clínica | Vanessa Mikaene Silva e Lima — CRO 10160 PB |

Aceite formal da política de governança pela Dra. Cibely: **registrado como
concluído em 25/06/2026**. Responsável técnica/clínica indicada em
25/06/2026: Vanessa Mikaene Silva e Lima (CRO 10160 PB) — o aspecto jurídico
não se aplica a esta indicação.

Retenção:

- prontuários, exames, imagens e assinaturas: mínimo de 20 anos após o último
  registro, sem exclusão automática;
- logs e histórico administrativo: mínimo de 5 anos;
- incidentes: mínimo de 5 anos;
- PDFs temporários: até 7 dias;
- backups locais: 30 dias;
- backups externos: 90 dias.

Descarte clínico exige prazo cumprido, ausência de impedimento legal, aprovação
institucional + clínica/jurídica, execução por IDs e evidência auditável.

Incidentes com risco ou dano relevante devem ser avaliados para comunicação à
ANPD e aos titulares em até 3 dias úteis, com complementação quando necessária.

Política completa:
[`docs/governanca_minima_2026-06-21.md`](docs/governanca_minima_2026-06-21.md).

## Checklist Go/No-Go

Concluído:

- [x] escopo funcional congelado;
- [x] HTTPS e domínio final;
- [x] PostgreSQL sem exposição pública;
- [x] firewall/reverse proxy revisados;
- [x] `.env`, DKIM e segredos fora do Git;
- [x] base sem dados demonstrativos;
- [x] backup diário, cópia externa e restore;
- [x] RPO/RTO definidos;
- [x] uploads e arquivos protegidos;
- [x] RBAC/IDOR;
- [x] dependências auditadas;
- [x] testes, rebuild, health e smoke;
- [x] Endodontia e Prótese identificadas como ocultas;
- [x] revogar e remover o token temporário Hostinger (25/06/2026);
- [x] obter aceite institucional da governança (25/06/2026);
- [x] indicar responsável técnica/clínica — Vanessa Mikaene Silva e Lima, CRO
  10160 PB (25/06/2026);
- [x] homologar fluxo ponta a ponta (Diego, Administrador, produção e
  desenvolvimento, 25/06/2026);
- [x] registrar aprovação da coordenação para entrada assistida (25/06/2026);
- [x] validar e-mails críticos em caixas Gmail e Outlook (25/06/2026 — ver
  detalhe abaixo);
- [x] entregar manuais e realizar treinamento por perfil (25/06/2026);
- [x] decisão **GO** registrada (Diego, Administrador, 25/06/2026) e tag de
  produção `v4.0.0` criada.

Pendente: nenhum item bloqueador — checklist Go/No-Go concluído.

Lembrete sem data definida (não bloqueia mais a entrada em operação):

- [ ] confirmar 2FA/recuperação/custódias da conta Google institucional (ver
  [Google Drive](#google-drive)).

### Validação de e-mails críticos (25/06/2026)

Teste real de entregabilidade via `services/mail_service.send_email`, mesmo
caminho transacional documentado em
[docs/email_producao_sorrisodagente_2026-06-16.md](docs/email_producao_sorrisodagente_2026-06-16.md):

- `gentillidiego@gmail.com` — aceito por `gmail-smtp-in.l.google.com` (`250
  2.0.0 OK`) e **entregue na caixa de entrada**;
- `gentillidiego@outlook.com` — aceito por
  `outlook-com.olc.protection.outlook.com` (`250 2.6.0`) e **entregue, porém
  classificado como spam**.

O envio em si funciona nos dois provedores (DKIM válido, DNS correto). A
classificação como spam pelo Outlook é uma questão de reputação de
remetente novo, não de configuração quebrada — o DMARC do domínio está em
`p=none` (modo observação) propositalmente até essa validação. Ação
recomendada, sem bloquear a operação: marcar o remetente
`nao-responda@sorrisodagentealagoas.com` como "não é spam"/seguro no
Outlook, e reavaliar depois de mais alguns envios reais se evolui o DMARC
para `p=quarantine`.

## Evolução durante a produção

### P1 — entrada e operação assistida

- adicionar o domínio atual ao Uptime Kuma;
- monitorar certificado, disco, backup vencido, Celery, Drive, PostgreSQL,
  Redis e Postfix;
- definir limites de CPU, memória e PIDs dos containers;
- revisar chaves SSH e restringir login root;
- ajustar workers e pool PostgreSQL conforme medição;
- implantar migrações versionadas;
- executar containers sem root e reduzir capabilities onde viável;
- completar dados e primeiro acesso dos usuários reais;
- refazer teste de carga separando capacidade de rate limit;
- homologar Recepção, Clínicos e Coordenação;
- validar entregabilidade Gmail/Outlook;
- confirmar competência SIGTAP vigente;
- preencher identificadores e importar XML no PEC antes de ativar e-SUS.

### P2 — primeiros 30 dias de estabilização

- criar staging separado;
- implantar CI com testes e auditoria;
- centralizar logs e métricas fora da VPS;
- automatizar restore periódico;
- criar segunda cópia de recuperação fora da mesma conta Google;
- revisar criptografia em repouso;
- revisar índices, queries lentas e crescimento do banco;
- evoluir DMARC após observação;
- eliminar alterações estruturais implícitas no boot.

### P3 — evolução posterior

- Portal do Paciente;
- visualizador DICOM avançado;
- BI com novas visões, indicadores e redesign;
- Endodontia e Prótese após validação operacional;
- CME/instrumental e inventário físico avançados;
- relatórios logísticos de perdas e reposição;
- retificação formal pós-assinatura com cadeia de versões;
- novos canais de notificação;
- integrações municipais adicionais.

Toda evolução em produção deve:

1. ter responsável e critério de aceite;
2. preservar backup e rollback;
3. usar pacote pequeno e rastreável;
4. incluir teste proporcional ao risco;
5. atualizar este README quando alterar estado, operação ou prioridade;
6. não misturar dado estimado com informação oficialmente homologada.

## Pontos de revisão técnica

A revisão geral de 21/06/2026 registrou riscos não bloqueantes para a candidata,
mas obrigatórios na estabilização:

- schema ainda é criado/alterado pelo boot em `database.py`; migrar para uma
  ferramenta versionada;
- Gunicorn calcula workers pela CPU do host; medir e limitar para a VPS
  compartilhada;
- processos ainda executam como root nos containers;
- não há ambiente separado de staging;
- logs e métricas permanecem majoritariamente na mesma VPS;
- criptografia em repouso ainda depende da proteção do host/provedor;
- antivírus de uploads ainda não foi implantado;
- assinatura atual é probatória interna, não ICP-Brasil;
- e-SUS, SIGTAP financeiro e economia gerada dependem de homologação externa;
- testes de release devem usar banco temporário isolado.

O modo direto de execução foi endurecido nesta candidata: `debug=False` por
padrão. O endpoint `/health` passou a expor a versão implantada.

## Documentação

Evidências e políticas atuais:

- [Go/No-Go de 21/06/2026](docs/auditoria_go_no_go_2026-06-21.md);
- [prontidão de produção](docs/auditoria_prontidao_producao_2026-06-19.md);
- [VPS e firewall Hostinger](docs/auditoria_vps_hostinger_2026-06-20.md);
- [RBAC e rotas](docs/matriz_rbac_rotas_2026-06-20.md);
- [dependências](docs/auditoria_dependencias_2026-06-20.md);
- [hardening web](docs/auditoria_hardening_web_2026-06-20.md);
- [OAuth e governança Google](docs/auditoria_oauth_governanca_2026-06-21.md);
- [governança mínima](docs/governanca_minima_2026-06-21.md);
- [backup e restore](docs/backup_restore_2026-06-08.md);
- [e-mail de produção](docs/email_producao_sorrisodagente_2026-06-16.md);
- [primeiro acesso e recuperação](docs/auth_primeiro_acesso_postfix_2026-06-16.md);
- [e-SUS XML LEDI](docs/esus_xml_ledi_2026-06-18.md);
- [preparação SIGTAP/e-SUS](docs/esus_sigtap_preparacao_2026-06-08.md);
- [referência clínica de especialidades e procedimentos SUS/SIGTAP](docs/referencia_clinica_especialidades_procedimentos_sigtap.pdf);
- [guia de configuração da WhatsApp Business Cloud API](docs/guia_configuracao_whatsapp_business_api.pdf) (roteiro passo a passo para habilitar o canal WhatsApp do módulo Comunicação);
- [manual base por perfil](docs/base_documentacao_manuais_usuarios.md);
- [plano mestre de manuais e treinamentos](docs/manuais_e_treinamentos/plano_mestre.md);
- [roteiros de videoaulas](docs/manuais_e_treinamentos/roteiros/README.md);
- [ambiente isolado de treinamento](docs/manuais_e_treinamentos/ambiente_treinamento.md);
- [arquitetura e regras](docs/system_architecture_and_rules.md).

Os documentos históricos continuam como evidência. Em caso de divergência de
status, prioridade ou versão, este README prevalece.

### Manuais, roteiros e videoaulas

Os materiais de treinamento ficam em `docs/manuais_e_treinamentos/`. O
andamento oficial é controlado no
[`plano_mestre.md`](docs/manuais_e_treinamentos/plano_mestre.md).

Regra obrigatória de acompanhamento:

1. ao iniciar ou concluir qualquer etapa, atualizar o quadro da atividade no
   plano mestre;
2. registrar data, responsável, resultado, pendência e próximo passo no
   histórico de avanços;
3. marcar uma etapa como concluída somente depois de verificar seu critério de
   aceite;
4. quando a mudança afetar escopo, prioridade ou prontidão da entrada
   assistida, atualizar também este README;
5. cada roteiro e manual deve informar a versão da aplicação usada na
   gravação e na captura das telas.

Primeiro pacote priorizado:

1. primeiro acesso;
2. novo usuário;
3. novo paciente;
4. triagem;
5. agenda;
6. TCLE;
7. anamnese;
8. plano de tratamento e evolução;
9. Central de Comando.

As gravações devem usar exclusivamente o ambiente local isolado em
`http://127.0.0.1:5103`. A base candidata de produção não deve receber usuários
ou pacientes fictícios. O ambiente pode ser recriado com
`scripts/training_environment.sh reset`.

## Registro consolidado

| Data | Marco | Resultado |
|---|---|---|
| 17/06/2026 | homologação inicial | branch/tag de homologação publicada |
| 18/06/2026 | continuidade | PostgreSQL interno, backup e restore validados |
| 19/06/2026 | reauditoria | bloqueadores de infraestrutura, RBAC e dependências identificados |
| 20/06/2026 | infraestrutura | legado e painéis isolados; firewall aplicado |
| 20/06/2026 | segurança | RBAC/IDOR, dependências e hardening web concluídos |
| 21/06/2026 | uploads | validação real de imagem/PDF/DICOM e derivados sem perda |
| 21/06/2026 | Drive | OAuth atômico, backup, restore e restart aprovados |
| 21/06/2026 | governança | política v1.0 concluída; aceite formal pendente |
| 21/06/2026 | release candidata | QA técnico aprovado; candidata `4.0.0-rc.1` |
| 22/06/2026 | treinamento | plano mestre, estrutura documental e nove roteiros iniciais criados |
| 22/06/2026 | ambiente de treinamento | Docker isolado, usuários fictícios e cenários de gravação validados |
| 22/06/2026 | assinatura da Anamnese | assinatura a rogo incorporada ao fluxo de produção com autenticação do CD, hash e comprovante probatório; ambiente de treinamento preservado |
| 24/06/2026 | exames e novo perfil | design do atestado e receituário unificado ao padrão da declaração de comparecimento; criado fluxo de solicitação de exame (Imagem e Clínico/Laboratorial) com filas dedicadas para Radiologia e para o novo perfil Análises Clínicas; simplificado o Exame Físico removendo a seção de Exames Complementares duplicada; commit `627be7d` |
| 24/06/2026 | produtividade SIGTAP e custos | crédito automático de produção SIGTAP/e-SUS ao atender Solicitação de Exame (imagem e laboratorial), creditado ao clínico solicitante; catálogo de tipos de exame restrito aos que têm código SIGTAP; novo grupo "Apoio Diagnóstico / Exames Laboratoriais"; tela "Custos SIGTAP" passou a cobrir os 138 códigos do catálogo (106 antes ausentes ficam como placeholder explícito, sem custo inventado) |
| 24/06/2026 | assinatura e produção | removida a exigência de assinatura do paciente na Anamnese (substituída por confirmação do clínico) e no Atendimento/Evolução (simplificado para assinatura única do Profissional Executor); Plano de Tratamento passa a ser só planejamento — produção/e-SUS só contam após o Executor confirmar a execução no Atendimento (`status` `Pendente` → `Planejado` → `Concluído`); 317 testes aprovados; commit `370c7b0` |
| 24/06/2026 | despersonalização do ambiente | removidos o paciente de teste e os procedimentos associados criados para validar as mudanças de assinatura/produção; ambiente de produção zerado (0 pacientes); usuários já cadastrados preservados; evidências de assinatura/auditoria mantidas (FK `ON DELETE SET NULL`), conforme a política de retenção de 20 anos |
| 24/06/2026 | módulo Comunicação | criado módulo administrativo de campanhas em massa por e-mail e WhatsApp Business Cloud API (integração direta com a Meta) e lembretes automáticos de consulta; novas tabelas `communication_templates/campaigns/messages/preferences`; permissões `comunicacao:view`/`write` restritas a contato e geografia do paciente (sem acesso a prontuário); canal WhatsApp desabilitado por padrão até credenciais serem configuradas; canal e-mail e lembretes operacionais desde já (lembretes desligados por padrão); 25 testes novos, suíte completa com 342 testes aprovados |
| 25/06/2026 | redesign do Estoque Operacional | tela reorganizada em abas (Visão Geral, Entrada de Mercadoria, Materiais, Lotes e Saldo, Ajustes e Perdas, Notas Fiscais, Fornecedores), mesmo padrão de abas com carregamento assíncrono do prontuário; corrigido bug do card "Materiais" (colisão de nome entre a chave `items` e o método `dict.items`); criado fluxo de Entrada de Mercadoria com conciliação obrigatória antes de afetar o saldo, alimentado por três origens — XML da NF-e (`lxml`, chave de acesso com proteção contra reimportação duplicada), PDF/DANFE de melhor esforço (`pdfplumber`, decodificação de CNPJ/série/número a partir da chave de acesso quando o dígito verificador confere) e lançamento manual de nota ou compra avulsa; novas tabelas `inventory_invoices`/`inventory_invoice_items`, CNPJ validado em `inventory_suppliers`, EAN em `inventory_items`, rastreabilidade de origem em `inventory_lots`; sem apuração de impostos (somente rastreabilidade/auditoria); mesmas permissões `inventory:view`/`write` de hoje; 19 testes novos, suíte completa com 361 testes aprovados |

## Git e publicação

Remoto oficial:

```text
git@github.com-gentillidiego:gentillidiego/GestaoClinica-SorrisodaGente.git
```

Fluxo:

```bash
git status
git diff --check
.venv/bin/pytest -q
docker compose up -d --build
git add <arquivos>
git commit -m "Consolida versão 4.0.0-rc.1"
git push
```

Decisão **GO** registrada em 25/06/2026 (Diego, Administrador). Tag de
produção `v4.0.0` criada e publicada no remoto oficial.

Estado em 25/06/2026: as mudanças de exames/RBAC, assinatura/produção, o
módulo Comunicação, o redesign do Estoque Operacional (entrada de mercadoria
com importação de XML/PDF e lançamento manual) e a conclusão do checklist
Go/No-Go estão publicados no remoto oficial, sob a tag `v4.0.0`.

---

© 2026 Programa Sorriso da Gente.
