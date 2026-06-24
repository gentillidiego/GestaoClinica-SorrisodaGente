# Roteiro 08 — Plano de tratamento e evolução clínica

Status: **pronto para validar**  
Versão de referência: **4.0.0-rc.1**  
Público: **Clínicos**  
Duração estimada: **9 minutos**

## Objetivo

Planejar um procedimento, associar código SUS/SIGTAP, validar o plano e
registrar a evolução do atendimento.

## Preparação

- paciente fictício com TCLE e anamnese;
- procedimento e código SIGTAP de demonstração;
- credenciais fictícias do executor e dentista responsável.

## Sequência

### 1. Criar o plano

**Narração:** “Na aba Plano de Tratamento, informe o dente, escolha a
especialidade e selecione o código SUS ou SIGTAP correspondente. O catálogo é
filtrado pela especialidade.”

**Tela:** Preencher dente, especialidade, código e descrição.

**Narração:** “Revise a descrição e clique em Adicionar.”

### 2. Editar ou excluir antes da conclusão

**Narração:** “Enquanto o procedimento estiver pendente, use Editar para
corrigir os dados ou Excluir quando o item tiver sido lançado indevidamente.”

**Tela:** Destacar os botões.

### 3. Validar o procedimento

**Narração:** “Ao concluir o procedimento, clique em Assinar. O dentista
responsável confirma suas credenciais. O item passa para Concluído e é
importado para a evolução clínica.”

**Tela:** Abrir o modal, ocultar a senha e confirmar.

### 4. Registrar uma evolução

**Narração:** “Na aba Atendimento, registre a data e descreva a conduta,
intercorrências, orientações e resultado do atendimento. Use linguagem
objetiva e suficiente para a continuidade do cuidado.”

**Tela:** Preencher e salvar uma evolução fictícia.

### 5. Confirmar executor, paciente e responsável

**Narração:** “A evolução possui três confirmações: profissional executor,
paciente e dentista responsável. O executor e o responsável autenticam suas
credenciais. O paciente assina no quadro ou, quando não alfabetizado, utiliza
o fluxo de assinatura a rogo.”

**Tela:** Demonstrar os três controles sem exibir senhas.

### 6. Conferir a conclusão

**Narração:** “Quando todas as confirmações estão registradas, a evolução fica
completa e rastreável. Os eventos também aparecem na Linha do Tempo.”

**Tela:** Mostrar a linha concluída e abrir a Linha do Tempo.

## Resultado esperado

Procedimento concluído, evolução registrada e confirmações vinculadas.

## Checklist da gravação

- [ ] selecionar especialidade antes do SIGTAP;
- [ ] mostrar procedimento pendente;
- [ ] validar com senha oculta;
- [ ] registrar evolução;
- [ ] explicar as três confirmações;
- [ ] mostrar Linha do Tempo.
