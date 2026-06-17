# Gestão Saúde Oral - Programa Sorriso da Gente

README 2.6 - análise de prontidão para produção atualizada em 17/06/2026.

Plataforma de gestão clínica, operacional e institucional de saúde bucal para o programa Sorriso da Gente. O sistema reúne triagem municipal, agenda, prontuário odontológico, estomatologia, exames, estoque, Central de Comando, BI, epidemiologia, relatórios e preparação SIGTAP/e-SUS APS.

Stack principal: Python/Flask, PostgreSQL 16, Redis, Celery, WeasyPrint e Docker Compose.

## Status Executivo

Leitura operacional atual:

- Fase 0 concluída e validada: núcleo clínico de alta urgência, estomatologia, alerta vermelho e PDF de encaminhamento.
- Fase 1 com base implementada: perfis, permissões, auditoria inicial, backup operacional, estrutura LGPD e hardening inicial de arquivos sensíveis. Ainda falta hardening de produção.
- Fase 2 com primeira versão operacional concluída: triagem, agenda, Central de Comando, fila inteligente, alertas, rastreabilidade, estoque, unidades de execução e resumo diário.
- Fase 3 iniciada e avançada: Epidemiologia, BI, relatórios institucionais, custos SIGTAP, PDF governamental e e-SUS draft. Ainda depende de homologações externas e integrações reais.
- Assinatura a rogo implementada para TCLE e confirmação do atendimento quando o paciente for não alfabetizado, com autenticação do CD, duas testemunhas, SHA-256, IP, user-agent, CPF do paciente e trilha de auditoria.
- Pacote probatório de assinatura padronizado para TCLE, confirmação do atendimento, Anamnese, Prótese, Pagamentos e Endodontia, com eventos em `signature_events`, registros em `digital_signatures`, link de comprovante e exibição na Linha do Tempo.
- Pré-cadastro profissional público implementado em `/cadastro/`, com página de confirmação dedicada, aprovação/recusa administrativa, criação de usuário em primeiro acesso e notificação por e-mail ao profissional.
- Fluxo de primeiro acesso e recuperação de senha implementado: profissional aprovado entra com login + data de nascimento, define senha definitiva, confirma e-mail e pode redefinir senha por link temporário.
- E-mail transacional configurado com serviço Docker `gestaosaudeoral-mail`, Postfix send-only, OpenDKIM, SPF, DKIM, DMARC e PTR/rDNS solicitado/registrado via API da Hostinger.
- Módulo de Endodontia ampliado até a Etapa E10 em nível MVP clínico-operacional, mas **não é prioridade de evolução neste momento**.
- Endodontia e Prótese permanecem temporariamente ocultas da navegação do prontuário por decisão operacional; os módulos não foram removidos.
- Decisão de 17/06/2026: escopo congelado para Endodontia, Prótese, Portal do Paciente e evoluções de BI até o Go/No-Go de produção. O BI existente pode ser validado e usado como apoio gerencial, mas não deve receber novas visões, indicadores, redesign ou ampliações antes da produção assistida.
- Última validação registrada em 16/06/2026: `.venv/bin/pytest -q` com `190 passed`; Docker em execução; `/health` saudável com `database=ok`.
- Status de produção: **não liberar produção plena ainda**. A aplicação está funcional e validada em Docker, mas ainda exige fechamento dos bloqueadores P0 de infraestrutura, LGPD, backup/restore, homologação operacional e aceite formal listados em `Plano de Prontidão para Produção`.

Prioridade atual de trabalho:

1. Atender as modificações solicitadas pelo Diego antes de iniciar novo passo a passo de evolução.
2. Manter o sistema funcional em Docker, com testes verdes e `/health` saudável após cada mudança relevante.
3. Preservar as regras operacionais já consolidadas: triagem não define unidade; agenda define unidade; Central respeita o recorte da agenda.
4. Não iniciar melhorias novas de Endodontia, Prótese, Portal do Paciente, BI ou UX da Central de Comando antes do Go/No-Go de produção.
5. Antes de produção plena, executar o plano P0 de produção e registrar evidências no Git.

Fora do foco imediato:

- Refinamentos do módulo de Endodontia.
- Melhorias de UX da Endodontia.
- Refinamentos ou reativação operacional de Prótese.
- Portal do Paciente.
- Novos painéis, indicadores, visões, redesign ou ampliações do BI.
- Melhorias de UX da Central de Comando.
- Visualizador DICOM avançado.
- Integrações externas reais de e-SUS/WhatsApp/SMS sem credenciais, endpoint e homologação.

## Regras Permanentes

Sempre atualizar este README quando houver mudança em fluxo, tela, regra de negócio, permissão, integração, relatório, métrica, teste ou decisão de produto.

Também atualizar `docs/base_documentacao_manuais_usuarios.md` quando a mudança impactar treinamento, uso por perfil, rotina operacional ou manual de usuário.

VOLTE E VERIFIQUE:

- Alterações em `templates/`, `static/` ou Python exigem `docker compose up -d --build`.
- Não registrar senhas, tokens, chaves, credenciais ou dados reais sensíveis neste README.
- Validar `git diff --check`, testes automatizados e `/health` antes de encerrar uma fase.
- Se houver mudança no fluxo de triagem, agenda ou unidade de execução, atualizar também os manuais de Triagem, Recepção, Agenda e Coordenação.
- A triagem não define unidade de execução. A unidade é determinada depois, no agendamento da consulta.
- Estoque e materiais são opcionais nesta etapa e não podem bloquear evolução clínica, assinatura, e-SUS ou alta.
- Economia gerada no BI é estimativa operacional até homologação formal pela gestão pública.
- e-SUS APS está em draft, validação interna e pré-envio simulado. Transmissão real depende de endpoint, credenciais e homologação da prefeitura.
- Backups Docker devem usar `scripts/docker_backup_postgres.sh`, que executa `pg_dump` via `postgres:16-alpine`, compatível com o PostgreSQL 16 do projeto.
- AVISO RELEVANTE: os módulos `Endodontia` e `Prótese` estão temporariamente ocultos da navegação do prontuário do paciente. Sempre informar ao usuário que esses módulos estão ocultos por decisão operacional temporária, não removidos do sistema.
- TCLE e confirmação de atendimento permitem assinatura a rogo apenas para paciente não alfabetizado, com login/senha do CD responsável e duas testemunhas. Não usar esse fluxo como substituto de conveniência para assinatura comum.

## Arquitetura Docker

| Container | Função | Porta |
|---|---|---|
| `gestaosaudeoral-web` | Flask + Gunicorn/Gevent | `5003` |
| `gestaosaudeoral-postgres` | PostgreSQL 16 | `5433` no host |
| `gestaosaudeoral-redis` | Redis, sessão, cache e broker | interno |
| `gestaosaudeoral-celery` | Worker Celery para PDFs e tarefas | interno |
| `gestaosaudeoral-beat` | Scheduler Celery Beat | interno |
| `gestaosaudeoral-mail` | Postfix send-only + OpenDKIM para e-mail transacional | interno, SMTP `25` |

Volumes nomeados:

- `postgres_data_oral`: banco de dados.
- `uploads_oral`: exames, radiografias e fotos clínicas.
- `pdf_temp_oral`: PDFs temporários/gerados.
- `logs_oral`: logs.
- `backups_oral`: backups operacionais.
- `redis_data_oral`: Redis.
- `deploy/mail/dkim`: chave DKIM privada local montada no container de e-mail. Diretório ignorado pelo Git, exceto `.gitkeep`.

## Comandos Operacionais

Subir ambiente:

```bash
docker compose up -d
```

Rebuild obrigatório após mudanças em código, templates ou estáticos:

```bash
docker compose up -d --build
```

Health check:

```bash
curl http://localhost:5003/health
```

Criar admin inicial:

```bash
ADMIN_USERNAME=admin ADMIN_PASSWORD=senha_segura docker compose run --rm gestaoclinica python create_admin.py
```

Rodar testes:

```bash
.venv/bin/pytest -q
git diff --check
```

Backup:

```bash
scripts/docker_backup_postgres.sh
```

Validar restauração em banco temporário:

```bash
scripts/docker_restore_verify.sh
```

Dados fictícios para demonstração:

```bash
docker compose exec -T gestaoclinica flask --app app:app seed-demo-data --count 100 --label "Demonstração institucional"
```

Coordenada territorial manual:

```bash
docker compose exec -T gestaoclinica python scripts/upsert_territorial_location.py \
  --scope bairro \
  --municipio "Maceió" \
  --bairro "Centro" \
  --lat -9.66599 \
  --lon -35.735 \
  --source manual
```

## Acesso Git/GitHub

O repositório remoto oficial deve usar o alias SSH local `github.com-gentillidiego`, que aponta para a chave específica do GitHub:

```bash
git remote set-url origin git@github.com-gentillidiego:gentillidiego/GestaoClinica-SorrisodaGente.git
```

Configuração esperada em `~/.ssh/config`:

```sshconfig
Host github.com-gentillidiego
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_github_gentillidiego
```

Testar autenticação SSH:

```bash
ssh -T git@github.com-gentillidiego
```

Resultado esperado:

```text
Hi gentillidiego! You've successfully authenticated, but GitHub does not provide shell access.
```

Publicar a branch e a tag de homologação:

```bash
git push origin main
git push origin homologacao-2026-06-17
```

VOLTE E VERIFIQUE:

- Não commitar chave privada SSH.
- A chave privada esperada é `~/.ssh/id_ed25519_github_gentillidiego`.
- A chave pública fica em `~/.ssh/id_ed25519_github_gentillidiego.pub` e pode ser cadastrada no GitHub quando necessário.
- Se o remoto voltar para `git@github.com:...`, o push pode falhar com `Permission denied (publickey)`.

## Variáveis de Ambiente

Copiar `.env.example` para `.env` e preencher:

| Variável | Uso |
|---|---|
| `SECRET_KEY` | Chave Flask |
| `DATABASE_URL` | URL PostgreSQL |
| `POSTGRES_PASSWORD` | Senha PostgreSQL |
| `REDIS_URL` | URL Redis |
| `ADMIN_USERNAME` | Admin inicial |
| `ADMIN_PASSWORD` | Senha do admin inicial |
| `BACKUP_DIR` | Diretório de backups |
| `BACKUP_RETENTION_DAYS` | Retenção local |
| `REPORTS_SCHEDULER_ENABLED` | Liga/desliga rotina automática de relatórios |
| `REPORTS_SCHEDULE_DAY` | Dia de geração mensal |
| `REPORTS_SCHEDULE_HOUR` | Hora de geração |
| `REPORTS_SCHEDULE_MINUTE` | Minuto de geração |
| `REPORTS_SCHEDULE_TYPES` | Tipos de relatório automático |
| `SIGTAP_DEFAULT_COMPETENCE` | Competência SIGTAP padrão |
| `TZ` | Fuso horário |
| `APP_BASE_URL` | URL pública usada nos links de e-mail, ex.: `https://sorrisodagentealagoas.com` |
| `SMTP_HOST` | Host SMTP interno, atualmente `mail` no Docker Compose |
| `SMTP_PORT` | Porta SMTP, atualmente `25` |
| `SMTP_USE_TLS` | Liga STARTTLS quando aplicável |
| `SMTP_USE_SSL` | Liga SMTP SSL quando aplicável |
| `SMTP_USERNAME` | Usuário SMTP, vazio no Postfix interno |
| `SMTP_PASSWORD` | Senha SMTP, vazia no Postfix interno |
| `MAIL_FROM` | Remetente transacional, ex.: `nao-responda@sorrisodagentealagoas.com` |

VOLTE E VERIFIQUE: conferir `.env.example` sempre que adicionar nova variável.

## Perfis de Acesso

Perfis ativos:

1. Administrador.
2. Coordenação.
3. Clínicos.
4. Recepção.
5. CME / Estoque.
6. Radiologia.
7. Comunicação.
8. SSA/SMS.
9. Auditoria.

Perfis legados são mantidos como aliases internos e migrados automaticamente para os perfis canônicos.

VOLTE E VERIFIQUE: ao criar uma rota, botão ou item de menu, validar permissão em `constants.py`, template e blueprint.

Regra atual da Agenda:

| Perfil | Escopo de visualização | Pode gerenciar |
|---|---|---|
| Administrador | Agenda completa | Sim |
| Coordenação | Agenda completa | Sim |
| Recepção | Agenda completa | Sim |
| Clínicos | Apenas a própria agenda | Sim, apenas a própria agenda |
| CME / Estoque, Radiologia, Comunicação, SSA/SMS e Auditoria | Sem acesso à tela de Agenda | Não |

VOLTE E VERIFIQUE: o escopo dos Clínicos deve ser aplicado por `dentista_id = current_user.id` no backend. Não basta ocultar filtros ou botões na interface.

## Pré-cadastro, Primeiro Acesso e Senha

Rotas públicas e administrativas:

- `/cadastro/`: página pública de pré-cadastro profissional.
- `/admin/professional-registrations`: análise administrativa dos pré-cadastros.
- `/primeiro-acesso`: valida login + data de nascimento para profissional aprovado.
- `/primeiro-acesso/definir-senha`: define senha definitiva e confirma e-mail.
- `/esqueci-senha`: solicita link de recuperação.
- `/redefinir-senha?token=...`: troca senha com token temporário.

Fluxo atual:

