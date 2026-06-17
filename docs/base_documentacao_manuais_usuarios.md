# Documentação Base para Manuais de Usuários - Gestão Saúde Oral

## 1. Introdução
Esta documentação consolida as regras de negócio, fluxos operacionais e permissões do sistema "Gestão Saúde Oral - Programa Sorriso da Gente". O objetivo é servir como base unificada para a criação de apostilas, tutoriais e treinamentos para os diferentes perfis de usuários.

Decisão operacional registrada em 17/06/2026: o escopo de Endodontia, Prótese, Portal do Paciente e evoluções de BI está congelado até o Go/No-Go de produção. O treinamento deve cobrir apenas os fluxos ativos e homologáveis da versão atual. O BI existente pode ser usado para validação gerencial e relatórios já implementados, sem promessa de novas visões, indicadores, redesign ou ampliações antes da produção assistida.

---

## 2. Perfis de Acesso e Permissões
O sistema opera com 9 perfis unificados. Cada perfil enxerga apenas os módulos pertinentes ao seu trabalho.

1. **Administrador** (`admin`): Acesso total. Gestão de usuários, senhas, acessos a logs de auditoria e configurações de integrações (SIGTAP/e-SUS).
2. **Coordenação** (`coordenacao`): Foco em gestão clínica e fila. Acesso à Central de Comando, BI, Epidemiologia, Agenda completa com edição, Pacientes e Custos SIGTAP.
3. **Clínicos** (`clinicos`): Odontólogos e auxiliares. Acesso ao Prontuário, à própria Agenda, Fila, Estomatologia, Evoluções, Assinaturas e Consumo de Estoque.
4. **Recepção** (`recepcao`): Acesso a Pacientes (cadastro e edição), Triagem, Agenda (marcação, confirmação, faltas) e geração de documentos.
5. **CME / Estoque** (`cme`): Foco no cadastro de materiais, lotes, fornecedores, ajustes administrativos e laudos de laboratório.
6. **Radiologia** (`radiologia`): Acesso a Pacientes e Exames (upload de radiografias, lote de imagens).
7. **Comunicação** (`comunicacao`): Acesso aos relatórios institucionais e painel BI para métricas sociais e marketing.
8. **SSA/SMS** (`ssa_sms`): Visão governamental restrita (BI Executivo e Mapa Epidemiológico).
9. **Auditoria** (`auditoria`): Acesso aos relatórios, logs do sistema e configuração de integrações (apenas visualização).

---

## 3. Navegação e Menus
O sistema organiza o menu lateral em blocos lógicos:
*   **Principal:** Início e Central de Comando.
*   **Operação Clínica:** Novo Paciente, Triagem, Pacientes / Prontuários e Agenda.
*   **Gestão e Indicadores:** Mapa Epidemiológico, BI Executivo, Relatórios.
*   **Financeiro e SUS:** Custos SIGTAP, Integração SIGTAP/e-SUS.
*   **Administração:** Usuários, Pré-cadastros, Unidades, Estoque, Auditoria.

---

## 4. Módulos e Fluxos Operacionais

### 4.1. Central de Comando (`/command-center`)
O coração da operação clínica. Centraliza alertas e prioridades.
*   **Fila Inteligente SUS:** Lista de pacientes aguardando. A prioridade é automática baseada em: Suspeita Oncológica, Idoso, Faltas Recorrentes, Tratamentos Pendentes, Lesão sem Retorno, Dor Aguda, Diabetes, Vulnerabilidade Socioeconômica e Tempo de Espera.
*   **Métricas Operacionais:** Espera média, fila ativa (30+, 60+, 90+ dias), gargalos de agenda por profissional, pacientes sem retorno.
*   **Metas Operacionais Automáticas:** Placar por recorte com produção clínica, comparecimento, conclusão de tratamento e fila reduzida. Cada meta mostra valor atual, alvo automático, progresso, status e conduta recomendada.
*   **Pendências Clínicas:**
    *   Exames pendentes de validação (sem dentista responsável/data).
    *   Documentos sem assinatura (evoluções clínicas, prótese, endodontia).
    *   Retornos endodônticos vencidos, quando a próxima sessão prevista já passou e o tratamento segue em andamento ou aguardando retorno.
    *   Proservações endodônticas vencidas, quando o retorno longitudinal planejado ainda não foi concluído.
