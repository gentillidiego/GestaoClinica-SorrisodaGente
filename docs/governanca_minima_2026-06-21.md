# Política de governança mínima — Gestão Saúde Oral

Versão: 1.0

Data: 21/06/2026

Escopo: Programa Sorriso da Gente

Esta política define responsáveis, acesso mínimo, retenção, descarte,
recuperação e resposta a incidentes. Não contém senhas, tokens, códigos de
recuperação nem dados de pacientes.

## 1. Responsáveis

| Função | Titular | Responsabilidade |
|---|---|---|
| Autoridade institucional e aprovadora de acessos | Dra. Cibely Candido | Aprovar acesso administrativo, retenção, descarte, restauração extraordinária e comunicação institucional |
| Ponto de contato de privacidade/LGPD e coordenadora de incidente | Dra. Cibely Candido | Receber demandas de titulares, decidir comunicação e coordenar resposta institucional |
| Custodiante técnico | Diego | VPS, Docker, deploy, RBAC, OAuth/rclone, logs, contenção técnica e recuperação |
| Responsável operacional por backup e restauração | Diego | Verificar backup, cópia externa, integridade, restore periódico e evidências |
| Revisão independente | Perfil Auditoria ou pessoa indicada pela autoridade institucional | Revisar acessos, logs, incidentes e evidências sem alterar registros clínicos |

Continuidade:

- na indisponibilidade de Diego, a Dra. Cibely autoriza um prestador técnico
  substituto, com credencial individual, prazo definido e auditoria;
- na indisponibilidade da Dra. Cibely, a Coordenação deve registrar por escrito
  quem assume temporariamente as aprovações institucionais;
- códigos de recuperação e segundo fator não podem ficar exclusivamente com o
  custodiante técnico;
- nenhuma pessoa deve aprovar e executar sozinha um descarte definitivo de
  prontuário.

Esta política usa “ponto de contato de privacidade/LGPD”, sem declarar
automaticamente a função legal de encarregado. A designação formal de
encarregado, se aplicável à natureza jurídica e ao risco do controlador, deve
ser feita em ato institucional próprio.

## 2. Matriz de decisão e execução

| Operação | Aprova | Executa | Evidência |
|---|---|---|---|
| Criar ou elevar usuário administrativo | Dra. Cibely | Diego | Solicitação, perfil, data e auditoria |
| Inativar usuário desligado | Gestor da área ou Dra. Cibely | Administrador autorizado | Data, motivo e auditoria |
| Alterar firewall, OAuth, backup ou infraestrutura crítica | Dra. Cibely quando houver impacto operacional | Diego | Plano, backup, validação e rollback |
| Restaurar produção | Dra. Cibely | Diego | Motivo, backup escolhido, hashes e validação |
| Descartar prontuário/documento clínico | Dra. Cibely + responsável clínico/jurídico | Diego | Termo de descarte e lista de IDs |
| Comunicar incidente à ANPD/titulares | Dra. Cibely | Ponto de contato designado | Protocolo e registro do incidente |

## 3. Acesso mínimo

- O acesso da aplicação segue a matriz RBAC documentada em
  `docs/matriz_rbac_rotas_2026-06-20.md`.
- Acesso à VPS, Tailscale, Portainer, Google Drive e backups é administrativo e
  não decorre automaticamente do perfil usado na aplicação.
- Contas são individuais. Credenciais compartilhadas são proibidas, salvo
  recuperação institucional controlada.
- Administradores da aplicação são revisados mensalmente; acessos externos,
  chaves SSH, sessões Google, apps OAuth e compartilhamentos são revisados
  trimestralmente.
- Contas com histórico clínico são inativadas, não apagadas.
- No desligamento ou troca de função, os acessos são removidos no mesmo dia e
  credenciais/códigos compartilhados são rotacionados.
- O usuário `root` da VPS consegue acessar volumes e segredos apesar do Docker;
  esse acesso fica restrito, usa chave SSH individual e deve permanecer
  rastreável.

## 4. Conta Google institucional

Conta proprietária: `sorrisodagentealagoas@gmail.com`.

Controles obrigatórios:

1. Verificação em duas etapas ativa.
2. Dois meios institucionais de recuperação, sob custódias diferentes.
3. Preferência por duas passkeys ou chaves de segurança; autenticador é
   alternativa.
4. Códigos de recuperação guardados fora da VPS e do Git.
5. Revisão trimestral de dispositivos, sessões, apps OAuth, encaminhamentos de
   e-mail e compartilhamentos.
6. Revogação imediata após desligamento ou suspeita de comprometimento.

O repositório registra somente a data e o resultado da revisão, nunca os
segredos ou códigos.

## 5. Retenção

| Categoria | Regra |
|---|---|
| Prontuário, exames, imagens, documentos e assinaturas clínicas | Mínimo de 20 anos após o último registro. A política padrão é não eliminar automaticamente; após 20 anos exige revisão clínica, jurídica e institucional |
| Evidências de consentimento e assinatura | Mesmo prazo do prontuário relacionado |
| Logs de auditoria e eventos de assinatura | 5 anos, ou o prazo maior do prontuário quando necessários para sua integridade/rastreabilidade |
| Registro de incidentes de segurança | Mínimo de 5 anos |
| Usuário desligado | Conta inativa; vínculos clínicos seguem o prazo do prontuário e o histórico administrativo/auditoria, no mínimo, 5 anos |
| Backup local | 30 dias |
| Backup externo | 90 dias |
| Cache local de originais do Drive | 2 dias, sujeito também ao limite LRU |
| Staging de upload | Até sincronização; órfãos sem referência só podem ser limpos após a janela técnica de segurança |
| Miniaturas e prévias clínicas | Enquanto o arquivo clínico relacionado estiver ativo |
| Relatórios/PDFs temporários | Remover após uso ou, no máximo, em 7 dias; a cópia incorporada ao prontuário segue o prazo clínico |