1. A equipe envia o link público `/cadastro/` ao profissional.
2. O profissional informa dados principais, classe pretendida, dados profissionais quando exigidos e login desejado.
3. Após envio, a tela não recarrega o formulário; exibe confirmação grande com protocolo e botão para login.
4. A administração aprova ou recusa em `/admin/professional-registrations`.
5. Ao aprovar, o sistema cria usuário ativo com `is_first_access = true` e envia e-mail de liberação com link para primeiro acesso.
6. Ao recusar, o sistema exige observação administrativa no backend e envia e-mail com o motivo ao profissional.
7. No primeiro acesso, o profissional usa login + data de nascimento, define senha definitiva duas vezes e confirma o e-mail de recuperação.
8. No login comum, há botão `Esqueci minha senha`, que envia e-mail com token temporário de redefinição.

Estado de UX/UI:

- A tela pública de cadastro foi reorganizada com formulário maior, painel lateral de orientação, botão de login e confirmação dedicada pós-envio.
- A tela administrativa de pré-cadastros foi convertida de tabela para cards por solicitação, com ações separadas para aprovar e recusar, evitando conflito de foco/click em formulários dentro de tabela.
- O botão de pré-cadastro foi removido da tela de login padrão; o link deve ser enviado diretamente pela equipe.

E-mail transacional:

- Serviço Docker `gestaosaudeoral-mail` com Postfix send-only e OpenDKIM.
- DNS autoritativo configurado na Hostinger: `A mail`, `MX`, `SPF`, `DKIM` e `DMARC`.
- PTR/rDNS do IPv4 registrado na API Hostinger para `mail.sorrisodagentealagoas.com`; a consulta pública pode depender de propagação/cache.
- Documentação operacional: `docs/auth_primeiro_acesso_postfix_2026-06-16.md` e `docs/email_producao_sorrisodagente_2026-06-16.md`.

VOLTE E VERIFIQUE:

- Nunca exibir novamente o link público de pré-cadastro na tela de login sem decisão explícita.
- Motivo de recusa deve continuar obrigatório no backend, mesmo que não use `required` no HTML.
- Testar envio real quando aprovar/recusar com e-mail externo.
- Não commitar `deploy/mail/dkim/mail.private` nem qualquer token/senha.

## Fluxo Operacional Principal

1. Cadastro do paciente:
   - A entrada operacional começa em `Operação Clínica > Novo Paciente`.
   - A equipe cadastra o paciente na ficha já existente.
   - O cadastro não pede senha de triagem.

2. Triagem de campo:
   - A equipe cria uma ação por município, data, local e observações.
   - Ao gerar senha, a equipe seleciona um paciente já cadastrado e a especialidade da demanda.
   - A senha é criada no formato `MUN-ESP-000` e já fica vinculada ao paciente.
   - Um mesmo paciente pode ter mais de uma senha quando houver mais de uma demanda/especialidade.
   - A senha representa a demanda eleita no município.
   - A triagem não define unidade de execução.

3. Pacientes / Prontuários:
   - O prontuário exibe todos os encaminhamentos/senhas de triagem vinculados ao paciente.
   - A lista de pacientes agrega as senhas sem duplicar o paciente.

4. Agendamento:
   - A unidade de execução é determinada na Agenda.
   - A população eleita pela triagem é direcionada para a unidade definida pela operação.
   - Listas de senhas exibem o destino quando já existe consulta agendada.

5. Atendimento clínico:
   - Prontuário, anamnese, exames, plano de tratamento, odontograma, estomatologia, prótese, endodontia, materiais e assinaturas.

6. Gestão:
   - Central de Comando monitora fila, alertas, pendências, metas, agenda, gargalos e resumo diário.
   - Epidemiologia, BI e relatórios consolidam dados para gestão pública e operação.

VOLTE E VERIFIQUE:

- Se a triagem voltar a pedir unidade, o fluxo estará incorreto.
- Se a agenda não exigir unidade, a execução operacional ficará sem destino.
- Se a Central filtrar senha/fila por unidade da triagem, estará errado. Unidade vale onde há consulta/agendamento.

## Módulos Atuais

### Triagem Municipal

Rotas principais:

- `/triagem/`
- `/triagem/acoes/nova`
- `/triagem/acoes/<id>`
- `/triagem/senhas`

Estado:

- Cria ações municipais de campo.
- Gera senha por paciente já cadastrado e especialidade.
- Permite mais de uma senha por paciente quando houver múltiplas demandas.
- Lista senhas e mostra destino quando existe consulta agendada.
- Não define unidade de execução.

### Agenda

Rotas principais:

- `/agenda/`
- `/agenda/nova`
- `/agenda/<consulta_id>/editar`

Estado:

- Agenda semanal.
- Status: Pendente, Confirmado, Realizado, Cancelado, Faltou.
- Define unidade de execução da consulta.
- Audita criação, edição, cancelamento e mudança de status.
- Regra de acesso vigente: Administrador, Recepção e Coordenação veem e gerenciam a agenda completa; Clínicos veem, criam, editam, cancelam e alteram status apenas da própria agenda, vinculada ao seu `dentista_id`.
- A rota `/agenda/`, os filtros, a criação, a edição, o cancelamento/status e os resumos de Agenda do Dashboard/Central de Comando devem respeitar esse escopo no backend, não apenas no menu ou template.
- Perfis sem `agenda:view` não devem visualizar a tela de Agenda, atalhos diretos ou resumos operacionais da Agenda fora dos módulos autorizados.
- O sistema usa cancelamento por status `Cancelado`; não há exclusão física de consulta na interface atual.

### Prontuário e Clínica

Inclui:

- Cadastro.
- Anamnese.
- Exames.
- Atendimento/evolução.
- Estomatologia, posicionada logo após Atendimento/evolução na navegação do prontuário.
- Plano de tratamento e odontograma.
- Aba do plano renomeada para `Plano de Tratamento`, com seleção de especialidade antes do código SUS/SIGTAP.
- A lista SUS/SIGTAP do plano é filtrada pela especialidade escolhida: Atenção Primária/Clínico Geral, Endodontia, Periodontia, Cirurgia Bucomaxilofacial, Prótese Dentária, Alta Complexidade/Hospitalar e Diagnóstico/Estomatologia/Radiologia.
- Prótese, temporariamente oculta da navegação do prontuário.
- Endodontia, temporariamente oculta da navegação do prontuário.
- Visual.
- Materiais.
- Linha do Tempo.

Estado:

- Primeira versão completa e validada.
- Alertas locais em abas responsáveis.
- Linha do tempo consolidada.
- Assinaturas existem em fluxos clínicos, mas assinatura digital institucional ainda está pendente.
- TCLE e assinatura do paciente na evolução/atendimento aceitam assinatura comum em tela e assinatura a rogo para paciente não alfabetizado.
- Assinatura a rogo exige autenticação do CD responsável por login/senha, declaração de leitura e explicação ao paciente, duas testemunhas e registro probatório com SHA-256, CPF do paciente, IP, user-agent, timestamp e auditoria.
- O comprovante consolidado de assinatura fica disponível em `/documents/signatures/<event_id>` e pode ser acessado pela Linha do Tempo ou pelo TCLE impresso quando houver evento vinculado.
- Assinaturas clínicas em Anamnese, Prótese, Pagamentos e Endodontia também geram evento probatório com SHA-256 e vínculo técnico ao documento, mesmo quando usam assinatura comum em tela.
- Plano de Tratamento registra especialidade SIGTAP escolhida e valida se o código selecionado pertence à especialidade informada.
- No prontuário do paciente, as abas visíveis seguem a ordem: Paciente, Anamnese, Exames, Plano de Tratamento, Atendimento, Estomatologia, Receituário, Atestado, Visual, Materiais quando permitido e Linha do Tempo.
- Endodontia e Prótese permanecem implementadas, mas estão ocultas temporariamente da navegação do prontuário.

### Endodontia

Rotas principais:

- `/endodontia/<patient_id>/add_element`
- `/endodontia/followup/<endo_id>`
- `/endodontia/followup/save_details/<endo_id>`
- `/endodontia/followup/add/<endo_id>`
- `/endodontia/followup/<endo_id>/images/upload`
- `/endodontia/image/<image_id>`
- `/endodontia/proservation/<proservation_id>/evaluate`
- `/endodontia/followup/<endo_id>/budget/generate`

Estado:

- Existe como aba do prontuário.
- Permite iniciar acompanhamento por elemento dentário.
- Registra exame clínico/radiográfico básico, diagnóstico livre, grampo e finalidade protética.
- Registra canais com CAD, referência, CT, lima inicial/final, cone e selamento.
- Registra sessões endodônticas numeradas, com etapa realizada, status da sessão, total planejado, próxima sessão prevista e janela de retorno.
- Registra protocolo biomecânico por sessão: LAI, técnica, sistema, liga do instrumento, solução irrigadora, EDTA, tempo, agitação, volume, medicação intracanal, veículo, quantidade e selamento provisório.
- Atualiza status do tratamento entre aguardando início, em andamento, aguardando retorno, obturado aguardando restauração, concluído, abandono e retratamento necessário.
- Permite assinatura do paciente e validação por usuário com permissão clínica.
- Pendências de assinatura aparecem como alerta local e na Central de Comando.
- Retornos endodônticos vencidos aparecem como pendência clínica/alerta operacional na Central de Comando para recepção e coordenação.
- A aba exibe vínculo com a anamnese existente do prontuário, sem duplicar formulário de anamnese.
- Cancelamento de acompanhamento passou a ser lógico, com motivo, credencial clínica e auditoria; casos cancelados deixam de aparecer como ativos.
- UX inicial da aba foi revisada com cards responsivos, estado vazio orientado à ação e linguagem alinhada a profissional/dentista responsável.
- A ficha de acompanhamento possui campos estruturados iniciais para queixa endodôntica, exame extraoral/intraoral e periodonto do elemento.
- A tela de acompanhamento resume riscos extraídos da anamnese existente, como alergias, medicações, condições sistêmicas, gestação, reação à anestesia, sangramento e históricos clínicos relevantes.
- Diagnóstico pulpar e apical estruturados seguem taxonomia AAE inicial, com CID-10 sugerido, tipo de fluxo e bloqueio de nova evolução quando o diagnóstico obrigatório está pendente.
- Odontometria por canal registra ponto de referência coronário, CAD, CRI, CAI, CRD calculado, CRT sugerido/final, localizador apical, confirmação eletrônica e justificativa auditável quando o CRT final diverge do sugerido.
- A ficha de acompanhamento exibe painel de sessões, número da próxima sessão, status endodôntico atual, planejamento de sessões e retorno previsto.
- O protocolo E5 usa a anamnese vinculada para bloquear hipoclorito quando houver alergia compatível, bloquear material eugenólico quando houver alergia a eugenol e destacar alerta persistente de látex.
- A obturação final E6 registra cone principal, calibre ISO, conicidade, prova de cone, tug-back, CRT confirmado, cimento obturador, classe/lote/validade, técnica obturadora, radiografia final, gaps/voids, controle de qualidade, restauração definitiva e selamento coronário adequado.
- Ao concluir obturação sem restauração definitiva, o status vai para `obturado_aguardando_restauracao`, a ficha exibe pendência restauradora e a Central de Comando lista o caso em pendências clínicas.
- A E7 cria upload protegido de imagens endodônticas por caso, sessão, canal, etapa visual, data de captura, equipamento e anotação clínica, usando `endodontia_imagens`.
- Imagens endodônticas entram na Biblioteca Visual do paciente como origem `Endodontia`, com categorias periapical inicial, odontometria, prova de cone, final de qualidade, proservação 6m/1a/2a/4a, CBCT e outra.
- A E8 cria proservações planejadas de 6, 12 e 24 meses após obturação realizada, com retorno de 48 meses quando há lesão periapical extensa, registra critérios clínicos/radiográficos de Strindberg e mostra proservações vencidas na Central.
- A E9 gera orçamento gerencial por canal, classifica complexidade por grupo dentário/número de canais, diferencia tratamento de retratamento, usa TUSS/SIGTAP como referência e bloqueia orçamento endodôntico para `polpa_normal`.

Plano de ampliação:

- Expandir para ficha endodôntica estruturada com diagnóstico AAE, testes diagnósticos, odontometria calculada, protocolo biomecânico, irrigação, medicação intracanal, obturação, proservação e alertas operacionais.
- Reaproveitar infraestrutura já existente de RBAC, TCLE geral, biblioteca visual, estoque/materiais, auditoria, agenda, Central de Comando, LGPD inicial e assinatura clínica transitória.
- Não duplicar módulos já existentes; integrar Endodontia com prontuário, exames/imagens, agenda, materiais, documentos, BI e Central.

VOLTE E VERIFIQUE:

- Diagnóstico endodôntico deve ser estruturado, não apenas texto livre, antes de liberar fases avançadas.
- TCLE específico endodôntico ainda não existe.
- Soft delete/versionamento endodôntico ainda precisa substituir exclusão física.
- Assinatura digital ICP-Brasil/Gov.br continua pendente institucional, mesmo com validações internas atuais.
- Visualizador DICOM avançado ainda é fase futura; arquivos TIFF/DICOM podem ser armazenados/baixados com proteção, mas sem janela/nível, medição ou anotações salvas.

### Estomatologia e Câncer de Boca

Rotas principais:

- `/patients/red-alerts`
- `/patients/<id>/estomatologia/save`
- `/documents/<patient_id>/estomatologia/<est_id>/pdf`

Estado:

- Ficha clínica especializada.
- Suspeita de neoplasia ativa alerta vermelho.
- Evolução fotográfica de lesões.
- Encaminhamento expresso em PDF.

### Biblioteca Visual

Estado:

- Consolida radiografias, fotos clínicas, lesões, antes/depois, evolução e documentos complementares.
- Consolida imagens endodônticas E7 por etapa clínica, dente, canal e sessão.
- Upload com legenda e metadados.
- Rotas autenticadas para visualização.

