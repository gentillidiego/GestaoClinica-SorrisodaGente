# Gestão Saúde Oral — Programa Sorriso da Gente

Versão candidata: **4.0.0-rc.1**

Atualização: **21/06/2026**

Status: **tecnicamente validada; produção plena ainda não aprovada**

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

Decisão atual: **NO-GO para produção plena com ampliação de pacientes reais**.

Bloqueadores restantes:

1. revogar no hPanel o token temporário da API Hostinger e remover o arquivo
   local;
2. confirmar 2FA, recuperação, custodiantes e revisão de sessões/apps da conta
   Google institucional;
3. obter o aceite formal da política de governança pela Dra. Cibely e indicar
   o responsável clínico/jurídico;
4. registrar a aprovação da coordenação para entrada assistida.

A versão `4.0.0-rc.1` identifica uma candidata técnica. Ela não representa
homologação municipal, aceite jurídico ou autorização para produção plena.

Evidência: [`docs/auditoria_go_no_go_2026-06-21.md`](docs/auditoria_go_no_go_2026-06-21.md).

## Escopo congelado da candidata

Incluído:

- triagem vinculada ao paciente;
- agenda por unidade e profissional;
- prontuário, anamnese, tratamento e evolução;
- Estomatologia e alerta de suspeita de neoplasia;
- exames odontológicos, de imagem e clínico-laboratoriais;
- documentos clínicos, consentimentos e assinatura probatória;
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
- Clínicos veem na Agenda apenas o próprio recorte;
- estoque não pode bloquear registro clínico;
- economia no BI permanece estimativa até homologação;
- XML e-SUS não pode ser anunciado como homologado antes de importação aceita
  no PEC municipal;
- TCLE e confirmação a rogo são exclusivos para paciente não alfabetizado e
  exigem autenticação do CD responsável.

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

- estoque, materiais e implantes;
- Central de Comando;
- Epidemiologia;
- BI executivo;
- referências SIGTAP e custos estimados;
- relatórios institucionais;
- preparação de remessas e-SUS APS.

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

Pendente antes de produção plena:

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
- [x] Endodontia e Prótese identificadas como ocultas.

Pendente:

- [ ] revogar e remover o token temporário Hostinger;
- [ ] confirmar 2FA/recuperação/custódias Google;
- [ ] obter aceite institucional da governança;
- [ ] indicar responsável clínico/jurídico;
- [ ] validar e-mails críticos em caixas Gmail e Outlook;
- [ ] entregar manuais e realizar treinamento por perfil;
- [ ] homologar fluxo ponta a ponta;
- [ ] registrar aprovação da coordenação;
- [ ] criar tag de produção somente após decisão **GO**.

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
- [manual base por perfil](docs/base_documentacao_manuais_usuarios.md);
- [arquitetura e regras](docs/system_architecture_and_rules.md).

Os documentos históricos continuam como evidência. Em caso de divergência de
status, prioridade ou versão, este README prevalece.

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

Tags de produção devem ser criadas somente depois de decisão **GO**. A tag
`v4.0.0-rc.1`, quando publicada, identifica apenas esta candidata técnica.

---

© 2026 Programa Sorriso da Gente.