*   **Alertas Operacionais:** Estoque baixo, material vencendo/vencido, implante sem pós-operatório.
*   **Filtros:** Município, Especialidade, Profissional, Unidade e Período.
*   Para usuários do perfil Clínicos, o filtro Profissional fica preso ao próprio usuário, preservando o mesmo escopo da Agenda.
*   **Unidades de Execução:** Modelo simples para até 2 unidades ativas, cadastradas em Administração > Unidades. A unidade é definida no agendamento da consulta, conforme planejamento operacional da execução.
*   **Resumo Operacional Diário:** Botão "Resumo Diário" abre uma versão imprimível da Central de Comando com KPIs, recomendações, alertas, agenda, fila prioritária, gargalos, pendências e métricas de espera. O botão "Exportar CSV" gera planilha do mesmo recorte para prestação de contas ou reunião de coordenação.

### 4.2. Módulo de Triagem
*   **Ações de Triagem:** A equipe cria ações (ex: mutirões) por município, data e local.
*   **Senhas:** Depois que o paciente já está cadastrado, a equipe seleciona o paciente e a especialidade para gerar uma senha no formato `MUN-ESP-000` (ex: `ARA-P-001` - Arapiraca/Prótese).
*   **Múltiplas demandas:** Um mesmo paciente pode ter mais de uma senha quando houver mais de uma demanda ou especialidade. O prontuário exibe todos os encaminhamentos vinculados.
*   **Destino Operacional:** A triagem não escolhe unidade de execução durante o trabalho de campo. A senha representa a demanda eleita no município; depois, no agendamento, a população selecionada é direcionada para uma unidade de execução determinada pela operação.
*   **Vinculação:** A senha é vinculada dentro da Triagem, não no cadastro do paciente. O cadastro é o primeiro passo; a triagem vem depois para registrar a demanda.

### 4.3. Pacientes e Prontuário
O Prontuário é dividido em abas, carregadas sob demanda:
*   **Cadastro:** CPF e CNS são obrigatórios para envio ao e-SUS. O cadastro não solicita senha de triagem; a associação de senha ocorre depois no módulo de Triagem.
    *   **Endereço residencial estruturado:** A equipe informa primeiro o CEP. Quando o CEP é localizado, o sistema preenche rua, cidade, bairro e UF; a equipe completa o número.
    *   Se o CEP não for localizado, o preenchimento segue por estado, cidade, bairro, rua e número. Alagoas aparece primeiro na lista de estados.
    *   Bairro, cidade, UF, CEP e código IBGE ficam gravados em campos próprios para apoiar epidemiologia, BI e relatórios.