VOLTE E VERIFIQUE:

- Criptografia em repouso ainda está pendente.
- Permissões finas por tipo de ação visual ainda precisam evoluir.
- Política de retenção/descarte ainda precisa ser formalizada.

### Estoque, Materiais e Implantes

Rotas principais:

- `/admin/inventory`
- Aba `Materiais` no prontuário.

Estado:

- Cadastro de materiais e lotes.
- Ajuste/perda com motivo e senha.
- Uso de material vinculado ao paciente.
- Custo por uso.
- Implante gera controle de pós-operatório.
- Alertas de estoque baixo, vencimento e implante sem retorno.

VOLTE E VERIFIQUE:

- Uso de estoque continua opcional.
- Falta inventário físico periódico.
- Falta relatório de perdas, consumo médio e previsão de reposição.
- Falta assinatura digital formal da baixa administrativa.

### Central de Comando

Rota:

- `/command-center`

Inclui:

- Pacientes do dia.
- Produção.
- Agenda por status.
- Fila Inteligente SUS.
- Alertas operacionais.
- Gargalos por especialidade.
- Pendências clínicas.
- Retornos endodônticos vencidos.
- Métricas operacionais de fila.
- Metas automáticas.
- Resumo diário imprimível.
- CSV do resumo.

Filtros:

- Município.
- Especialidade.
- Profissional.
- Unidade.
- Período.

VOLTE E VERIFIQUE:

- Unidade filtra agenda/consultas.
- Unidade não deve filtrar senha de triagem como se a triagem definisse destino.
- Resumo diário e CSV devem preservar o recorte atual.

### Epidemiologia

Rota:

- `/epidemiologia`

Inclui:

- Lesões.
- Suspeita oncológica.
- Câncer confirmado.
- Perda dentária por odontograma.
- Absenteísmo.
- Demanda reprimida.
- Áreas críticas.
- Mapa com coordenadas municipais e drill-down territorial.

VOLTE E VERIFIQUE:

- Coordenadas finas de bairros, locais e ações de triagem ainda precisam ser cadastradas se o mapa for usado para decisão territorial precisa.
- Mapa cartográfico com polígonos/tiles oficiais é refinamento futuro.

### BI Executivo

Rota:

- `/bi`

Inclui:

- Produção.
- Fila.
- Impacto social.
- Metas automáticas.
- Comparativos mensais.
- Rankings.
- Visões: Geral, Prefeitura, SSA, SMS, Coordenação Clínica e Auditoria.
- Economia gerada estimada.
- PDF governamental da visão atual.

VOLTE E VERIFIQUE:

- Economia gerada é estimativa até homologação formal.
- Custos demonstrativos precisam ser substituídos por referências oficiais aprovadas.

### Custos SIGTAP

Rota:

- `/admin/finance/cost-references`

Inclui:

- Revisão manual de referências.
- Importação CSV.
- Status de metodologia.
- Auditoria de alteração, homologação e importação.

### Relatórios Institucionais

Rota:

- `/reports/institutional`

Inclui:

- Prévia.
- Exportação PDF assíncrona.
- Recortes Institucional, SSA e SMS.
- Histórico.
- Assinatura técnica SHA-256.
- Scheduler mensal por Celery Beat.

VOLTE E VERIFIQUE:

- Falta assinatura digital homologada.
- Envio transacional por e-mail existe para autenticação e pré-cadastro; envio institucional de relatórios por e-mail ainda não foi ativado.

### SIGTAP/e-SUS APS

Rota:

- `/admin/integrations/esus`

Inclui:

- Catálogo local SIGTAP.
- Importador de competência oficial.
- Vínculo de procedimento clínico com SIGTAP.
- Lote draft e-SUS APS.
- Checklist de homologação.
- Validação interna.
- Pré-envio simulado.
- Download JSON.
- Relatório de homologação em PDF.

VOLTE E VERIFIQUE:

- Transmissão real não está implementada.
- Depende de endpoint, HTTPS, autenticação, CNES/INE, versão PEC/e-SUS APS e regras da prefeitura.

## Status por Fase

### Fase 0 - Concluída

Entregue em 29/05/2026.

Pronto:

- Estomatologia.
- Alerta vermelho.
- Evolução fotográfica.
- Fila vermelha.
- Encaminhamento expresso em PDF.

### Fase 1 - Base Implementada, Hardening Pendente

Pronto:

- Perfis simplificados.
- Permissões por módulo.
- Migração de papéis legados.
- Auditoria inicial.
- Tela de auditoria.
- Filtro de auditoria por período, IP e severidade.
- Backup operacional local.
- Rate limiting.
- Testes de segurança.

Pendente:

- Criptografia robusta em repouso.
- Política formal de retenção/descarte.
- Bloqueio completo de acesso direto a arquivos sensíveis.
- Consentimento versionado com revogação.
- Auditoria plena de visualização sensível.
- Assinatura digital institucional.
- Backup diário automatizado.
- Replicação externa e teste de restauração.

### Fase 2 - Primeira Versão Operacional Concluída

Pronto:

- Central de Comando.
- Fila Inteligente SUS v2.
- Agenda com falta operacional.
- Alertas clínicos e operacionais.
- Linha do tempo do paciente.
- Biblioteca visual.
- Estoque e materiais.
- Pós-operatório de implante.
- Métricas de fila.
- Resumo diário e CSV.
- Metas automáticas.
- Unidades de execução administrativas.
- Correção da regra de triagem e destino operacional.

Pendente:

- Instrumental esterilizado, caixas cirúrgicas e ciclos de esterilização.
- Intercorrências, conduta pós-operatória e alta clínica mais detalhadas.
- Hardening LGPD do módulo visual.
- Custos por procedimento, especialidade, profissional, município e tipo de material.
- Produtividade por equipe, cadeira, especialidade, período e unidade, se a segunda unidade for usada.
- Inventário físico e relatórios logísticos avançados.
- Treinamento e implantação assistida.

### Fase 3 - Iniciada e Avançada

Pronto:

- Epidemiologia v3.
- Mapa com coordenadas municipais.
- Drill-down territorial.
- BI Governamental v2.
- PDF governamental do BI.
- Custos SIGTAP configuráveis.
- Relatórios institucionais/SSA/SMS.
- Automação mensal com Celery Beat.
- Prontidão SIGTAP/DataSUS.
- e-SUS APS draft.
- Pré-envio simulado.
- Relatório de homologação e-SUS.
- Validação interna de formato para CNS/CPF, CNS profissional, CBO, CNES, INE/equipe e CRO-UF.
- Dados demonstrativos completos.
- Pré-cadastro profissional público, primeiro acesso e recuperação de senha com e-mail transacional.
- Postfix/OpenDKIM em Docker, DNS de e-mail configurado e documentação operacional.

Pendente:

- Coordenadas reais finas de bairros, locais e ações.
- Mapa cartográfico oficial, se necessário.
- Homologação formal da metodologia de economia.
- Substituição de valores demonstrativos por referências oficiais.
- Calendário de revisão dos valores e responsável técnico.
- Assinatura digital ICP-Brasil/Gov.br ou provedor homologado.
- Envio institucional de relatórios por e-mail, se a gestão decidir automatizar distribuição.
- Validação da versão PEC/e-SUS APS da prefeitura.
- Transmissão real para e-SUS quando houver endpoint e credenciais.
- Validação final de compatibilidade externa com ambiente da prefeitura.

## Plano de Prontidão para Produção

Objetivo:

- Transformar a versão funcional atual em uma implantação segura, auditável e operável em produção, com critérios claros de entrada, responsáveis e evidências.
- Encerrar o desenvolvimento aberto, congelar escopo, preparar o ambiente final e iniciar operação assistida sem misturar dados demonstrativos com pacientes reais.

### Diagnóstico Profundo em 16/06/2026

| Área | Situação | Decisão |
|---|---|---|
| Funcionalidade clínica e operacional | Prontuário, triagem, agenda, Central, BI, relatórios, assinatura probatória, pré-cadastro, primeiro acesso e e-mail transacional estão funcionais | Pode seguir para homologação assistida |
| Testes automatizados | `.venv/bin/pytest -q` com `190 passed` em 16/06/2026 | Base técnica favorável |
| Docker local/VPS | Web, PostgreSQL, Redis, Celery, Beat e Mail em execução | Base funcional |
| Git/release | Branch `main` está `ahead 21` em relação a `origin/main` | Precisa publicar/taguear antes de release |
| Banco atual | Base contém `patients_demo=100`, `patients_total=100`, `users_active=4` | Bloqueia entrada com pacientes reais até limpeza/decisão de migração |
| PostgreSQL | `docker-compose.yml` publica `5433:5432` no host | Bloqueia produção plena se a porta estiver acessível externamente |
| Domínio/e-mail | Domínio e e-mail transacional configurados; Postfix/OpenDKIM ativo | Falta validação final de entrega e monitoramento |
| HTTPS/proxy/firewall | Não há evidência final registrada no README de proxy HTTPS/firewall de produção | Bloqueia produção plena |
| Segurança/LGPD | Hardening inicial existe, mas retenção, descarte, criptografia em repouso e matriz de acesso final seguem pendentes | Bloqueia produção plena |
| Backup/continuidade | Scripts existem e restore já foi validado em etapa anterior, mas falta automação diária e cópia externa atual | Bloqueia produção plena |
| Homologação operacional | Fluxos prontos, mas falta aceite formal por perfil com usuários reais | Bloqueia uso oficial amplo |
| Treinamento | Base documental existe; manuais finais por perfil ainda pendentes | Bloqueia entrada com equipe ampla |
| e-SUS/SIGTAP | e-SUS permanece draft/simulação; SIGTAP depende de competência oficial e homologação | Não bloqueia piloto interno, mas bloqueia anúncio de integração real |
| Assinatura digital formal | Pacote probatório SHA-256/auditoria implementado; decisão institucional ICP-Brasil/Gov.br/outro ainda pendente | Não bloquear piloto se houver aceite jurídico formal; bloquear promessa de assinatura ICP |

Conclusão executiva:

- A aplicação está **apta para homologação assistida controlada**.
- A aplicação **não deve entrar em produção plena com pacientes reais** antes de fechar os P0 abaixo.
- O maior risco atual não é funcionalidade clínica; é governança de produção: exposição de portas, segredos, base demo, LGPD, backup externo, aceite e treinamento.
- A entrada recomendada é em duas etapas: `produção assistida` com checklist fechado e depois `produção plena` após evidências e aceite formal.

### Próximos Passos para Finalizar Desenvolvimento

Ordem recomendada:

1. Congelar escopo funcional.
   - Não abrir novas frentes de Endodontia, Prótese, Portal do Paciente, BI, UX da Central, WhatsApp ou integrações externas antes do Go/No-Go.
   - Usar o BI atual apenas para validação, leitura gerencial e relatórios já existentes; novas métricas, telas ou mudanças visuais ficam para pós-produção assistida.
   - Aceitar apenas correções bloqueantes, ajustes de texto, permissões e estabilidade.

2. Publicar e organizar Git.
   - Fazer `git push` dos commits locais quando Diego autorizar.
   - Criar tag de homologação, por exemplo `homologacao-2026-06-16`.
   - Registrar no README o hash da release usada em produção assistida.

3. Fechar infraestrutura de borda.
   - Definir proxy HTTPS final.
   - Restringir portas expostas.
   - Remover ou proteger a exposição do PostgreSQL `5433`.
   - Confirmar `/health` via HTTPS.

4. Fechar base real.
   - Decidir se produção começa vazia ou migrada.
   - Remover ou isolar `patients_demo=100`.
   - Criar usuários reais por perfil.
   - Trocar senhas temporárias e desativar usuários de teste.

5. Executar hardening LGPD final.
   - Confirmar proteção dos volumes `uploads_oral`, `pdf_temp_oral` e relatórios.
   - Validar tentativa de acesso direto a arquivos sem login.
   - Definir retenção/descarte, criptografia em repouso e rotina de incidente.

6. Automatizar backup e restore.
   - Agendar backup diário do PostgreSQL e uploads.
   - Enviar cópia para fora da VPS.
   - Rodar restore de verificação antes do go-live.

7. Homologar ponta a ponta.
   - Executar roteiro com Recepção, Clínico e Coordenação.
   - Validar assinatura comum e assinatura a rogo.
   - Validar pré-cadastro, aprovação, primeiro acesso e recuperação de senha.
   - Validar agenda por perfil, Central, BI já existente e relatório.

8. Treinar usuários.
   - Entregar manuais mínimos por perfil.
   - Definir rotina diária e canal de suporte.
   - Registrar aceite ou presença.

9. Rodar QA final.
   - `.venv/bin/pytest -q`.
   - `git diff --check`.
   - `docker compose up -d --build`.
   - Smoke test das rotas críticas.
   - Conferir logs sem `Traceback`, HTTP 500 ou erro recorrente.

10. Liberar produção assistida.
   - Operar primeiros dias com acompanhamento próximo.
   - Registrar incidentes, ajustes e decisões.
   - Só depois liberar produção plena.

### P0 - Bloqueadores Antes de Produção Plena

1. Git, release e congelamento.
   - Responsável sugerido: desenvolvimento.
   - O que fazer:
     - Publicar commits locais no remoto autorizado.
     - Criar tag de homologação/release.
     - Registrar hash, data, responsável e resultado dos testes.
     - Congelar novas funcionalidades até o Go/No-Go.
   - Evidência exigida:
     - Commit/tag no Git.
     - README com hash e data da release.
     - Lista clara do que está dentro e fora do escopo.
   - Critério de pronto:
     - Equipe sabe exatamente qual versão está em homologação/produção.