Backups são instrumentos de recuperação, não arquivos permanentes. Depois de um
descarte aprovado, o item pode permanecer em backups imutáveis até completar a
retenção de 90 dias. Se um backup for restaurado nesse período, a lista de
descarte deve ser reaplicada antes da liberação do ambiente.

## 6. Descarte

Não existe descarte automático de prontuário clínico.

Fluxo obrigatório:

1. Abrir solicitação com fundamento, paciente/IDs, categoria e intervalo.
2. Verificar prazo de retenção, litígio, auditoria, obrigação legal e pedido do
   titular.
3. Obter aprovação da Dra. Cibely e de responsável clínico/jurídico.
4. Gerar backup e manifesto antes da operação quando o descarte for em lote.
5. Executar por identificadores persistidos, sem comandos amplos ou caminhos
   informados pelo solicitante.
6. Remover cópias ativas, derivados e compartilhamentos relacionados.
7. Registrar executor, aprovadores, data, motivo, quantidade e resultado.
8. Manter a lista de descarte até expirar o último backup que ainda possa conter
   os itens.

Solicitação de titular não implica eliminação imediata quando a conservação for
necessária para obrigação legal/regulatória ou exercício de direitos.

## 7. Backup e recuperação

- Backup diário de PostgreSQL, uploads e manifesto SHA-256.
- Cópia externa validada por `rclone check --download`.
- Restore isolado trimestral e antes de cada Go/No-Go.
- Objetivo inicial de ponto de recuperação (RPO): até 24 horas.
- Objetivo inicial de recuperação (RTO): até 8 horas para o serviço clínico
  principal, condicionado à disponibilidade da VPS e do provedor.

Ordem de recuperação:

1. Conter o incidente e preservar evidências.
2. Confirmar autorização institucional para restaurar produção.
3. Escolher o backup pelo manifesto e validar hashes.
4. Restaurar em ambiente isolado.
5. Validar banco, arquivos, autenticação, RBAC, Celery, Drive e saúde HTTP.
6. Reaplicar lista de descarte posterior ao backup, se houver.
7. Liberar produção e registrar perda de dados estimada, duração e aprovadores.

## 8. Incidentes

Incidente inclui acesso indevido, vazamento, alteração, indisponibilidade, perda
de dados, ransomware, credencial exposta ou envio ao destinatário errado.

Prazos internos:

- alerta ao custodiante técnico e à Dra. Cibely: imediato, meta de até 2 horas;
- contenção inicial e preservação de evidências: tão logo seja seguro;
- avaliação preliminar de dados/titulares/risco: até 24 horas;
- quando houver risco ou dano relevante, comunicação pelo controlador à ANPD e
  aos titulares: até 3 dias úteis do conhecimento;
- complementação fundamentada: até 20 dias úteis;
- registro do incidente: mínimo de 5 anos.

Procedimento:

1. Registrar data/hora, descoberta, sistemas e dados potencialmente afetados.
2. Conter sem destruir evidência: inativar usuário, revogar sessão/token,
   restringir rede ou isolar serviço.
3. Preservar logs, hashes, imagens e cronologia.
4. Avaliar confidencialidade, integridade, disponibilidade, titulares e dados
   sensíveis.
5. Dra. Cibely decide, com apoio técnico/jurídico, a comunicação necessária.
6. Recuperar por credencial limpa e restore validado.
7. Registrar causa, impacto, comunicação, correção e prevenção.

## 9. Direitos dos titulares

- O ponto de contato de privacidade recebe pedidos de confirmação, acesso,
  correção, informação e eliminação quando aplicável.
- A identidade do solicitante deve ser validada antes de revelar dados.
- O atendimento e sua decisão são registrados sem incluir dados clínicos em
  canal inadequado.
- Pedidos incompatíveis com obrigação legal de guarda recebem resposta
  fundamentada e preservam o prontuário.

## 10. Revisão e aprovação

- Revisão ordinária: anual.
- Revisão extraordinária: após incidente relevante, mudança legal, troca de
  responsáveis ou alteração importante de arquitetura.

Registro de aceite:

| Papel | Nome | Situação |
|---|---|---|
| Autoridade institucional | Dra. Cibely Candido | Assinatura/aceite formal pendente |
| Custodiante técnico | Diego | Política implementada tecnicamente |
| Responsável clínico/jurídico | A indicar pela autoridade institucional | Pendente |

Até o aceite institucional, esta política funciona como procedimento técnico
provisório e bloqueia a declaração de Go/No-Go final.

## Fontes oficiais

- Lei nº 13.787/2018 — guarda mínima de prontuário:
  https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/L13787.htm
- LGPD — Lei nº 13.709/2018:
  https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/L13709compilado.htm
- ANPD — agentes de tratamento de pequeno porte:
  https://www.gov.br/anpd/pt-br/acesso-a-informacao/institucional/atos-normativos/regulamentacoes_anpd/resolucao-cd-anpd-no-2-de-27-de-janeiro-de-2022
- ANPD — comunicação de incidentes:
  https://www.gov.br/anpd/pt-br/assuntos/comunicacao-de-incidentes-de-seguranca-cis
- CFO — Manual do Prontuário:
  https://website.cfo.org.br/wp-content/uploads/2026/03/CFO_Manual_do_Prontuario_Ebook.pdf