*   **Anamnese:** Histórico médico e odontológico.
*   **Exames / Visual (Biblioteca):** Consolida radiografias, fotos clínicas, imagens de estomatologia e imagens endodônticas. Exige legenda, data clínica e grupo comparativo quando houver acompanhamento visual.
*   **Plano de Tratamento / Odontograma:** A aba `Plano de Tratamento` registra dente, especialidade, código SUS/SIGTAP e procedimento previsto. O código SUS/SIGTAP é filtrado conforme a especialidade escolhida, cobrindo Atenção Primária/Clínico Geral, Endodontia, Periodontia, Cirurgia Bucomaxilofacial, Prótese Dentária, Alta Complexidade/Hospitalar e Diagnóstico/Estomatologia/Radiologia. Dentes extraídos geram dados de perda dentária para o Mapa Epidemiológico.
*   **Atendimento (Evolução Clínica):** Registro da conduta. Exige assinatura (executor, dentista, paciente). Permite vincular Procedimento SIGTAP. Quando o paciente for não alfabetizado, a confirmação do paciente pode ser registrada como `assinatura a rogo`: o CD responsável autentica com login e senha, declara que leu e explicou o procedimento ao paciente, registra duas testemunhas e o sistema grava hash SHA-256, IP, navegador/dispositivo, data/hora e trilha de auditoria.
*   **🚨 Estomatologia (Câncer de Boca):** Aba visível logo após Atendimento no prontuário.
*   **Materiais (Estoque):** Vinculação do lote utilizado ao procedimento. Implantes geram alerta automático de pós-operatório (7 dias padrão).
*   **Prótese e Endodontia:** Módulos existentes, porém temporariamente ocultos da navegação do prontuário. Sempre informar ao usuário que estão ocultos por decisão operacional temporária, não removidos do sistema. A Endodontia usa a anamnese já existente do prontuário como fonte vinculada; não há nova anamnese separada dentro do módulo. Na ficha endodôntica, o clínico registra apenas dados específicos do dente tratado: queixa/história da dor, exame extraoral/intraoral, periodonto do elemento, diagnóstico pulpar e apical estruturados, odontometria canal a canal com CRD/CRT, localizador apical, justificativa para override de CRT, informações técnicas e sessões endodônticas numeradas em histórico de cartões, com formulário separado para nova sessão. Cada sessão registra etapa realizada, status da sessão, procedimento executado, total planejado, próxima sessão prevista, janela de retorno, status do tratamento, protocolo biomecânico, irrigação, EDTA, medicação intracanal, selamento provisório, obturação final, controle radiográfico e restauração definitiva quando aplicável. A evolução endodôntica só deve avançar após diagnóstico pulpar e apical preenchidos; `Polpa normal` exige justificativa clínica para prosseguir e bloqueia geração de orçamento endodôntico. A ficha bloqueia hipoclorito quando houver alergia compatível, bloqueia material eugenólico quando houver alergia a eugenol e destaca alerta de látex a partir da anamnese vinculada. Retornos endodônticos vencidos aparecem na Central de Comando para ação da recepção/coordenação. Casos obturados sem restauração definitiva continuam em gestão como pendência restauradora. Imagens endodônticas podem ser vinculadas a dente, canal e sessão com categoria clínica, equipamento, data de captura e anotação clínica, ficando disponíveis também na Biblioteca Visual. Após obturação realizada, o sistema planeja proservações de 6, 12 e 24 meses, adicionando 48 meses para lesão periapical extensa; cada retorno pode registrar critérios clínicos/radiográficos de Strindberg e resultado sucesso/dúvida/insucesso. A ficha também gera orçamento gerencial por canal, com complexidade, TUSS/SIGTAP e CID-10 de referência, sem substituir faturamento oficial homologado. O manual rápido de treinamento e aceite está em `docs/manual_rapido_endodontia_e10_2026-06-14.md`.
*   **Detalhes da Estomatologia:**
    *   Ficha especializada (localização, tamanho, risco).
    *   **Alerta Vermelho:** Checkbox "Suspeita de Neoplasia" envia o paciente para a "Fila Vermelha" de regulação.
    *   Encaminhamento expresso em PDF gerado com 1 clique.
    *   Diagnóstico Confirmado: Campo para marcar quando o câncer é comprovado (diferente da suspeita).
*   **Linha do Tempo:** Rastreabilidade completa consolidando consultas, altas, exames, assinaturas e auditoria desde o primeiro acolhimento. Eventos de assinatura mostram se houve assinatura comum ou assinatura a rogo e exibem link para o comprovante consolidado.

### 4.4. Agenda
*   Controle semanal. Criação, edição e cancelamento.
*   **Escopo completo:** Administrador, Recepção e Coordenação veem, criam, editam, cancelam e alteram status de consultas de todos os profissionais.
*   **Escopo clínico:** Clínicos veem, criam, editam, cancelam e alteram status apenas da própria agenda, vinculada ao seu usuário como `dentista_id`.
*   **Sem acesso à Agenda:** CME / Estoque, Radiologia, Comunicação, SSA/SMS e Auditoria não acessam a tela de Agenda.
*   A restrição de escopo da Agenda deve ser aplicada no backend, inclusive nos resumos do Dashboard, Central de Comando e Resumo Operacional Diário. A interface pode esconder filtros e botões, mas isso não substitui a validação por perfil e profissional.
*   **Status "Faltou":** Impacta a inteligência da fila e o mapa epidemiológico (absenteísmo).
*   Eventos da agenda são auditados e aparecem na linha do tempo.

### 4.5. Estoque e Materiais (`/admin/inventory`)
*   Uso no prontuário é opcional para não travar o fluxo clínico.
*   Cadastro de Itens (com estoque mínimo) e Lotes (com validade, quantidade e custo).
*   Ajustes/Perdas: Podem ser feitos administrativamente. Exigem motivo e **senha de confirmação do usuário logado**.
*   Consumo calcula o valor estimado do atendimento (Qtd x Custo do Lote).

