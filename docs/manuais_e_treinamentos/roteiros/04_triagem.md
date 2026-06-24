# Roteiro 04 — Triagem

Status: **pronto para validar**  
Versão de referência: **4.0.0-rc.1**  
Público: **Recepção**  
Duração estimada: **7 minutos**

## Objetivo

Criar uma ação de triagem e gerar uma senha vinculada a paciente e
especialidade.

## Preparação

- paciente fictício já cadastrado;
- município e especialidade ativos;
- sessão de Recepção ou Administrador.

## Sequência

### 1. Explicar a ordem correta

**Narração:** “O paciente precisa estar cadastrado antes da triagem. A triagem
registra a demanda identificada no município; a unidade de atendimento será
definida posteriormente, na Agenda.”

**Tela:** Abrir o menu `Triagem`.

### 2. Criar a ação

**Narração:** “Clique em Nova Ação. Selecione o município, informe a data, o
local da ação e, se necessário, observações sobre equipe ou logística.”

**Tela:** Preencher e salvar a ação.

### 3. Localizar o paciente

**Narração:** “Dentro da ação, pesquise o paciente por nome, CPF ou CNS.
Selecione o cadastro correto conferindo os dados exibidos.”

**Tela:** Pesquisar e selecionar o paciente fictício.

### 4. Gerar e vincular a senha

**Narração:** “Escolha a especialidade correspondente à demanda e clique em
Gerar e Vincular. O sistema cria automaticamente o código da senha e o associa
ao prontuário.”

**Tela:** Selecionar especialidade, gerar e mostrar a confirmação.

### 5. Explicar múltiplas demandas

**Narração:** “Quando o paciente tiver mais de uma demanda, repita o processo
para cada especialidade. O mesmo paciente pode possuir várias senhas, e todas
ficam visíveis no prontuário.”

### 6. Consultar senhas

**Narração:** “Na tela Senhas, use os filtros de código, município,
especialidade e status. Senhas já vinculadas ao paciente não devem ter seu
status alterado manualmente.”

**Tela:** Abrir `Senhas` e demonstrar os filtros.

## Resultado esperado

Senha vinculada ao paciente e disponível para organização da fila e agenda.

## Checklist da gravação

- [ ] paciente já cadastrado;
- [ ] criar ação;
- [ ] localizar paciente;
- [ ] selecionar especialidade;
- [ ] mostrar código gerado;
- [ ] explicar múltiplas demandas;
- [ ] reforçar que a unidade é definida na Agenda.