2. Infraestrutura, domínio, HTTPS e firewall.
   - Responsável sugerido: infraestrutura/devops.
   - O que fazer:
     - Confirmar servidor definitivo e domínio oficial `https://sorrisodagentealagoas.com`.
     - Colocar a aplicação atrás de Nginx/Traefik/Caddy com HTTPS válido e renovação automática.
     - Bloquear acesso público direto às portas internas: web `5003`, PostgreSQL `5433`, Redis, Celery e SMTP interno.
     - Reavaliar o mapeamento `5433:5432` do PostgreSQL em `docker-compose.yml`; em produção, manter o banco sem exposição pública ou protegido por firewall/VPN.
     - Confirmar que Gunicorn fica acessível apenas pela rede interna/reverse proxy.
     - Definir política de logs de proxy e rotação.
     - Validar bloqueio de scanners comuns para `.env`, WordPress, arquivos internos e diretórios de upload.
   - Evidência exigida:
     - URL HTTPS acessível.
     - Teste de portas externas mostrando apenas `80/443` públicos e SSH restrito.
     - Registro da configuração de proxy/firewall fora do README, sem segredos.
   - Critério de pronto:
     - `/health` responde via HTTPS e o banco não fica exposto publicamente.

3. Segredos, usuários e credenciais.
   - Responsável sugerido: administração técnica.
   - O que fazer:
     - Gerar `SECRET_KEY` forte e exclusiva.
     - Trocar `POSTGRES_PASSWORD`, `ADMIN_PASSWORD` e qualquer senha temporária.
     - Rotacionar a chave API da Hostinger usada na configuração de DNS/PTR, pois foi compartilhada durante suporte.
     - Avaliar troca da senha sudo compartilhada durante suporte.
     - Garantir que `.env` real não seja versionado.
     - Confirmar que `deploy/mail/dkim/mail.private` nunca será versionado e terá backup seguro.
     - Criar usuários reais por perfil e desativar usuários demo/teste.
     - Revisar perfis: Administrador, Coordenação, Recepção, Clínicos, CME, Radiologia, Comunicação, SSA/SMS e Auditoria.
     - Padronizar login, e-mail e data de nascimento para primeiro acesso.
   - Evidência exigida:
     - Lista de usuários reais conferida sem registrar senhas.
     - Registro de data/hora da troca de credenciais.
   - Critério de pronto:
     - Nenhum usuário genérico ou senha padrão permanece ativo.

4. Base real, dados demo e cadastros iniciais.
   - Responsável sugerido: coordenação + desenvolvimento.
   - O que fazer:
     - Decidir se a produção começará vazia ou com migração.
     - Remover ou isolar os `100` pacientes demo atuais antes de qualquer atendimento real.
     - Validar municípios, especialidades, unidades de execução, profissionais e permissões.
     - Cadastrar usuários reais via pré-cadastro/aprovação ou carga administrativa.
     - Registrar competência SIGTAP de referência usada.
   - Evidência exigida:
     - Relatório simples de contagens: pacientes reais/demo, usuários ativos, unidades, especialidades e pré-cadastros pendentes.
   - Critério de pronto:
     - Nenhum dado fictício se mistura com atendimento real.

5. LGPD, arquivos sensíveis e auditoria de visualização.
   - Responsável sugerido: responsável LGPD + desenvolvimento.
   - O que fazer:
     - Mapear uploads, fotos clínicas, radiografias, PDFs, anexos endodônticos e relatórios.
     - Validar que todos os arquivos sensíveis são servidos por rotas autenticadas e com cabeçalhos `no-store`.
     - Implementar ou formalizar auditoria de visualização/download de imagens, PDFs e anexos clínicos.
     - Definir política de retenção, descarte, acesso mínimo e resposta a incidente.
     - Decidir criptografia em repouso: volume criptografado, storage externo criptografado ou camada própria.
     - Confirmar que Nginx/proxy não serve diretamente `uploads`, `pdf_temp`, `.env`, backups ou chaves DKIM.
     - Definir quem pode visualizar/downloadar documentos sensíveis por perfil.
   - Evidência exigida:
     - Matriz de arquivos sensíveis e permissões por perfil.
     - Política LGPD aprovada.
     - Teste de tentativa de acesso direto a arquivo sem login.
   - Critério de pronto:
     - Arquivos clínicos não são acessíveis fora das rotas protegidas e há trilha de auditoria adequada.

6. Backup, restore e continuidade operacional.
   - Responsável sugerido: infraestrutura/devops.
   - O que fazer:
     - Automatizar `scripts/docker_backup_postgres.sh` diariamente.
     - Incluir backup do PostgreSQL e do volume `uploads_oral`.
     - Incluir estratégia para `deploy/mail/dkim/mail.private`, sem versionar a chave.
     - Replicar backup para fora da VPS/servidor principal.
     - Rodar `scripts/docker_restore_verify.sh` em ambiente isolado.
     - Definir RPO e RTO aceitos pela gestão.
     - Documentar rotina de restauração e responsável acionável.
     - Fazer pelo menos um restore completo antes do go-live, com contagem de tabelas e amostra funcional.
   - Evidência exigida:
     - Último backup com data/hora.
     - Log de restore validado.
     - Local externo de cópia confirmado.
   - Critério de pronto:
     - Restore testado com sucesso antes da virada para produção.

7. E-mail transacional e entregabilidade.
   - Responsável sugerido: desenvolvimento + infraestrutura.
   - O que fazer:
     - Validar envio real para Gmail/Outlook de recuperação de senha, aprovação e recusa de pré-cadastro.
     - Conferir headers SPF, DKIM e DMARC nas mensagens recebidas.
     - Confirmar PTR público propagado para `mail.sorrisodagentealagoas.com`.
     - Definir caixa/responsável para mensagens de suporte, mesmo que `nao-responda` não receba respostas.
     - Definir monitoramento básico da fila: `docker exec gestaosaudeoral-mail postqueue -p`.
   - Evidência exigida:
     - Print ou registro textual dos headers recebidos, sem expor dados sensíveis.
     - Fila Postfix vazia após testes.
   - Critério de pronto:
     - E-mails críticos chegam e não ficam presos na fila.

8. Homologação operacional ponta a ponta.
   - Responsável sugerido: Recepção, Clínico responsável e Coordenação.
   - O que fazer:
     - Executar roteiro triagem -> cadastro paciente -> agenda -> atendimento -> assinatura comum -> assinatura a rogo -> procedimento -> Central -> BI/relatório.
     - Executar roteiro pré-cadastro profissional -> aprovação -> primeiro acesso -> login -> esqueci senha.
     - Validar a regra atual da Agenda: Admin/Recepção/Coordenação com agenda completa; Clínicos apenas própria agenda.
     - Validar prontuário com as abas atualmente visíveis: Paciente, Anamnese, Exames, Plano de Tratamento, Atendimento, Estomatologia, Receituário, Atestado, Visual, Materiais quando permitido e Linha do Tempo.
     - Validar o comprovante consolidado de assinatura em `/documents/signatures/<event_id>`.
     - Informar aos usuários que Endodontia e Prótese estão temporariamente ocultas do prontuário.
   - Evidência exigida:
     - Checklist assinado/aprovado por pelo menos um usuário de Recepção, um Clínico e um usuário de Coordenação.
   - Critério de pronto:
     - Nenhum fluxo crítico depende de suporte técnico para acontecer.

9. Treinamento e suporte inicial.
   - Responsável sugerido: coordenação operacional.
   - O que fazer:
     - Criar os manuais rápidos pendentes por perfil.
     - Definir rotina de abertura, fechamento e conferência diária.
     - Definir canal de suporte, responsável de plantão e SLA inicial.
     - Treinar os usuários reais no ambiente final.
     - Treinar administradores no fluxo de pré-cadastro, aprovação, recusa, primeiro acesso e troca de senha.
     - Treinar clínicos na diferença entre assinatura comum e assinatura a rogo.
   - Evidência exigida:
     - Lista de presença ou aceite por perfil.
     - Checklist de treinamento final.
   - Critério de pronto:
     - Usuários sabem operar sem depender do desenvolvedor para tarefas comuns.

10. QA técnico final e congelamento.
   - Responsável sugerido: desenvolvimento.
   - O que fazer:
     - Congelar novas funcionalidades.
     - Rodar `.venv/bin/pytest -q`.
     - Rodar `git diff --check`.
     - Rodar `docker compose up -d --build`.
     - Verificar `curl http://localhost:5003/health` ou endpoint HTTPS final.
     - Validar rotas críticas com usuários reais.
     - Conferir `docker compose ps`.
     - Conferir logs recentes de `gestaoclinica`, `celery-worker`, `celery-beat`, `postgres`, `redis` e `mail`.
   - Evidência exigida:
     - Resultado dos testes.
     - Health check.
     - Commit final de release.
   - Critério de pronto:
     - Build e testes verdes, sem mudanças não revisadas.

### P1 - Homologação Institucional e Produção Assistida

1. Assinatura digital e validade documental.
   - Decidir provedor ICP-Brasil, Gov.br ou alternativa institucional.
   - Separar assinatura técnica SHA-256 de assinatura digital formal.
   - Registrar decisão formal se a operação iniciar com assinatura transitória.

2. SIGTAP, custos e economia gerada.
   - Substituir valores demonstrativos por referências oficiais aprovadas.
   - Homologar metodologia de economia com responsável técnico.
   - Manter relatórios como estimativa enquanto não houver homologação formal.

3. e-SUS APS.
   - Confirmar versão PEC/e-SUS APS da prefeitura.
   - Obter endpoint, credenciais, CNES, INE/equipe e regras de homologação.
   - Manter como draft/simulado até transmissão real validada.

4. BI existente, Epidemiologia e território.
   - Não criar novas visões, indicadores, filtros, cards ou redesign de BI antes do Go/No-Go.
   - Usar o BI atual apenas para validar os indicadores já disponíveis e confirmar quais dados serão apresentados como estimativa.
   - Cadastrar coordenadas reais de unidades, bairros e locais de triagem quando o mapa for usado para decisão.
   - Validar com gestão quais indicadores serão oficiais.
   - Definir periodicidade de relatórios institucionais.

5. Produção assistida.
   - Rodar primeiros dias com acompanhamento próximo.
   - Criar rotina de reunião diária curta: pendências, faltas, fila, alertas, erros e suporte.
   - Registrar ajustes de texto/fluxo sem abrir novas frentes grandes durante estabilização.
   - Manter botão/atalhos de pré-cadastro fora do login, enviando o link apenas quando a operação desejar cadastrar profissional.

### P2 - Melhorias Pós-Entrada

- Portal do paciente e TCLE versionado com revogação.
- Evoluções do BI, novos indicadores, novas visões executivas e redesign.
- Notificações reais por WhatsApp/SMS e ampliação de e-mails transacionais para outros fluxos.
- Visualizador DICOM avançado com medição/anotações.
- Inventário físico periódico e relatórios avançados de perdas/reposição.
- Instrumental esterilizado, caixas cirúrgicas e ciclos.
- Retificação formal pós-assinatura com cadeia completa de versões.
- Métricas de performance e carga com volume real.

### Checklist Go/No-Go de Produção

Produção plena só deve ser liberada quando todos os itens abaixo estiverem marcados:

- [ ] Commits locais publicados no remoto autorizado.
- [ ] Tag de homologação/release criada.
- [ ] Escopo funcional congelado.
- [ ] Domínio final configurado com HTTPS.
- [ ] Banco PostgreSQL sem exposição pública indevida.
- [ ] Firewall/reverse proxy revisados.
- [ ] `.env` real revisado e fora do Git.
- [ ] Senhas iniciais trocadas.
- [ ] Chave API Hostinger rotacionada após configuração.
- [ ] Senha sudo compartilhada durante suporte avaliada/trocada.
- [ ] Chave DKIM privada protegida e com backup seguro fora do Git.
- [ ] Usuários reais cadastrados e usuários demo/teste desativados.
- [ ] Dados fictícios removidos ou isolados.
- [ ] Backup diário automatizado.
- [ ] Restore testado com sucesso.
- [ ] Cópia externa de backup confirmada.
- [ ] RPO/RTO definidos.
- [ ] Uploads clínicos protegidos contra acesso direto.
- [ ] Auditoria de visualização/download sensível definida ou implementada.
- [ ] Política LGPD de retenção, descarte e incidente aprovada.
- [ ] E-mails de primeiro acesso, recuperação, aprovação e recusa testados em caixa externa.
- [ ] SPF/DKIM/DMARC conferidos nos headers recebidos.
- [ ] PTR público confirmado para `mail.sorrisodagentealagoas.com`.
- [ ] Manuais por perfil entregues.
- [ ] Treinamento por perfil realizado.
- [ ] Fluxo ponta a ponta homologado.
- [ ] Fluxo de pré-cadastro e primeiro acesso homologado.
- [ ] Assinatura comum e assinatura a rogo homologadas.
- [ ] Regra de Agenda por perfil validada.
- [ ] Endodontia e Prótese comunicadas como módulos ocultos temporariamente.
- [ ] e-SUS marcado como draft/simulado ou homologado formalmente.
- [ ] Economia gerada marcada como estimativa ou homologada formalmente.
- [ ] `.venv/bin/pytest -q` verde.
- [ ] `git diff --check` limpo.
- [ ] Docker rebuild final executado.
- [ ] `/health` saudável.
- [ ] Commit/tag de release criado.

### Roteiro de Homologação Operacional

Executar antes do Go/No-Go:

1. Administração:
   - cadastrar/receber pré-cadastro;
   - aprovar profissional;
   - recusar outro cadastro com observação;
   - confirmar chegada dos e-mails.