### 4.6. Inteligência e BI
Nesta etapa, o BI está em modo de validação do que já existe. Não entram novos painéis, indicadores, filtros, visões executivas ou redesign antes do Go/No-Go de produção.

*   **Mapa Epidemiológico (`/epidemiologia`):**
    *   Filtros: período, bairro, município, sexo, idade, etc.
    *   Indicadores: Perda Dentária, Suspeitas Oncológicas, Câncer Confirmado, Faltas, Demanda Reprimida.
    *   A consolidação por bairro/cidade usa primeiro os campos estruturados do endereço do paciente e mantém fallback para dados legados.
    *   Mapa Georreferenciado: Usa coordenadas municipais. Áreas críticas (Crítico, Atenção, Monitorar) indicam necessidades de mutirão.
*   **BI Executivo (`/bi`):**
    *   Cards executivos de produção, fila e impacto social.
    *   Economia Gerada Estimada (baseada em custos de referência SIGTAP).
    *   **Visões por Perfil:** Geral, Prefeitura, SSA, SMS, Coordenação Clínica e Auditoria. O conteúdo se adapta à visão selecionada.
    *   Geração de PDF Governamental do BI (protegido, assinado com Hash).
*   **Relatórios Institucionais:** PDF automatizado mensalmente via Celery Beat (SSA, SMS, Institucional) ou manual.

### 4.7. Integração SUS e SIGTAP
*   **Catálogo SIGTAP:** Custos importados (TXT/ZIP) ou editados em `/admin/finance/cost-references`. Homologação de valores exige status `validated`.
*   **e-SUS APS (`/admin/integrations/esus`):**
    *   Preparação de lotes mensais (Draft).
    *   Exige preenchimento de campos obrigatórios (CNS paciente, CNS/CBO/CNES/INE do profissional).
    *   Painel mostra pendências antes do fechamento do lote.
    *   Lotes passam por *Validação Interna* e *Pré-envio Simulado* antes de exportar o JSON real para a Prefeitura.

### 4.8. Administração
*   **Usuários:** Cadastro, edição de perfil e gestão do ciclo de vida do acesso.
    *   O botão **Excluir** só deve aparecer e funcionar para usuário sem login, primeiro acesso, recuperação de senha, auditoria ou qualquer vínculo operacional/clínico.
    *   Quando o usuário já tiver acessado ou tiver qualquer histórico vinculado, o caminho correto é **Inativar acesso**, preservando rastreabilidade.
    *   O sistema bloqueia a exclusão no backend mesmo que alguém tente chamar a rota diretamente.
*   **Pré-cadastros (`/admin/professional-registrations`):** Tela de análise das solicitações recebidas pela página pública `/cadastro/`. Cada solicitação aparece em cartão próprio. A administração pode aprovar, criando automaticamente um usuário em primeiro acesso, ou recusar com observação obrigatória no backend. A aprovação envia e-mail de liberação com orientação de primeiro acesso; a recusa envia e-mail com as observações administrativas.
*   **Página pública de cadastro (`/cadastro/`):** Link enviado diretamente pela equipe ao profissional. Não fica exposto na tela de login. Após envio, o profissional vê confirmação com protocolo e aguarda análise administrativa.
*   **Primeiro acesso e senha:** Profissional aprovado entra em `/primeiro-acesso` usando login e data de nascimento, define senha definitiva e confirma o e-mail de recuperação. A tela de login oferece recuperação de senha por e-mail.
*   **Unidades (`/admin/execution-units`):** Cadastro e edição de unidades de execução, com nome, código interno, CNES, endereço, observações, status ativo e unidade padrão.
*   **Regra operacional das unidades:** O sistema permite no máximo 2 unidades ativas. A unidade padrão precisa estar ativa e unidades com agenda vinculada não devem ser desativadas.
*   **Auditoria:** Criação e atualização de unidades geram eventos administrativos rastreáveis.

---

## 5. Alertas e Regras Automáticas Importantes

1.  **Fila Inteligente (Fatores Agravantes):**
    *   Diagnóstico/Suspeita oncológica ativa.
    *   Idade avançada, vulnerabilidade socioeconômica.
    *   Aguardando há muito tempo sem primeira consulta.
