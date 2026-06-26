# Plano Mestre de Manuais, Roteiros e Videoaulas

Versão do plano: **1.0**

Aplicação de referência: **4.0.0-rc.1**

Início: **22/06/2026**

Status geral: **em elaboração**

Ambiente de gravação: **disponível e validado**

## 1. Objetivo

Produzir treinamento por atividade e perfil de acesso para a entrada assistida
do Gestão Saúde Oral. Cada atividade deve resultar em:

1. roteiro validado;
2. videoaula gravada;
3. conjunto de capturas aprovado;
4. manual ilustrado em PDF;
5. aceite do perfil responsável.

## 2. Escopo

Perfis atendidos:

- Administrador;
- Coordenação;
- Recepção;
- Clínicos;
- CME / Estoque;
- Radiologia;
- Comunicação;
- SSA/SMS;
- Auditoria.

Ficam fora deste primeiro ciclo: Endodontia, Prótese, Portal do Paciente e
novas funcionalidades de BI.

## 3. Etapas de produção

### Etapa 1 — Catálogo e priorização

Critério de aceite: atividades, público, dependências e ordem aprovados.

### Etapa 2 — Roteiro

Cada roteiro deve conter objetivo, perfil, preparação, texto falado, ação na
tela, alertas, resultado esperado e checklist.

Critério de aceite: o fluxo pode ser executado integralmente seguindo apenas o
roteiro.

### Etapa 3 — Preparação do ambiente

Criar usuários e pacientes fictícios, limpar notificações desnecessárias e
garantir que nenhum dado pessoal real apareça.

Critério de aceite: cenário reproduzível e seguro para gravação.

### Etapa 4 — Gravação

Gravar uma atividade por vídeo, preferencialmente entre 3 e 8 minutos.

Critério de aceite: imagem legível, áudio compreensível e fluxo concluído sem
exposição de credenciais ou dados reais.

### Etapa 5 — Capturas

Selecionar imagens que mostrem entrada, ação principal, confirmação e resultado.

Critério de aceite: arquivos nomeados, sem dados reais e correspondentes à
versão documentada.

### Etapa 6 — Manual PDF

Converter o roteiro em instruções ilustradas, incluindo pré-requisitos,
passos, alertas e solução de erros comuns.

Critério de aceite: PDF revisado visualmente e executável por usuário do perfil.

### Etapa 7 — Homologação

O perfil responsável executa a atividade usando o vídeo e o manual.

Critério de aceite: aceite registrado ou correções documentadas.

### Etapa 8 — Publicação e manutenção

Publicar os links aprovados e revisar os materiais quando telas, permissões ou
regras forem alteradas.

Critério de aceite: versão, data de revisão e responsável visíveis.

## 4. Primeiro pacote

Legenda: `Pendente`, `Em elaboração`, `Pronto para validar`, `Aprovado`,
`Gravado`, `Publicado` ou `Bloqueado`.

| Nº | Atividade | Perfil principal | Roteiro | Gravação | Capturas | PDF | Aceite |
|---:|---|---|---|---|---|---|---|
| 01 | Primeiro acesso | Todos | Pronto para validar | Pendente | Pronto para validar | Pronto para validar | Pendente |
| 02 | Novo usuário | Administrador | Pronto para validar | Pendente | Pronto para validar | Pronto para validar | Pendente |
| 03 | Novo paciente | Recepção | Pronto para validar | Pendente | Pronto para validar | Pronto para validar | Pendente |
| 04 | Triagem | Recepção | Pronto para validar | Pendente | Pronto para validar | Pronto para validar | Pendente |
| 05 | Agenda | Recepção e Clínicos | Pronto para validar | Pendente | Pronto para validar | Pronto para validar | Pendente |
| 06 | TCLE | Clínicos | Pronto para validar | Pendente | Pronto para validar | Pronto para validar | Pendente |
| 07 | Anamnese | Clínicos | Pronto para validar | Pendente | Pronto para validar | Pronto para validar | Pendente |
| 08 | Plano de tratamento e evolução | Clínicos | Pronto para validar | Pendente | Pronto para validar | Pronto para validar | Pendente |
| 09 | Central de Comando | Coordenação | Pronto para validar | Pendente | Pronto para validar | Pronto para validar | Pendente |

## 5. Ordem recomendada de gravação

1. Primeiro acesso;
2. novo usuário;
3. novo paciente;
4. triagem;
5. agenda;
6. TCLE;
7. anamnese;
8. plano de tratamento e evolução;
9. Central de Comando.

A ordem acompanha o ciclo operacional: acesso, preparação da equipe,
acolhimento do paciente, organização da demanda, atendimento e gestão.

## 6. Convenção de arquivos

- roteiro: `NN_nome_da_atividade.md`;
- captura: `NN_nome_da_atividade_PP_descricao.png`;
- manual-fonte: `NN_nome_da_atividade_manual.md`;
- PDF: `NN_nome_da_atividade_vX.Y.pdf`;
- registro de vídeo: `NN_nome_da_atividade_video.md`.

## 7. Modelo do registro de avanço

Ao final de cada etapa, acrescentar uma linha:

| Data | Atividade | Etapa | Responsável | Resultado | Pendência | Próximo passo |
|---|---|---|---|---|---|---|
| DD/MM/AAAA | Nome | Roteiro/Gravação/Capturas/PDF/Aceite | Nome | Entrega realizada | Ajustes necessários ou “nenhuma” | Ação seguinte |

## 8. Histórico de avanços

| Data | Atividade | Etapa | Responsável | Resultado | Pendência | Próximo passo |
|---|---|---|---|---|---|---|
| 22/06/2026 | Plano geral | Planejamento | Equipe do projeto | Estrutura e regras de acompanhamento definidas | Validar prioridades com a coordenação | Revisar os nove roteiros |
| 22/06/2026 | Pacote 01–09 | Roteiro | Equipe do projeto | Primeiras versões dos nove roteiros criadas | Validar texto falado e cenário de demonstração | Ajustar e iniciar gravação do roteiro 01 |
| 22/06/2026 | Pacote 01–09 | Preparação do ambiente | Equipe do projeto | Ambiente Docker isolado disponível na porta 5103, com nove perfis e cenários fictícios | Nenhuma | Validar o roteiro 01 e iniciar a gravação |
| 22/06/2026 | Pacote 01–09 | Roteiros em PDF | Equipe do projeto | Nove PDFs institucionais gerados e validados na pasta de roteiros | Regenerar após qualquer alteração textual | Revisar o roteiro 01 antes da gravação |
| 22/06/2026 | Anamnese | Regra de assinatura, roteiro e implantação | Equipe do projeto | Assinatura a rogo implantada e validada em produção; roteiro 07 e PDF regenerados | Nenhuma | Gravar os dois modos de assinatura |
| 22/06/2026 | Primeiro acesso | Capturas e manual PDF | Equipe do projeto | Modelo institucional de seis páginas criado com identidade visual e quatro capturas do ambiente de treinamento | Aguardando validação visual e editorial | Aplicar ajustes aprovados e usar o padrão nos demais manuais |
| 22/06/2026 | Novo usuário | Capturas e manual PDF | Equipe do projeto | Manual institucional de seis páginas criado no padrão aprovado, com perfil Clínicos e ciclo de vida do acesso | Aguardando validação de conteúdo | Validar o Manual 02 e iniciar o Manual 03 |
| 22/06/2026 | Novo paciente | Capturas e manual PDF | Equipe do projeto | Manual institucional de seis páginas criado com pesquisa de duplicidade, identificação SUS, endereço e resultado sem triagem | Aguardando validação de conteúdo | Validar o Manual 03 e iniciar o Manual 04 |
| 22/06/2026 | Triagem | Capturas e manual PDF | Equipe do projeto | Manual institucional de seis páginas criado com ação municipal, vínculo paciente/especialidade, código da senha e consulta da fila | Aguardando validação de conteúdo | Validar o Manual 04 e iniciar o Manual 05 |
| 22/06/2026 | Agenda | Capturas e manual PDF | Equipe do projeto | Manual institucional de seis páginas criado com visão semanal, nova consulta, unidade, edição, status e escopo do Clínico | Aguardando validação de conteúdo | Validar o Manual 05 e iniciar o Manual 06 |
| 22/06/2026 | TCLE | Capturas e manual PDF | Equipe do projeto | Manual institucional de seis páginas criado com bloqueio clínico, leitura do termo, assinatura em tela, assinatura a rogo e liberação do prontuário | Aguardando validação de conteúdo | Validar o Manual 06 e iniciar o Manual 07 |
| 22/06/2026 | Anamnese | Capturas e manual PDF | Equipe do projeto | Manual institucional de seis páginas criado com entrevista inicial, riscos médicos, histórico odontológico, hábitos, assinatura em tela, assinatura a rogo e consulta da ficha | Aguardando validação de conteúdo | Validar o Manual 07 e iniciar o Manual 08 |
| 22/06/2026 | Plano de tratamento e evolução | Capturas e manual PDF | Equipe do projeto | Manual institucional de seis páginas criado com planejamento SIGTAP, validação profissional, evolução clínica, três confirmações e Linha do Tempo | Aguardando validação de conteúdo | Validar o Manual 08 e iniciar o Manual 09 |
| 23/06/2026 | Central de Comando | Conteúdo-fonte, HTML e gerador | Equipe do projeto | Manual institucional criado no padrão aprovado com cobertura completa dos cinco passos operacionais (filtros, indicadores, fila inteligente, alertas e resumo diário); conteúdo-fonte em Markdown, HTML diagramado e script Python gerador criados | Aguardando geração das capturas de tela e validação de conteúdo | Iniciar o ambiente de treinamento e executar `generate_command_center_manual.py` para gerar as capturas e o PDF |

## 9. Checklist permanente

- [ ] utilizar somente dados fictícios;
- [ ] ocultar senhas, tokens, e-mails privados e dados sensíveis;
- [ ] confirmar o perfil usado na gravação;
- [ ] informar a versão da aplicação;
- [ ] mostrar o resultado final da atividade;
- [ ] revisar linguagem e termos institucionais;
- [ ] registrar o avanço neste documento;
- [ ] atualizar o README quando houver mudança de escopo ou prontidão.
