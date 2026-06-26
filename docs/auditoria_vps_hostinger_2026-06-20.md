# Auditoria e Hardening da VPS Hostinger — 20/06/2026

## Escopo

Auditoria inicial executada em modo leitura pela API oficial da Hostinger e
diretamente na VPS `srv1403247`. Depois da validação e autorização de cada
pacote, foram isolados o legado, os painéis e as publicações diretas, e foi
aplicado o firewall Hostinger descrito neste documento.

O token não foi exibido. O arquivo local estava com permissão `0600`.

## Resultado Executivo

A auditoria confirma a decisão **NO-GO para produção plena**.

A aplicação Gestão Saúde Oral está corretamente isolada em Docker, com web em
`127.0.0.1:5003` e PostgreSQL somente na rede interna. A auditoria inicial
encontrou os riscos abaixo na borda compartilhada da VPS:

- nenhum firewall Hostinger está associado à VPS;
- o PostgreSQL da aplicação legada está público em `5432`;
- aplicação legada, aplicações auxiliares e painéis administrativos estão
  publicados diretamente;
- Portainer e Uptime Kuma possuem acesso ao socket Docker e estão acessíveis
  publicamente;
- Cockpit e Webmin também estão públicos;
- os containers não possuem limites de CPU, memória ou PIDs.

## Hostinger

Dados confirmados pela API:

- VPS ID `1403247`;
- plano KVM 2;
- 2 vCPUs;
- 8 GB de RAM;
- 100 GB de disco;
- Debian 13;
- estado `running`;
- IPv4 `72.60.248.85`;
- PTR do IPv4: `mail.sorrisodagentealagoas.com`;
- `firewall_group_id: null`;
- duas restaurações semanais disponíveis, criadas em 12/06/2026 e 19/06/2026;
- nenhum snapshot ativo;
- Monarx não instalado;
- nenhum SSH public key cadastrado pelo recurso de chaves da Hostinger.

Existe um firewall Hostinger chamado `teste`, mas:

- não está associado à VPS;
- não está sincronizado;
- possui somente uma regra TCP pública para a porta `18789`;
- não representa a política necessária para esta VPS.

Estado após o hardening de 20/06/2026:

- criado o firewall novo `srv1403247-producao-minimo-20260620`, ID `315250`;
- regras de entrada limitadas a TCP `22`, TCP `80`, TCP `443` e UDP `41641`;
- firewall associado à VPS `1403247` e sincronizado pela API;
- o grupo `teste` não foi reutilizado nem associado;
- verificações IPv4/IPv6 mantiveram somente `22/80/443` públicos entre as
  portas inventariadas;
- verificação TCP externa confirmou `22/80/443` abertos e `5432/9443`
  fechados;
- Gestão Saúde Oral, Gestão Clínica legada, MotoFlow, Galeria, RecadFácil e
  Navidrome continuaram acessíveis pelos proxies;
- Portainer, Uptime Kuma e OpenGravity continuaram acessíveis pela Tailscale;
- `tailscale netcheck` confirmou UDP e conectividade IPv4/IPv6.

Exceção preexistente e não causada pelo firewall:

- `/bootdp` responde `502` porque não existe processo ouvindo em
  `127.0.0.1:18789`;
- `openclaw.diegopereira.cloud` não possui resolução DNS.

## Recursos

Métricas Hostinger de 13/06/2026 a 20/06/2026:

| Recurso | Média | P95 | Máximo |
|---|---:|---:|---:|
| CPU | 19,78% | 44,65% | 73,14% |
| RAM | 2,89 GiB | 4,08 GiB | 5,34 GiB |
| Disco ocupado | variável no período | até aproximadamente 79 GiB | aproximadamente 79 GiB |

Estado observado no host:

- disco: 43 GiB usados de 99 GiB, 52 GiB livres;
- memória: 3,5 GiB usados e 4,3 GiB disponíveis;
- swap: 1,9 GiB usados de 4 GiB;
- uptime: aproximadamente 92 dias;
- load average observado: `2.81`, `2.69`, `2.19` em 2 vCPUs.

Conclusão:

- não há esgotamento imediato de RAM ou disco;
- há pouca folga de CPU em picos e uso relevante de swap;
- limites por container e agendamento de tarefas pesadas são necessários na
  VPS compartilhada.

## Inventário de Portas Públicas

As portas abaixo aceitaram conexão pelo IPv4 público durante a auditoria:

| Porta | Serviço identificado | Situação recomendada |
|---:|---|---|
| `22` | SSH | manter conforme política; atualmente senha desativada e Fail2ban ativo |
| `80/443` | Nginx público | manter |
| `3001` | Galeria | mover para loopback se o acesso oficial continuar pelo Nginx |
| `3025` | Uptime Kuma | restringir a Tailscale/VPN ou loopback |
| `3333` | OpenGravity/AgenteEliza | confirmar necessidade pública ou mover para proxy |
| `5000` | MotoFlow | mover para loopback; já existe proxy Nginx |
| `5002` | Gestão Clínica legada | mover para loopback enquanto houver necessidade ou desligar |
| `5432` | PostgreSQL legado | fechar imediatamente após backup/verificação |
| `8000/9443` | Portainer | restringir a Tailscale/VPN; possui acesso ao socket Docker |
| `8080/8443` | Caddy/Galeria | revisar; evitar publicação paralela se Nginx for a borda oficial |
| `9090` | Cockpit | restringir a Tailscale/VPN ou desativar se não usado |
| `10000` | Webmin | restringir a Tailscale/VPN ou desativar se não usado |

Também foram observadas portas de sistema/Tailscale, incluindo UDP `41641`.
Elas devem ser consideradas na política final antes de aplicar o firewall.

Correção das aplicações auxiliares em 20/06/2026:

- MotoFlow `5000` movido para loopback e mantido pelo proxy Nginx;
- Galeria `3001` movida para loopback e mantida pelo proxy Nginx;
- Caddy da Galeria removido; `8080/8443` fechadas e volumes preservados;
- OpenGravity `3333` identificado como painel administrativo sem autenticação,
  capaz de alterar configurações, OAuth, WhatsApp e treinamento;
- como o agente utiliza conexões de saída e não recebe webhook externo, o
  painel foi restrito à Tailscale em `100.79.5.76:3333`;
- portas `3001`, `3333`, `5000`, `8080` e `8443` fechadas externamente em IPv4
  e IPv6;
- backup local e externo criado antes da alteração.

## Docker

Aplicação nova:

- `gestaosaudeoral-web`: somente `127.0.0.1:5003`;
- PostgreSQL, Redis, Celery, Beat, Postfix e backup sem publicação no host;
- estado saudável na observação.

Aplicação legada:

- `gestaoclinica-docker`: `0.0.0.0:5002`;
- `gestaoclinica-postgres`: `0.0.0.0:5432`;
- base confirmada com 19 pacientes, 8 usuários e 39 atendimentos;
- Nginx ainda publica `/GestaoClinica/`;
- Uptime Kuma monitora a aplicação legada.

Backups legados:

- não foi encontrado dump PostgreSQL recente no diretório do projeto;
- os arquivos locais encontrados são de março de 2026 e não substituem um
  backup verificado do PostgreSQL atual;
- os backups semanais da Hostinger protegem a VPS inteira, mas não substituem
  um dump lógico e uma restauração verificável da aplicação legada.

Todos os containers observados estão sem limites de memória, CPU e PIDs. Com
exceção da Galeria, os containers inspecionados não definem usuário não-root.

## Painéis Administrativos

Achado original:

- Portainer está público e monta `/var/run/docker.sock`;
- Uptime Kuma está público e também monta `/var/run/docker.sock`;
- Cockpit está público;
- Webmin está público e executa como root.

Comprometimento de um painel com socket Docker equivale, na prática, a controle
amplo sobre containers e host. Esses painéis devem ser retirados da internet e
acessados pela Tailscale já instalada ou por outra VPN/rede administrativa.

Correção aplicada em 20/06/2026:

- Portainer restrito ao IP Tailscale `100.79.5.76`, portas `8000/9443`;
- Uptime Kuma restrito ao IP Tailscale `100.79.5.76`, porta `3025`;
- volumes e dados preservados;
- Cockpit desinstalado;
- Webmin desinstalado, incluindo repositório e chave;
- portas `3025`, `8000`, `9443`, `9090` e `10000` fechadas no IPv4 público;
- Portainer/Uptime validados pela Tailscale;
- backup local e externo das configurações criado antes da remoção.

## SSH

Confirmado:

- `PasswordAuthentication no`;
- `KbdInteractiveAuthentication no`;
- duas chaves no `authorized_keys` do usuário `diego`;
- Fail2ban ativo e habilitado;
- Tailscale ativa.

Pendente:

- `PermitRootLogin yes` permite login root por chave;
- revisar as chaves autorizadas de root e alterar para
  `PermitRootLogin prohibit-password` ou `no`, conforme a operação permitir;
- considerar SSH administrativo pela Tailscale depois de validar acesso de
  contingência.

## Uptime Kuma

Monitores existentes:

- Moto Flow;
- Gestão Clínica legada;
- ping da VPS;
- OpenGravityEliza.

Não existe monitor para:

- `https://sorrisodagentealagoas.com/health`;
- idade do backup da aplicação;
- sincronização Google Drive;
- disco;
- Celery/Postfix.

## Domínio e DNS

Confirmado pela API Hostinger:

- domínio `sorrisodagentealagoas.com` ativo;
- expiração em 30/04/2027;
- bloqueio de transferência ativo;
- proteção de privacidade ativa;
- A e `www` apontando para a VPS;
- `mail` e MX configurados;
- SPF, DKIM e DMARC presentes;
- PTR do IPv4 coerente com o host de e-mail.