2.  **Assinaturas Obrigatórias:** Documentos e evoluções aparecem na Central de Comando e no topo do Prontuário se não assinados. TCLE e confirmação do atendimento aceitam assinatura comum em tela ou, para paciente não alfabetizado, assinatura a rogo com autenticação do CD e duas testemunhas.
3.  **Implantes e Pós-Operatório:** Se um "Implante" é consumido do estoque, um alerta aparecerá na Central de Comando se o pós-operatório (7 dias) não for realizado.
4.  **Estoque Baixo / Vencimento:** Alertas ativos na Central de Comando e na tela de Estoque para lotes vencendo em 30 dias ou estoque global < mínimo.
5.  **Endodontia com retorno vencido:** Casos endodônticos em andamento ou aguardando retorno aparecem como pendência quando a próxima sessão prevista fica anterior à data atual.
6.  **Segurança no protocolo endodôntico:** A anamnese vinculada bloqueia escolhas incompatíveis com alergia a hipoclorito/cloro ou eugenol e sinaliza alergia a látex durante o lançamento da sessão.
7.  **Endodontia sem restauração definitiva:** Casos com status `obturado_aguardando_restauracao` aparecem como pendência clínica até registrar restauração coronária definitiva e selamento adequado.
8.  **Proservação endodôntica vencida:** Retornos planejados de 6, 12, 24 ou 48 meses aparecem na Central quando passam da data prevista sem conclusão.
9.  **Orçamento endodôntico:** A ficha gera estimativa gerencial por canal com TUSS/SIGTAP de referência; `Polpa normal` bloqueia orçamento de tratamento de canal.

---

## 6. Procedimentos de Segurança e Auditoria

*   **Auditoria Plena:** Criação de consultas, edição de pacientes, exclusão de fotos, visualização de exames, ajustes de estoque e login são rastreados (IP, Data, Usuário, Módulo).
*   **Assinatura a rogo:** Usada somente quando o paciente for não alfabetizado. O CD responsável deve ler e explicar o termo ou procedimento em linguagem acessível, esclarecer dúvidas, colher o consentimento verbal do paciente e registrar duas testemunhas. O sistema grava evento probatório com modo `a_rogo`, login do CD, CPF do paciente, hash SHA-256 do conteúdo, IP, user-agent, timestamp e auditoria.
*   **Pacote probatório de assinatura:** TCLE, confirmação do atendimento, Anamnese, Prótese, Pagamentos e Endodontia geram evento técnico em `signature_events` e registro em `digital_signatures` quando há assinatura. O comprovante consolidado fica disponível pela Linha do Tempo ou por `/documents/signatures/<event_id>`.
*   **LGPD:** Visualização de imagens só carrega se logado. Relatórios e eventos probatórios de assinatura geram Hash (SHA-256) para demonstrar integridade do conteúdo registrado.
*   **Dados de Treinamento/Demonstração:** Os pacientes gerados por CLI para demonstração possuem `is_demo=TRUE` e não se misturam com integrações reais.

---

> ⚠️ **CHECKLIST PARA O DESENVOLVEDOR (MANUTENÇÃO DESTE ARQUIVO):**
> 1. Quando criar novo Perfil ou alterar permissão de módulo, atualize a seção 2.
> 2. Quando mudar lógica de Fila Inteligente ou adicionar Novo Alerta, atualize as seções 4.1 e 5.
> 3. Quando criar ou alterar abas do Prontuário, atualize a seção 4.3.
> 4. Quando adicionar novas rotas de Inteligência (BI, Reports, Epidemiologia), atualize a seção 4.6.
> 5. Quando alterar regras de integração e-SUS / SIGTAP / Dados obrigatórios, atualize as seções 4.7.
> 6. Quando alterar o Resumo Operacional Diário, atualize a seção 4.1 e os manuais da Coordenação.
> 7. Quando alterar critérios das Metas Operacionais Automáticas, atualize a seção 4.1 e os exemplos dos manuais da Coordenação.
> 8. Quando alterar nomes ou regras das Unidades de Execução, atualize as seções 4.1 e 4.8 e os manuais de Administração, Agenda, Triagem e Coordenação.
> 9. Quando alterar assinatura de TCLE, atendimento ou assinatura a rogo, atualize as seções 4.3, 5 e 6 e revise o treinamento de Clínicos e Recepção.
> 10. Quando alterar pré-cadastro, primeiro acesso, recuperação de senha ou e-mails transacionais, atualize a seção 4.8 e o manual de Administração.