2. Primeiro acesso:
   - login + data de nascimento;
   - senha definitiva;
   - confirmação de e-mail;
   - login comum;
   - esqueci minha senha.

3. Recepção:
   - criar paciente;
   - gerar e vincular senha na Triagem selecionando paciente já cadastrado e especialidade;
   - validar múltiplas senhas no mesmo paciente quando houver mais de uma demanda;
   - agendar com unidade definida;
   - confirmar/faltar/cancelar consulta.

4. Clínico:
   - abrir prontuário;
   - revisar anamnese;
   - lançar plano de tratamento;
   - registrar atendimento;
   - assinar com paciente alfabetizado;
   - assinar a rogo para paciente não alfabetizado;
   - verificar Linha do Tempo e comprovante.

5. Coordenação:
   - abrir Central de Comando;
   - revisar fila, alertas, pendências e agenda;
   - exportar resumo diário/CSV quando aplicável.

6. Gestão:
   - abrir BI;
   - abrir Epidemiologia;
   - gerar relatório institucional;
   - confirmar que economia/SIGTAP/e-SUS aparecem como estimativa/draft quando não homologados.

### Definição de Pronto para Produção Assistida

Produção assistida pode começar quando:

- P0 1 a 10 estiverem fechados ou formalmente aceitos com risco residual documentado.
- Não houver pacientes demo misturados a atendimento real.
- Banco não estiver exposto publicamente.
- Backups e restore estiverem testados.
- E-mails críticos estiverem entregando.
- Usuários reais tiverem sido treinados.
- O Go/No-Go estiver assinado pela coordenação.

Produção plena só deve ser declarada depois de pelo menos alguns dias de produção assistida sem incidente crítico e com suporte operacional definido.

### Registro de Evidências de Produção

Ao fechar cada item P0, registrar no Git:

- data da validação;
- responsável;
- comando executado;
- resultado resumido;
- link/caminho do artefato, quando houver;
- pendência remanescente, se houver.

Não registrar no Git:

- senhas;
- tokens;
- chaves privadas;
- credenciais e-SUS/SIGTAP;
- dados reais sensíveis de pacientes;
- prints com dados pessoais identificáveis sem anonimização.

## Plano de Ampliação do Módulo de Endodontia

Referência de produto:

- Documento-base: `modulo_endodontia_spec.md`.
- Referências clínicas usadas no documento: taxonomia AAE, Técnica de Bregman, critérios de Strindberg, CFO Res. 91/2009, LGPD, Lei 13.787/2018, CID-10/TUSS.

Premissas:

- O módulo já existe dentro do prontuário e deve evoluir sem quebrar os acompanhamentos atuais.
- A ampliação deve reaproveitar o que o sistema já possui: pacientes, anamnese, TCLE geral, exames/imagens, biblioteca visual, agenda, materiais/estoque, assinaturas clínicas, auditoria, Central de Comando e controles LGPD iniciais.
- A anamnese sistêmica não deve ser recriada dentro da Endodontia. A tela endodôntica deve apenas consultar, resumir e linkar a anamnese existente do prontuário, destacando riscos relevantes para o tratamento de canal.
- Criptografia robusta em repouso, assinatura digital ICP-Brasil/Gov.br, portal do paciente, envio WhatsApp real e DICOM avançado são dependências institucionais/futuras, não bloqueadores do MVP endodôntico.
- Alterações clínicas relevantes devem gerar auditoria e entrar na linha do tempo do paciente.
- O fluxo deve ser tratado como operação clínica profissional: o profissional responsável registra, revisa e valida o atendimento; o paciente assina quando aplicável. Não considerar fluxo de alunos, supervisores acadêmicos ou clínica-escola como regra do produto.
- A interface deve seguir a identidade visual atual do Sorriso da Gente: base clara, azul institucional, cartões objetivos, hierarquia visual limpa, responsividade real para desktop, tablet e celular, e telas utilizáveis em atendimento clínico com toque/caneta.

### Etapa E0 - Diagnóstico Técnico e Compatibilidade

Objetivo:

- Mapear o módulo atual e preparar evolução segura sem perda de dados.

O que fazer:

- Inventariar campos atuais das tabelas `endodontia`, `endodontia_canais` e `endodontia_followup`.
- Definir migração incremental para novos campos sem remover os campos legados.
- Definir regras de compatibilidade para casos antigos: caso sem diagnóstico estruturado fica como `diagnostico_estruturado_pendente`.
- Trocar exclusão física futura por cancelamento/soft delete com motivo, usuário e timestamp.
- Definir eventos de auditoria específicos: criação, edição técnica, alteração de diagnóstico, override de odontometria, assinatura, cancelamento, conclusão e proservação.

Critério de pronto:

- Casos antigos continuam abrindo.
- Novas estruturas podem ser criadas sem quebrar a aba atual.
- Testes cobrem compatibilidade e migração incremental.

Status em 10/06/2026:

- Implementado cancelamento lógico com `cancelado_em`, `cancelado_por`, `motivo_cancelamento` e `updated_at`.
- Listagem ativa do prontuário oculta casos cancelados.
- Central de Comando ignora pendências de assinatura de casos cancelados.
- Linha do tempo registra evento de cancelamento endodôntico.
- Aba de Endodontia mostra anamnese vinculada e UI responsiva inicial.
- Validação local: `.venv/bin/pytest -q` com `119 passed` e `git diff --check` limpo para os arquivos alterados.
- Docker reconstruído com `docker compose up -d --build`; `/health` saudável com `database=ok`; aba `/patients/view/<id>/tab/tab-endodontia` renderizada com HTTP 200; template da ficha de acompanhamento renderizado sem erro com contexto sintético.

### Etapa E1 - Ficha Endodôntica Estruturada

Objetivo:

- Transformar a ficha atual em registro clínico endodôntico estruturado, sem duplicar a anamnese do prontuário.

O que fazer:

- Exibir um resumo da anamnese existente com link direto para a aba de Anamnese do prontuário.
- Extrair da anamnese existente os riscos sistêmicos úteis para Endodontia: alergias, medicações em uso, gestação, hipertensão, diabetes, sangramento, cirurgia/hospitalização e observações clínicas relevantes.
- Criar campos estruturados apenas para a queixa endodôntica/história da dor do dente tratado: início, duração, intensidade, localização, fatores de piora, fatores de alívio e descrição livre.
- Criar exame extraoral e intraoral específico: linfadenopatia, assimetria, edema, fístula, cárie profunda, restauração inadequada, desgaste e observações.
- Criar parâmetros periodontais do dente: mobilidade, sondagem por face e classificação endodôntica/periodontal/endo-perio/inconclusiva.
- Exibir alertas de alergias relevantes usando dados já existentes da anamnese quando possível.
- Manter integração com TCLE geral e preparar gancho para TCLE endodôntico específico.
- Revisar UX/UI da aba e da ficha para uso responsivo multiplataforma, com seções progressivas, controles grandes o bastante para toque, botões claros de salvar/validar/cancelar, tabelas com rolagem horizontal apenas onde forem tecnicamente necessárias e estado vazio orientado à ação.

Critério de pronto:

- O clínico consegue registrar uma avaliação inicial completa por dente.
- Campos essenciais aparecem de forma objetiva na aba de Endodontia e na tela de acompanhamento.
- Alertas críticos do paciente ficam visíveis durante o atendimento endodôntico.
- A anamnese aparece como fonte vinculada e não como formulário repetido.
- A experiência é confortável em desktop, tablet e celular sem sobreposição de textos, botões ou tabelas.

Status em 10/06/2026:

- Implementados campos estruturados da queixa endodôntica/história da dor: início, duração, intensidade, localização, fatores de piora, fatores de alívio e descrição livre.
- Implementados campos de exame extraoral e intraoral: linfadenopatias, assimetria, edema, fístula, cárie profunda, restauração inadequada, faceta de desgaste e observações.
- Implementados parâmetros periodontais do elemento: mobilidade, sondagem por face e tipo de lesão.
- Implementado resumo automático de riscos clínicos a partir da anamnese existente, sem duplicar o formulário de anamnese.
- Criado `services/endodontia_service.py` para opções, normalização da ficha e resumo de anamnese.
- Validação local: `.venv/bin/pytest -q` com `123 passed`; `git diff --check` limpo para os arquivos alterados.
- Docker reconstruído com `docker compose up -d --build`; `/health` saudável com `database=ok`; aba `/patients/view/<id>/tab/tab-endodontia` renderizada com HTTP 200; template da ficha de acompanhamento renderizado sem erro com campos E1.

### Etapa E2 - Diagnóstico AAE, CID-10 e Bloqueios Clínicos

Objetivo:

- Substituir diagnóstico livre por diagnóstico endodôntico padronizado e acionável.

O que fazer:

- Criar enum de diagnóstico pulpar: polpa normal, pulpite reversível, pulpite irreversível sintomática, pulpite irreversível assintomática, necrose pulpar, dente previamente tratado e terapia previamente iniciada.
- Criar enum de diagnóstico apical: tecidos apicais normais, periodontite apical sintomática/assintomática, abscesso apical agudo/crônico e osteíte condensante.
- Gerar sugestão de CID-10 a partir do diagnóstico AAE.
- Marcar retratamento quando o diagnóstico for `dente_previamente_tratado`.
- Bloquear avanço para planejamento técnico avançado quando diagnóstico pulpar ou apical estiver ausente.
- Bloquear tratamento endodôntico para `polpa_normal`, salvo justificativa clínica auditada.
- Para abscesso apical agudo, sugerir abertura de receituário/atestado já existentes.

Critério de pronto:

- Todo novo caso tem diagnóstico pulpar e apical estruturados antes de avançar.
- O sistema diferencia tratamento primário, retratamento e terapia previamente iniciada.
- Central/alertas conseguem identificar urgências endodônticas.

Status em 10/06/2026:

- Implementados enums de diagnóstico pulpar e apical com opções AAE.
- Implementado CID-10 sugerido a partir do diagnóstico pulpar/apical.
- Implementada classificação de fluxo: tratamento, retratamento, continuidade terapêutica, controle conservador e avaliação/sem indicação radical.
- Implementados alertas para pulpite irreversível sintomática, periodontite apical sintomática, abscesso apical agudo/crônico, osteíte condensante, pulpite reversível e retratamento.
- Nova evolução/sessão fica bloqueada enquanto diagnóstico pulpar ou apical estiver pendente.
- Diagnóstico `polpa_normal` bloqueia avanço endodôntico sem justificativa clínica auditável.
- Validação local focada: `tests/test_phase4_endodontia.py` com `11 passed`.
- Validação completa: `.venv/bin/pytest -q` com `127 passed`; `git diff --check` limpo para os arquivos alterados.
- Docker reconstruído com `docker compose up -d --build`; `/health` saudável com `database=ok`; aba `/patients/view/<id>/tab/tab-endodontia` renderizada com HTTP 200; template da ficha com diagnóstico AAE renderizado sem erro.

### Etapa E3 - Odontometria Canal a Canal

Objetivo:

- Criar núcleo matemático de odontometria com rastreabilidade por canal.

O que fazer:

- Expandir `endodontia_canais` ou criar tabela complementar para cada canal com ponto de referência coronário, CAD, CRI, CAI, CRD, CRT sugerido e CRT final.
- Implementar cálculo de Bregman: `CRD = (CRI x CAD) / CAI`.
- Sugerir CRT conforme diagnóstico: polpa viva com margem maior; necrose/retratamento com margem menor.
- Permitir edição manual do CRT final com justificativa obrigatória.
- Auditar overrides de odontometria com valor sugerido, valor final, motivo e usuário.
- Sugerir canais típicos pelo grupo dentário e alertar variações em pré-molares e molares.

Critério de pronto:

- Cada canal tem odontometria própria.
- Cálculos são reproduzíveis em testes unitários.
- Override manual fica rastreável e visível na ficha.

Status em 10/06/2026:

- `endodontia_canais` foi expandida com ponto de referência coronário, CRI, CAI, CRD, CRT sugerido, CRT final, justificativa de override, localizador apical, modelo, leitura e confirmação eletrônica.
- Implementado cálculo de Bregman: `CRD = (CRI x CAD) / CAI`, com validação de CAI maior que zero.
- Implementada sugestão de CRT por diagnóstico pulpar: margem menor para necrose/retratamento/terapia previamente iniciada e margem maior para polpa viva.
- Quando o CRT final difere do CRT sugerido, a ficha exige justificativa e registra auditoria `endodontia_odontometry_override` com canal, CRD, CRT sugerido, CRT final, motivo e usuário.
- A tabela técnica da ficha foi ampliada de forma responsiva, com rolagem horizontal em telas menores e campos compactos para cada canal.
- A ficha exibe sugestão anatômica inicial por elemento em padrão FDI, incluindo alerta de MV2 em molares superiores, variação distal em molares inferiores, variações de pré-molares e possibilidade de canal lingual em incisivos inferiores.
- Validação local focada: `tests/test_phase4_endodontia.py` com `19 passed`.
- Validação completa: `.venv/bin/pytest -q` com `135 passed`; `git diff --check` limpo para os arquivos alterados.
- Docker reconstruído com `docker compose up -d --build`; `/health` saudável com `database=ok`; aba `/patients/view/<id>/tab/tab-endodontia` renderizada com HTTP 200; template da ficha com odontometria canal a canal renderizado sem erro.

### Etapa E4 - Sessões Endodônticas e Fluxo de Status

Objetivo:

- Evoluir follow-up simples para gestão multi-sessão.

O que fazer:

- Numerar sessões automaticamente.
- Registrar etapa realizada: abertura, neutralização séptica, odontometria, preparo parcial/completo, medicação intracanal, troca de medicação, obturação e proservação.
- Registrar status da sessão: em andamento, realizada, cancelada ou aguardando retorno.
- Registrar total de sessões planejadas, próxima sessão prevista e janela de retorno.
- Atualizar status do tratamento: aguardando início, em andamento, aguardando retorno, obturado aguardando restauração, concluído, abandono ou retratamento necessário.
- Integrar próxima sessão prevista com Agenda quando a operação decidir agendar.
- Manter assinatura do paciente e validação do responsável clínico.

Critério de pronto:

- A evolução deixa de ser apenas texto e passa a alimentar status, alertas e fila.
- Sessão vencida sem retorno aparece para recepção/coordenação.
- Sessões assinadas ficam travadas para edição direta, com fluxo de retificação futuro.

Status em 12/06/2026:

- `endodontia_followup` foi expandida com número da sessão, etapa realizada, status da sessão, próxima sessão prevista, janela de retorno e observação clínica.
- `endodontia` passou a guardar status do tratamento, total de sessões planejadas, próxima sessão prevista e janela de retorno.
- A ficha endodôntica registra sessões estruturadas em vez de evolução solta, mantendo compatibilidade visual para evoluções legadas.
- O número da próxima sessão é calculado automaticamente a partir do maior número já registrado.
- O status do tratamento é derivado da etapa/status da sessão, com opção de override para abandono ou retratamento necessário.
- Assinatura do paciente e validação do profissional responsável continuam no fluxo existente de sessão.
- A aba do prontuário exibe status endodôntico e próxima sessão prevista por elemento.
- A Central de Comando passou a contar retornos endodônticos vencidos como pendência clínica e alerta operacional.
- Validação local focada: `tests/test_phase4_endodontia.py` com `23 passed`.
- Validação local focada: `tests/test_phase2_command_center.py` com `27 passed`.
- Validação completa: `.venv/bin/pytest -q` com `140 passed`.

### Etapa E5 - Protocolo Biomecânico, Irrigação e Medicação Intracanal

Objetivo:

- Registrar a execução técnica com segurança clínica e rastreabilidade.

O que fazer:

- Registrar LAI, técnica de instrumentação, sistema rotatório/reciprocante, liga do instrumento e observações.
- Integrar instrumentos e materiais com estoque quando o item estiver cadastrado.
- Registrar solução irrigadora, EDTA, tempo, agitação, volume e observações.
- Bloquear hipoclorito quando houver alergia registrada a hipoclorito.
- Bloquear material eugenólico quando houver alergia a eugenol.
- Exibir alerta persistente para alergia a látex.
- Registrar medicação intracanal, veículo, quantidade aproximada e selamento provisório.
- Criar alerta de retorno quando houver medicação intracanal com janela vencida.

Critério de pronto:

- O clínico registra protocolo técnico sem depender de texto solto.
- Alertas críticos impedem escolhas incompatíveis com alergias.
- Uso de materiais pode ser vinculado ao controle de estoque sem bloquear atendimento quando estoque estiver desativado.

Status em 12/06/2026:

- `endodontia_followup` foi expandida com campos de protocolo por sessão: LAI, técnica de instrumentação, sistema, liga do instrumento, observações técnicas, solução irrigadora, EDTA, tempo, agitação, volume, observações de irrigação, medicação intracanal, veículo, quantidade e selamento provisório.
- A ficha de sessão passou a registrar protocolo biomecânico, irrigação e medicação no mesmo lançamento clínico assinado/validado.
- Sessões já registradas continuam compatíveis; os campos E5 aparecem apenas quando preenchidos.
- A anamnese vinculada bloqueia seleção de hipoclorito quando houver alergia compatível com hipoclorito/cloro.
- A anamnese vinculada bloqueia selamento/material eugenólico quando houver alergia a eugenol.
- A ficha destaca alerta persistente quando houver alergia a látex.
- O retorno previsto e a janela da E4 continuam sendo a base para controlar medicação intracanal com retorno vencido na Central.
- Validação local focada: `tests/test_phase4_endodontia.py` com `28 passed`.
- Validação completa: `.venv/bin/pytest -q` com `145 passed`.

### Etapa E6 - Obturação Final e Encaminhamento Restaurador

Objetivo:

- Fechar a fase endodôntica com controle de qualidade e continuidade restauradora.

O que fazer:

- Registrar cone principal: material, calibre ISO, conicidade, prova de cone, tug-back e CRT confirmado.
- Registrar cimento obturador: classe, lote e validade, reaproveitando estoque quando possível.
- Registrar técnica de obturação.
- Registrar controle de qualidade radiográfico: radiografia final aprovada, gaps, voids e observações.
- Ao concluir obturação, mover status para `obturado_aguardando_restauracao`.
- Gerar alerta para clínico/recepção quando não houver restauração definitiva agendada ou registrada.
- Permitir registrar restauração coronária definitiva e selamento adequado.

Critério de pronto:

- Tratamento obturado não some da gestão antes da restauração definitiva.
- Central de Comando exibe pendência restauradora.
- O prontuário mostra fechamento técnico e pendência restauradora com clareza.

Estado implementado em 14/06/2026:

- `endodontia_followup` registra obturação final, controle radiográfico e restauração definitiva.
- `endodontia` mantém os marcadores consolidados de restauração definitiva e selamento coronário adequado.
- A ficha exibe resumo de obturação/restauração por sessão e alerta local quando o caso está obturado aguardando restauração.
- A Central de Comando exibe pendência de Endodontia sem restauração definitiva.

### Etapa E7 - Imagens Endodônticas e Biblioteca Visual

Objetivo:

- Organizar imagens endodônticas por etapa clínica sem duplicar o módulo visual.

O que fazer:

- Adicionar categorias endodônticas à biblioteca visual: periapical inicial, odontometria, prova de cone, final de qualidade, proservação 6m/1a/2a/4a, CBCT e outra.
- Permitir vincular imagem a dente, canal e sessão.
- Registrar metadados: data de captura, equipamento, anotação clínica e operador.
- Usar as proteções de arquivo sensível já existentes.
- Planejar DICOM avançado como fase futura: zoom, janela/nível, negativo, pseudocor, medição e anotações salvas.

Critério de pronto:

- Imagens de Endodontia ficam localizáveis por caso e etapa.
- Radiografia final pode ser usada no controle de qualidade.
- Visualização respeita permissões e cabeçalhos LGPD já existentes.

Estado implementado em 14/06/2026:

- Criada tabela `endodontia_imagens` com vínculo a paciente, caso, sessão, canal, categoria, legenda, anotação clínica, equipamento, data de captura, operador e arquivo protegido.
- A ficha de Endodontia permite enviar imagens JPG/PNG/WEBP/TIFF/DICOM com etapa visual, sessão e canal.
- A rota protegida `/endodontia/image/<image_id>` usa os cabeçalhos de arquivo sensível já existentes.
- A Biblioteca Visual passou a listar e editar metadados da origem `Endodontia`.
- DICOM avançado segue como refinamento futuro de visualizador, medição e anotações salvas.

### Etapa E8 - Proservação e Critérios de Strindberg

Objetivo:

- Acompanhar resultado longitudinal do tratamento.

O que fazer:

- Ao concluir obturação/restauração, criar retornos previstos de 6, 12 e 24 meses.
- Criar retorno de 48 meses quando houver lesão periapical extensa inicial.
- Registrar critérios clínicos: função mastigatória, ausência de dor à percussão/palpação, ausência de edema e ausência de fístula.
- Registrar critérios radiográficos: espaço periodontal, lâmina dura, ausência ou redução de lesão radiolúcida.
- Classificar resultado como sucesso, dúvida ou insucesso.
- Para dúvida, sugerir novo retorno em 6 meses.
- Para insucesso, sugerir retratamento/apicectomia como conduta a avaliar.

Critério de pronto:

- Proservações vencidas aparecem na Central/agenda operacional.
- Resultado longitudinal fica registrado no prontuário.
- Indicadores futuros podem medir sucesso clínico endodôntico.

Estado implementado em 14/06/2026:

- Criada tabela `endodontia_proservacao` com retornos planejados, status, data prevista/realizada, critérios clínicos, critérios radiográficos, restauração coronária e resultado Strindberg.
- Ao registrar sessão de obturação realizada, o sistema cria proservações de 6, 12 e 24 meses; casos com lesão periapical extensa também recebem retorno de 48 meses.
- A ficha endodôntica permite avaliar cada retorno com função mastigatória, dor à percussão/palpação, edema, fístula, espaço periodontal, lâmina dura, lesão radiolúcida e redução de lesão preexistente.
- O resultado é classificado como sucesso, dúvida ou insucesso; insucesso atualiza o caso para `retratamento_necessario`.
- Proservações planejadas vencidas entram nas pendências clínicas e alertas operacionais da Central de Comando.

### Etapa E9 - Orçamento, TUSS/SIGTAP e Indicadores

Objetivo:

- Preparar a camada financeira/gerencial sem confundir custo operacional com faturamento oficial.

O que fazer:

- Calcular complexidade por grupo dentário e número de canais.
- Diferenciar tratamento de retratamento.
- Sugerir CID-10 e TUSS quando houver catálogo/local de referência.
- Integrar custos estimados com materiais, tempo clínico e referências já existentes.
- Manter SIGTAP/e-SUS separado: só vincular procedimento oficial quando aplicável e homologado.
- Criar indicadores para BI/Central: casos em andamento, urgências, retratamentos, obturados sem restauração, retornos vencidos, sucesso/dúvida/insucesso.

Critério de pronto:

- Gestão consegue enxergar carga endodôntica e gargalos.
- Orçamento/custo é rastreável e não substitui faturamento oficial sem homologação.
- BI não mistura estimativa com dado homologado.

Estado implementado em 14/06/2026:

- Criada tabela `endodontia_orcamento_items` para orçamento gerencial por canal, com vínculo a paciente, caso, dente, canal, procedimento, TUSS, SIGTAP, CID-10, valores de referência, complexidade e status.
- O serviço classifica complexidade por grupo dentário e número de canais, diferencia tratamento primário de retratamento e aplica multiplicadores clínicos para estimativa gerencial.
- A geração de orçamento usa referências ativas de `procedure_cost_references` quando disponíveis, calcula referência pública/privada e economia estimada, sem tratar o valor como faturamento homologado.
- Diagnóstico `polpa_normal` bloqueia geração de orçamento endodôntico, preservando a regra clínica definida na especificação.
- A ficha exibe resumo financeiro, itens por canal, TUSS/SIGTAP de referência, CID-10 sugerido e indicadores de complexidade.

### Etapa E10 - QA, Documentação e Aceite Clínico

Objetivo:

- Entregar o módulo ampliado com segurança operacional.

O que fazer:

- Criar testes unitários para enums, cálculo de Bregman, CRT sugerido, bloqueios por alergia, status e alertas.
- Criar testes de serviço para sessões, proservação, soft delete e auditoria.
- Validar rotas principais em Docker.
- Atualizar `docs/base_documentacao_manuais_usuarios.md`.
- Criar manual rápido do fluxo endodôntico para Clínicos, Recepção e Coordenação.
- Rodar caso ponta a ponta: diagnóstico -> TCLE -> odontometria -> preparo -> medicação -> obturação -> restauração -> proservação.

Critério de pronto:

- Testes automatizados verdes.
- `git diff --check` limpo.
- Docker saudável e `/health` OK.
- Fluxo validado por pelo menos um clínico responsável.
- README e manuais atualizados.

Estado implementado em 14/06/2026:

- Adicionado teste automatizado E10 do fluxo clínico em nível de serviço: diagnóstico estruturado, odontometria por Bregman, preparo, medicação, obturação, proservação, Strindberg e orçamento por canal.
- Adicionado teste de mapa de rotas críticas do blueprint de Endodontia: criação de caso, ficha, salvar detalhes, sessão, upload/visualização de imagem, proservação e orçamento.
- Criado manual rápido `docs/manual_rapido_endodontia_e10_2026-06-14.md` para Clínicos, Recepção e Coordenação.
- `docs/base_documentacao_manuais_usuarios.md` atualizado com referência ao manual rápido e ao fluxo E8/E9/E10.
- Aceite clínico-operacional preparado como checklist; validação formal por clínico responsável segue como etapa humana/institucional antes de implantação oficial.

Backlog fora do MVP endodôntico:

- Assinatura digital ICP-Brasil/Gov.br integrada.
- Portal do paciente para aceite de TCLE.
- WhatsApp/API real de comunicação.
- Visualizador DICOM completo.
- Criptografia robusta em repouso para todos os anexos.
- Retificação formal pós-assinatura com cadeia de versões completa.

## Plano de Finalização do Desenvolvimento

Este plano é a rota de referência para transformar a versão funcional em versão homologável/implantável. Ele não deve ser executado automaticamente antes das modificações solicitadas pelo Diego nesta nova rodada.

### Etapa 1 - Manuais Rápidos e Treinamento por Perfil

Objetivo:

- Criar material operacional para a equipe usar o sistema com segurança.

O que fazer:

- Criar manual de Administração.
- Criar manual de Recepção e Triagem.
- Criar manual de Agenda e Central de Comando.
- Criar manual Clínico/Prontuário.
- Criar manual de Estoque/CME.
- Criar manual de BI, Relatórios, Epidemiologia e e-SUS.
- Criar checklist de treinamento por perfil.

Como fazer:

1. Usar `docs/base_documentacao_manuais_usuarios.md` como base.
2. Para cada perfil, listar:
   - objetivo do perfil;
   - rotas/telas usadas;
   - rotina diária;
   - o que preencher;
   - o que não preencher;
   - alertas que o perfil precisa resolver;
   - erros comuns;
   - checklist de fim do dia.