HTTPS observado:

- certificado Let's Encrypt válido;
- validade até 29/07/2026;
- página principal e `/health` responderam HTTP 200.

## API Hostinger

O token da API pode executar operações destrutivas conforme as permissões da
conta. Mantê-lo dentro da própria VPS aumenta o impacto de um comprometimento.

Procedimento recomendado:

1. manter o arquivo `0600` somente durante o trabalho de infraestrutura;
2. não registrar o token em comandos, logs, Git ou documentação;
3. ao concluir a organização da VPS, revogar o token no hPanel;
4. apagar o arquivo local;
5. criar um novo token apenas quando uma nova manutenção exigir.

## Ordem de Correção Recomendada

1. Criar dump e restore verificável da Gestão Clínica legada.
2. Retirar imediatamente o PostgreSQL legado da interface pública.
3. Mover a aplicação legada para loopback enquanto a decisão de
   migração/arquivamento não for tomada.
4. Restringir Portainer, Uptime Kuma, Cockpit e Webmin à Tailscale/VPN.
5. Mover aplicações já atendidas pelo Nginx para loopback.
6. Criar e associar um firewall Hostinger com a lista mínima de portas —
   concluído em 20/06/2026.
7. Cadastrar o monitor da Gestão Saúde Oral no Uptime Kuma.
8. Definir limites de recursos por container.
9. Revisar SSH root e rotacionar/revogar o token da API.

## Atualização Operacional Após a Auditoria

Em 20/06/2026 foi executada a primeira parte do item 1:

- backup legado local em
  `/home/diego/projetos/backups/GestaoClinica/20260620_091443`;
- cópia externa validada em
  `sorriso.drive:backup_vps_snapshots/GestaoClinica/20260620_091443`;
- dump PostgreSQL, logs, volume de PDFs, relatório de integridade e manifesto
  SHA-256 preservados;
- restauração das seções de estrutura e dados confirmou 20 tabelas, 19
  pacientes, 8 usuários e 39 atendimentos;
- a restauração completa das constraints foi impedida por inconsistências já
  presentes na origem: 1 anamnese, 2 procedimentos, 6 próteses e 1 receituário
  apontam para pacientes ausentes;
- nenhuma linha da base legada foi corrigida ou removida;
- em seguida, o Compose legado foi alterado para publicar a aplicação somente
  em `127.0.0.1:5002` e não publicar o PostgreSQL no host;
- containers web/PostgreSQL foram recriados preservando os volumes;
- health interno e proxy Nginx permaneceram funcionais;
- contagens permaneceram em 19 pacientes, 8 usuários e 39 atendimentos;
- `5002/5432` foram confirmadas fechadas externamente em IPv4 e IPv6;
- migração, arquivamento ou desligamento definitivo continuam como decisão
  posterior.

Também foi redefinida a base ativa da Gestão Saúde Oral, após backup e restore
prévio:

- 0 pacientes e 0 atendimentos;
- somente `Diego` (#8) e `Cibely.adm` (#12);
- pasta ativa do paciente removida do Drive;
- arquivos clínicos locais removidos;
- baseline pós-limpeza `gestao_saude_oral_20260620_092016.dump` restaurada com
  54 tabelas e os dois usuários esperados.

Em seguida, os painéis administrativos foram protegidos:

- definição persistente criada em
  `/home/diego/projetos/infra-admin-panels/docker-compose.yml`;
- Portainer disponível somente em `https://100.79.5.76:9443`;
- Uptime Kuma disponível somente em `http://100.79.5.76:3025`;
- Cockpit e Webmin desinstalados;
- backups em `/home/diego/projetos/backups/AdminPanels`;
- cópia externa validada em
  `sorriso.drive:backup_vps_snapshots/AdminPanels/system-panels-20260620_111120`.

Também foram reduzidas as publicações diretas:

- MotoFlow e Galeria ficaram em loopback e continuam acessíveis pelo Nginx;
- Caddy da Galeria foi removido;
- OpenGravity ficou somente na Tailscale;
- pacote de rollback:
  `/home/diego/projetos/backups/SharedApps/20260620_111830`;
- cópia externa:
  `sorriso.drive:backup_vps_snapshots/SharedApps/20260620_111830`.

Por fim, foi aplicado o firewall Hostinger:

- grupo novo `srv1403247-producao-minimo-20260620`, ID `315250`;
- regras TCP `22/80/443` e UDP `41641`;
- associação e sincronização confirmadas pela API;
- serviços públicos, acessos Tailscale e portas fechadas revalidados após a
  aplicação.

## Referências Oficiais

- Hostinger API: https://developers.hostinger.com/
- Hostinger API MCP oficial e lista de endpoints:
  https://github.com/hostinger/api-mcp-server
- Guia oficial da API Hostinger:
  https://www.hostinger.com/support/10840865-what-is-hostinger-api/
