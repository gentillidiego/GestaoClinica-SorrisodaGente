# Manual 04 — Triagem

Status: **modelo para validação**  
Versão de referência: **4.0.0-rc.1**  
Público: **Recepção**  
Revisão: **22/06/2026**

## Objetivo

Orientar a criação de uma ação municipal de triagem, a localização do paciente
já cadastrado e a geração de uma senha vinculada à especialidade da demanda.

## Antes de começar

- confirme que o paciente já possui cadastro;
- confirme o município e a data da ação;
- identifique a especialidade correspondente à demanda;
- utilize uma sessão com permissão de Triagem;
- não escolha unidade de atendimento nesta etapa.

## Passo 1 — Criar a ação

Abra **Triagem**, clique em **Nova Ação** e informe município, data, local e
observações operacionais. A ação representa a origem municipal da demanda.

## Passo 2 — Localizar o paciente

Dentro da ação, pesquise por nome, CPF ou CNS. Confira o cadastro correto antes
de selecionar o paciente.

## Passo 3 — Gerar e vincular a senha

Escolha a especialidade e clique em **Gerar e Vincular**. O sistema cria o
código automaticamente e associa a senha ao prontuário.

Quando houver mais de uma demanda, repita o processo para cada especialidade.
O paciente pode possuir várias senhas.

## Passo 4 — Consultar as senhas

Abra **Senhas** e utilize os filtros de código, município, especialidade e
status. Senhas vinculadas ao paciente não podem ter o status alterado
manualmente.

## Regra da unidade de atendimento

A Triagem registra município, paciente e especialidade. A unidade onde o
atendimento ocorrerá será escolhida posteriormente, durante o agendamento.

## Problemas comuns

- **Paciente não encontrado:** cadastre-o antes de gerar a senha.
- **Especialidade incorreta:** não gere a senha antes de confirmar a demanda.
- **Demanda adicional:** gere uma nova senha para a outra especialidade.
- **Status bloqueado:** senhas vinculadas não são alteradas manualmente.
- **Unidade ainda ausente:** defina-a depois, na Agenda.

## Resultado esperado

Senha vinculada ao paciente e à especialidade, disponível para organização da
fila e posterior agendamento.