3. Transformar cada manual em documento curto, direto e testável.
4. Validar cada manual navegando no sistema em Docker.

Informações a coletar com desenvolvedor/gestão:

- Quem são os usuários reais de cada perfil.
- Quais perfis serão usados na implantação inicial.
- Nomes finais das unidades de execução.
- Fluxo real da triagem de campo.
- Quem decide o destino operacional da população triada.
- Quem pode alterar agenda e unidade de execução.
- Quais relatórios serão usados em reunião diária, semanal e mensal.
- Qual linguagem a equipe prefere nos manuais.

Critério de pronto:

- Todos os perfis têm manual.
- Cada manual foi testado contra a tela real.
- O responsável operacional aprovou o fluxo.

VOLTE E VERIFIQUE:

- Triagem: campo, senha e demanda. Não define unidade.
- Agenda: define unidade e destino.
- Central: coordenação acompanha fila, destino, metas e pendências.

### Etapa 2 - Homologação do Fluxo Operacional Ponta a Ponta

Objetivo:

- Confirmar que o fluxo real do paciente funciona sem atalhos perigosos.

O que fazer:

- Testar fluxo completo:
  1. Cadastrar paciente em `Novo Paciente`.
  2. Criar ação de triagem.
  3. Gerar senha selecionando o paciente já cadastrado e a especialidade.
  4. Gerar segunda senha para o mesmo paciente, se houver múltipla demanda, e confirmar exibição agregada no prontuário.
  5. Agendar consulta e definir unidade.
  6. Realizar atendimento.
  7. Registrar evolução.
  8. Assinar documentos necessários.
  9. Lançar procedimento SIGTAP.
  10. Registrar exame ou imagem, se houver.
  11. Registrar material, se houver.
  12. Conferir Central de Comando.
  13. Conferir BI/Epidemiologia.
  14. Gerar resumo diário.

Como fazer:

- Criar uma carga controlada de teste ou usar pacientes demo.
- Executar o roteiro em Docker.
- Registrar prints ou anotações de cada etapa.
- Anotar divergências de texto, fluxo, permissão ou regra.
- Corrigir apenas o que bloquear ou confundir operação.

Informações a coletar com desenvolvedor/gestão:

- Quais especialidades entram no piloto.
- Volume esperado de triagem por município.
- Quantidade de cadeiras/equipes por unidade.
- Horários de funcionamento.
- Regras de remarcação, falta e cancelamento.
- Quem pode confirmar presença.
- Quem pode marcar `Faltou`.
- Quem pode concluir atendimento.
- Quem pode corrigir erro de senha/paciente.

Critério de pronto:

- Fluxo validado por pelo menos um usuário de Recepção, um Clínico e um usuário de Coordenação.
- Nenhuma tela crítica depende de dado fictício.
- Central de Comando reflete corretamente agenda, fila e pendências.

VOLTE E VERIFIQUE:

- Senha aparece como aguardando agendamento até consulta existir.
- Depois da consulta, a senha mostra destino.
- Unidade da Central bate com unidade da Agenda.

### Etapa 3 - Hardening de Produção, LGPD e Continuidade

Objetivo:

- Reduzir risco jurídico, operacional e técnico antes da entrada em produção.

O que fazer:

- Criptografar ou proteger armazenamento de uploads clínicos.
- Formalizar política de retenção/descarte.
- Bloquear acesso direto a arquivos sensíveis.
- Auditar visualização de documentos/imagens sensíveis.
- Automatizar backup diário.
- Replicar backup fora do servidor.
- Testar restauração.
- Definir RPO/RTO.
- Decidir assinatura digital homologada ou alternativa transitória.

Como fazer:

1. Mapear todos os tipos de arquivo sensível.
2. Verificar todas as rotas que servem imagens/PDFs/uploads.
3. Criar matriz de permissão por perfil para upload, edição, exclusão e visualização.
4. Implantar logs de visualização sensível.
5. Automatizar script de backup.
6. Restaurar backup em ambiente isolado e registrar evidência.
7. Documentar procedimento de incidente e restauração.

Informações a coletar com desenvolvedor/gestão:

- Onde ficará o servidor definitivo.
- Quem administra infraestrutura.
- Política institucional de backup.
- Storage disponível: local, S3, volume criptografado ou outro.
- Exigência formal de LGPD.
- Prazo legal/institucional de retenção.
- Provedor de assinatura desejado: ICP-Brasil, Gov.br, outro.
- Quem será encarregado/responsável LGPD.

Critério de pronto:

- Backup diário funcionando.
- Restore testado.
- Arquivos sensíveis sem acesso direto indevido.
- Auditoria de visualização sensível ativa.
- Política de retenção documentada.

VOLTE E VERIFIQUE:

- Fotos clínicas, radiografias e PDFs são os pontos de maior risco.
- Assinatura técnica SHA-256 não substitui assinatura digital formal.

### Etapa 4 - Fechamento Financeiro e Logístico

Objetivo:

- Decidir o que precisa estar pronto para controle operacional real de custos e materiais.

O que fazer:

- Confirmar se o estoque será usado no piloto.
- Confirmar se a segunda unidade será usada no piloto.
- Definir relatórios mínimos de consumo e perdas.
- Definir se produtividade por unidade será necessária agora.
- Definir se inventário físico periódico entra na versão final.

Como fazer:

1. Revisar `/admin/inventory`.
2. Revisar aba `Materiais` no prontuário.
3. Criar materiais/lotes reais mínimos para piloto.
4. Simular consumo clínico.
5. Simular ajuste/perda.
6. Conferir alertas na Central.
7. Verificar impacto no custo do paciente.

Informações a coletar com desenvolvedor/gestão:

- Lista real de materiais controlados.
- Categorias oficiais de materiais.
- Unidades de medida.
- Estoque mínimo por item.
- Centros de custo.
- Quem recebe lote.
- Quem autoriza ajuste/perda.
- Como será feito inventário físico.
- Se custos por unidade/equipe serão cobrados em relatório.

Critério de pronto:

- Estoque mínimo do piloto cadastrado.
- Usuários sabem registrar lote, uso e ajuste.
- Relatório mínimo de consumo/perdas definido.

VOLTE E VERIFIQUE:

- Estoque não bloqueia atendimento clínico.
- Custo por material é operacional, não faturamento oficial.

### Etapa 5 - Homologação da Fase 3

Objetivo:

- Separar o que já está implementado do que depende de validação institucional externa.

O que fazer:

- Homologar metodologia de economia gerada.
- Substituir referências demonstrativas por valores oficiais aprovados.
- Definir responsável técnico pela metodologia.
- Validar versão PEC/e-SUS APS da prefeitura.
- Confirmar compatibilidade LEDI.
- Obter endpoint, autenticação, CNES, INE e regras de homologação.
- Validar campos obrigatórios finais.
- Refinar coordenadas territoriais se o mapa for ferramenta de decisão.

Como fazer:

1. Gerar relatório BI/PDF com nota metodológica.
2. Revisar `/admin/finance/cost-references`.
3. Marcar referências homologadas apenas com aprovação formal.
4. Gerar lote draft e-SUS.
5. Rodar validação interna e pré-envio simulado.
6. Apresentar checklist de homologação e-SUS à prefeitura.
7. Registrar pendências por campo obrigatório.
8. Atualizar documentação técnica.

Informações a coletar com desenvolvedor/gestão:

- Competência SIGTAP de referência.
- Fonte oficial dos valores privados/comparativos.
- Quem aprova metodologia de economia.
- Endpoint e-SUS/PEC.
- Ambiente de homologação ou produção.
- Tipo de autenticação.
- CNES/INE oficiais.
- Regras da prefeitura para envio.
- Responsável municipal pela validação.
- Coordenadas reais de unidades, bairros e locais de triagem.

Critério de pronto:

- Economia gerada com metodologia aprovada ou marcada claramente como estimativa.
- Referências oficiais cadastradas.
- Lote e-SUS sem pendências críticas.
- Transmissão real implementada somente se a prefeitura fornecer ambiente e credenciais.

VOLTE E VERIFIQUE:

- Não vender economia estimada como economia formal antes de homologação.
- Não marcar e-SUS como integrado enquanto não houver transmissão real validada.

### Etapa 6 - QA Final, Congelamento e Implantação Assistida

Objetivo:

- Fechar escopo da versão e preparar operação.

O que fazer:

- Congelar novas funcionalidades.
- Rodar testes automatizados.
- Validar rotas críticas em Docker.
- Criar backup antes da implantação.
- Conferir perfis reais.
- Conferir dados mínimos reais.
- Executar treinamento.
- Fazer operação assistida nos primeiros dias.

Como fazer:

1. Rodar:

```bash
.venv/bin/pytest -q
git diff --check
docker compose up -d --build
curl http://localhost:5003/health
```

2. Validar rotas:
   - `/dashboard`
   - `/triagem/`
   - `/triagem/senhas`
   - `/agenda/`
   - `/command-center`
   - `/patients`
   - `/epidemiologia`
   - `/bi`
   - `/reports/institutional`
   - `/admin/inventory`
   - `/admin/execution-units`
   - `/admin/finance/cost-references`
   - `/admin/integrations/esus`

3. Criar checklist de aceite por perfil.
4. Registrar evidências da homologação.
5. Atualizar README e manuais.

Informações a coletar com desenvolvedor/gestão:

- Data de entrada em operação.
- Usuários e perfis finais.
- Senha/admin inicial a ser trocada.
- Domínio e HTTPS.
- Servidor definitivo.
- Rotina de suporte.
- Quem aprova aceite final.
- Canais para chamados.

Critério de pronto:

- Testes verdes.
- Docker saudável.
- Backup e restore validados.
- Manuais entregues.
- Usuários treinados.
- Aceite formal registrado.

VOLTE E VERIFIQUE:

- Não iniciar produção sem plano de backup e restauração testado.
- Não iniciar produção sem responsáveis por suporte, LGPD e gestão dos usuários.

## Backlog Priorizado

Prioridade atual - modificações solicitadas:

- Receber e implementar as modificações pontuais solicitadas pelo Diego.
- Validar cada mudança com teste automatizado ou checagem operacional compatível com o risco.
- Atualizar README e manuais quando a mudança alterar fluxo, tela, permissão, relatório, métrica ou rotina de uso.
- Manter Endodontia, Prótese, Portal do Paciente, evoluções de BI e UX avançada da Central fora do foco até o Go/No-Go de produção.

Prioridade 0 - antes de produção plena:

- Manuais rápidos por perfil.
- QA ponta a ponta do fluxo triagem -> agenda -> atendimento -> gestão.
- Backup diário automatizado.
- Teste de restauração.
- Proteção final de uploads clínicos.
- Auditoria de visualização sensível.
- Política de retenção/descarte.
- Checklist de aceite por perfil.

Prioridade 1 - produção/homologação institucional:

- Assinatura digital homologada.
- Homologação da economia gerada.
- Referências oficiais de custo.
- e-SUS transmissão real, se a prefeitura fornecer ambiente.
- Coordenadas finas de bairros, locais e unidades.
- Produtividade/custos por unidade, se a segunda unidade entrar em operação.

Prioridade 2 - refinamentos avançados:

- Mapa cartográfico oficial com polígonos/tiles.
- Inventário físico periódico.
- Relatórios avançados de perdas, consumo médio e reposição.
- Instrumental esterilizado, caixas cirúrgicas e ciclos.
- Intercorrências e alta clínica avançada.
- Refinamentos do módulo de Endodontia.
- Melhorias de UX da Endodontia.
- Melhorias de UX da Central de Comando.
- Portal do Paciente.
- Evoluções de BI, novos indicadores e novas visões executivas.

## Checklist de Aceite Final

- [ ] Manuais por perfil revisados.
- [ ] Usuários reais cadastrados com perfis corretos.
- [ ] Unidades de execução cadastradas e aprovadas.
- [ ] Fluxo de triagem validado em campo simulado.
- [ ] Fluxo de agenda validado com unidade definida.
- [ ] Prontuário validado por clínico.
- [ ] Central validada por coordenação.
- [ ] BI e relatórios validados pela gestão.
- [ ] Backup automático configurado.
- [ ] Restore testado.
- [ ] Uploads sensíveis protegidos.
- [ ] Auditoria de visualização sensível definida.
- [ ] Política LGPD registrada.
- [ ] e-SUS homologado ou marcado explicitamente como draft.
- [ ] Economia gerada homologada ou marcada como estimativa.
- [ ] Docker rebuild final executado.
- [ ] `/health` saudável.
- [ ] `.venv/bin/pytest -q` verde.
- [ ] `git diff --check` limpo.

## Documentação e Manuais

Base de manuais:

- `docs/base_documentacao_manuais_usuarios.md`
- `docs/manual_rapido_endodontia_e10_2026-06-14.md` (referência histórica/operacional; Endodontia não é prioridade atual)
- `docs/qa_endodontia_e10_2026-06-14.md` (referência histórica/operacional; Endodontia não é prioridade atual)

Manuais a criar:

- `docs/manual_admin.md`
- `docs/manual_recepcao_triagem.md`
- `docs/manual_agenda_central.md`
- `docs/manual_clinico_prontuario.md`
- `docs/manual_estoque_cme.md`
- `docs/manual_bi_relatorios_esus.md`
- `docs/checklist_implantacao.md`

VOLTE E VERIFIQUE:

- Cada manual deve ter rotina diária, campos obrigatórios, erros comuns, alertas que o perfil resolve e checklist de fechamento.

## Ponto de Retomada

Checkpoint de sessão em 16/06/2026:

- Aplicação validada em Docker com PostgreSQL 16, Redis, Celery worker, Celery Beat e serviço `mail` em execução.
- `/health` respondeu `status=healthy` e `database=ok`.
- Testes focados de autenticação, primeiro acesso, pré-cadastro e e-mail executados com `11 passed`.
- Há muitas alterações locais não commitadas; tratar como trabalho existente e não reverter sem pedido explícito.
- O README foi atualizado para refletir o fluxo de pré-cadastro público, aprovação/recusa por e-mail, primeiro acesso, recuperação de senha e infraestrutura Postfix/OpenDKIM.
- Modificações desta rodada implementadas: assinatura a rogo, pacote probatório ampliado, pré-cadastro profissional, primeiro acesso, recuperação de senha, e-mail transacional e reorganização UX/UI das telas de cadastro/pré-cadastros.
- Endodontia E0-E10 permanece implementada como MVP clínico-operacional, mas está fora da prioridade atual.
- Melhorias de UX da Endodontia, Prótese, Portal do Paciente, evoluções de BI e Central de Comando ficam estacionadas até depois do Go/No-Go de produção.
- Antes de produção plena, continuam obrigatórios os bloqueadores P0: infraestrutura segura, segredos, LGPD/arquivos sensíveis, backup/restore, limpeza de dados demo, homologação ponta a ponta, treinamento e QA final.

Próxima continuidade recomendada:

- Seguir a próxima solicitação funcional/operacional do Diego.
- Fazer alteração pequena, validável e bem documentada.
- Rodar validação proporcional ao risco da mudança.
- Atualizar README e manuais quando houver impacto em fluxo ou treinamento.

## Histórico Consolidado

- 29/05/2026: Fase 0 entregue e validada.
- 30/05/2026: Fase 1 revisada; Fase 2 inicial validada; Fase 3 iniciada com Epidemiologia, BI e Relatórios v1.
- 01/06/2026: SIGTAP/e-SUS draft, checklist de homologação, dados demo, pré-envio simulado e relatório de homologação.
- 02/06/2026: Mapa georreferenciado, BI Governamental v2, custos SIGTAP e PDF governamental do BI.
- 03/06/2026: Perfis simplificados, limpeza da base fictícia, módulo visual avançado, estoque/materiais e mapa visual de Alagoas.
- 05/06/2026: Fila Inteligente SUS v2, alertas clínicos, filtros, métricas, resumo diário, metas automáticas e unidades de execução.
- 06/06/2026: Regra refinada de triagem/unidade: triagem é campo e senha; unidade é definida no agendamento. README reorganizado para versão 2.0.
- 10/06/2026: Registrado plano de ampliação do módulo de Endodontia com base em `modulo_endodontia_spec.md`, priorizando diagnóstico AAE, odontometria, sessões, obturação, proservação e integração com recursos já existentes. Etapa E0 iniciada com anamnese vinculada, cancelamento lógico auditado, casos cancelados fora da lista ativa/Central e revisão UX/UI inicial. Etapa E1 iniciada com queixa endodôntica estruturada, exame extra/intraoral, periodonto do elemento e resumo de riscos da anamnese existente. Etapa E2 iniciada com diagnóstico AAE, CID-10 sugerido, tipo de fluxo e bloqueio de avanço sem diagnóstico estruturado. Etapa E3 iniciada com odontometria canal a canal, cálculo de Bregman, CRT sugerido/final, auditoria de override e sugestão anatômica por elemento dentário.
- 12/06/2026: Etapa E4 implementada com sessões endodônticas numeradas, etapa/status da sessão, status do tratamento, planejamento de sessões, retorno previsto, alerta de retorno vencido na Central de Comando e atualização da aba de Endodontia no prontuário.
- 12/06/2026: Etapa E5 implementada com protocolo biomecânico por sessão, campos de instrumentação, irrigação/EDTA, medicação intracanal, selamento provisório, bloqueio por alergia a hipoclorito/eugenol e alerta de látex baseado na anamnese vinculada.
- 14/06/2026: Etapas E6 e E7 implementadas com obturação final, controle radiográfico, pendência restauradora na Central, registro de restauração definitiva, upload protegido de imagens endodônticas e integração da origem Endodontia à Biblioteca Visual.
- 14/06/2026: Etapas E8 e E9 implementadas com proservações automáticas, critérios clínico-radiográficos de Strindberg, alerta de proservação vencida na Central, orçamento gerencial por canal, TUSS/SIGTAP de referência e bloqueio de orçamento para `polpa_normal`.
- 14/06/2026: Etapa E10 implementada com teste automatizado de fluxo clínico ponta a ponta em nível de serviço, teste de mapa de rotas críticas, manual rápido para Clínicos/Recepção/Coordenação e checklist de aceite clínico-operacional.
- 15/06/2026: Corrigido acesso à ficha `Acompanhar` da Endodontia quando o caso ainda não possui orçamento gerado; resumo financeiro vazio agora inicia com totais `Decimal('0.00')` e há teste automatizado específico para orçamento vazio.
- 15/06/2026: Reorganizada a seção `Sessões endodônticas e fluxo de status` da ficha de acompanhamento, substituindo a tabela comprimida por histórico em cartões e formulário de nova sessão em grid responsivo.
- 15/06/2026: Endodontia e Prótese foram temporariamente ocultas da navegação do prontuário do paciente; Estomatologia foi reposicionada para aparecer logo após Atendimento. Usuários devem ser avisados de que os módulos ocultos continuam existentes no sistema.
- 16/06/2026: Implementada assinatura a rogo para TCLE e confirmação do atendimento quando o paciente for não alfabetizado, com autenticação do CD, duas testemunhas, evento probatório, SHA-256, IP, user-agent, CPF do paciente, registro em `digital_signatures` e auditoria.
- 16/06/2026: Padronizado pacote probatório de assinatura para Anamnese, Prótese, Pagamentos e Endodontia; Linha do Tempo passou a exibir eventos de assinatura de forma legível; criada rota de comprovante consolidado `/documents/signatures/<event_id>`; modal de confirmação do atendimento passou a exibir nome e CPF do paciente.
- 16/06/2026: Implementado pré-cadastro profissional público em `/cadastro/`, tela administrativa de análise, aprovação com criação de usuário em primeiro acesso e recusa com observação administrativa.
- 16/06/2026: Implementados primeiro acesso com login + data de nascimento, definição de senha definitiva, confirmação de e-mail e recuperação de senha com token temporário por e-mail.
- 16/06/2026: Configurado e-mail transacional com Docker `gestaosaudeoral-mail`, Postfix send-only, OpenDKIM, SPF, DKIM, DMARC e PTR/rDNS na Hostinger; documentação adicionada em `docs/auth_primeiro_acesso_postfix_2026-06-16.md` e `docs/email_producao_sorrisodagente_2026-06-16.md`.
- 16/06/2026: Melhorada UX/UI do cadastro público e da tela administrativa de pré-cadastros; a análise administrativa passou de tabela para cards por solicitação, com ações separadas para aprovar ou recusar.
- 17/06/2026: Congelado o escopo de Endodontia, Prótese, Portal do Paciente e evoluções de BI até o Go/No-Go de produção. O BI existente permanece disponível para validação gerencial e relatórios já implementados, sem novas visões, indicadores, redesign ou ampliações antes da produção assistida.
- 17/06/2026: Ajustado fluxo operacional para `Novo Paciente -> Triagem -> Pacientes / Prontuários -> Agenda`; o cadastro não solicita senha, a Triagem gera senha vinculando paciente já cadastrado e um paciente pode ter múltiplas senhas/demandas.
- 17/06/2026: Publicada a branch `main` e a tag `homologacao-2026-06-17` no GitHub usando o remoto SSH `git@github.com-gentillidiego:gentillidiego/GestaoClinica-SorrisodaGente.git`.

## Última Validação Técnica Registrada

Resultado mais recente em 17/06/2026:

- Release candidata de homologação: `homologacao-2026-06-17`.
- Commit da versão candidata: `d39dfce406b5c669dbb8d0e78c4dd3c009d46dff`.
- Escopo congelado: Endodontia, Prótese, Portal do Paciente e evoluções de BI seguem fora da versão de homologação.
- Fluxo homologável atual: `Novo Paciente -> Triagem -> Pacientes / Prontuários -> Agenda`.
- `.venv/bin/pytest -q`: `192 passed`.
- Testes focados de fluxo Triagem/Paciente, rastreabilidade e segurança: `tests/test_triage_patient_link_flow.py`, `tests/test_phase2_traceability.py` e `tests/test_phase1_security.py`: `15 passed`.
- `.venv/bin/python -m py_compile database.py blueprints/patients.py blueprints/triage.py services/patient_service.py`: sem erros.
- `git diff --check`: sem erros.
- `docker compose up -d --build`: executado com rebuild da aplicação web, worker Celery, beat e mail.
- `docker compose ps`: containers principais em execução; PostgreSQL e Redis saudáveis.
- `/health`: `status=healthy`, `database=ok`.
- PostgreSQL: `triagem_senhas.patient_id` sem restrição `UNIQUE`, permitindo múltiplas senhas/demandas por paciente.

Validações anteriores mantidas como referência histórica:

- `.venv/bin/pytest -q`: `190 passed` em 16/06/2026.
- Testes focados de autenticação/pré-cadastro: `.venv/bin/pytest -q tests/test_auth_flow_service.py`: `11 passed`.
- `python3 -m compileall blueprints/professional_registration.py blueprints/admin.py services/professional_registration_service.py`: sem erros.
- `docker compose up -d --build gestaoclinica`: executado com rebuild da aplicação web.
- `docker compose ps`: containers principais em execução; PostgreSQL e Redis saudáveis.
- `/health`: `status=healthy`, `database=ok`.
- Template administrativo de pré-cadastros carregado no container sem erro.
- `.venv/bin/pytest -q`: `179 passed` em 16/06/2026 após pacote probatório.
- Testes focados de assinatura probatória, linha do tempo e segurança: `tests/test_signature_evidence_service.py`, `tests/test_phase2_traceability.py` e `tests/test_phase1_security.py`: `17 passed`.
- `git diff --check`: sem erros em validação anterior da rodada.
- `python3 -m compileall blueprints/patients.py services/signature_evidence_service.py database.py`: sem erros.
- `docker compose up -d --build`: executado com rebuild da aplicação web, worker Celery e beat.
- Banco: tabela `signature_events` criada e indexada no PostgreSQL.
- `.venv/bin/pytest -q`: `170 passed` em 15/06/2026.
- Testes focados Endodontia/Central/Visual: `tests/test_phase4_endodontia.py`, `tests/test_phase2_command_center.py` e `tests/test_phase2_visual_media.py`: `83 passed`.
- Testes focados E8/E9/E10/Central: `tests/test_phase4_endodontia.py` e `tests/test_phase2_command_center.py`: `75 passed`.
- Templates carregados no container: `endodontia/followup.html`, `patients/includes/_tab_endodontia.html`, `patients/includes/_tab_visual.html` e `command_center.html`: sem erros.
- Rotas resolvidas no container: `/endodontia/followup/1`, `/endodontia/followup/save_details/1`, `/endodontia/followup/add/1`, `/endodontia/proservation/1/evaluate`, `/endodontia/followup/1/budget/generate`, `/endodontia/followup/1/images/upload`, `/endodontia/image/1` e `/agenda/`.
- Endodontia E6: obturação final, controle radiográfico, restauração definitiva e pendência restauradora na Central validados por testes.
- Endodontia E7: `endodontia_imagens`, categorias endodônticas, metadados, origem `Endodontia` na Biblioteca Visual e arquivos sensíveis validados por testes e carga de template.
- Endodontia E8: `endodontia_proservacao`, agenda longitudinal, Strindberg e pendência de proservação vencida na Central validados por testes.
- Endodontia E9: `endodontia_orcamento_items`, orçamento por canal, complexidade, TUSS/SIGTAP de referência e bloqueio para `polpa_normal` validados por testes.
- Endodontia E10: teste de fluxo clínico ponta a ponta em nível de serviço, teste de mapa de rotas, manual rápido e QA de aceite documentados.

VOLTE E VERIFIQUE: repetir validação completa antes de qualquer entrega final ou implantação.

## Acessos e Rotas de Referência

- Landing Page: `https://sorrisodagentealagoas.com`
- Painel: `/dashboard`
- Pacientes: `/patients/list`
- Fila Vermelha: `/patients/red-alerts`
- Triagem: `/triagem/`
- Senhas: `/triagem/senhas`
- Agenda: `/agenda/`
- Central de Comando: `/command-center`
- Resumo Diário: `/command-center/daily-summary`
- Exportação CSV da Central: `/command-center/daily-summary/export.csv`
- Endodontia - ficha do caso: `/endodontia/followup/<endo_id>`
- Endodontia - avaliar proservação: `POST /endodontia/proservation/<proservation_id>/evaluate`
- Endodontia - gerar orçamento: `POST /endodontia/followup/<endo_id>/budget/generate`
- Epidemiologia: `/epidemiologia`
- BI: `/bi`
- PDF Governamental do BI: `POST /bi/export`
- Relatórios Institucionais: `/reports/institutional`
- Estoque: `/admin/inventory`
- Unidades: `/admin/execution-units`
- Custos SIGTAP: `/admin/finance/cost-references`
- SIGTAP/e-SUS APS: `/admin/integrations/esus`
- Auditoria: `/admin/audit`
- Health: `/health`
- Banco no host: porta `5433`

---

© 2026 Programa Sorriso da Gente. Todos os direitos reservados.
