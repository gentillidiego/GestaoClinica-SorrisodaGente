# Roteiro 05 — Agenda

Status: **pronto para validar**  
Versão de referência: **4.0.0-rc.1**  
Público: **Recepção, Coordenação e Clínicos**  
Duração estimada: **7 minutos**

## Objetivo

Agendar, confirmar, remanejar, concluir, registrar falta e cancelar consultas.

## Preparação

- paciente fictício cadastrado;
- profissional clínico ativo;
- unidade de execução ativa;
- horário fictício disponível.

## Sequência

### 1. Apresentar os escopos

**Narração:** “Recepção, Coordenação e Administrador visualizam a agenda de
todos os profissionais. O perfil Clínicos visualiza e administra somente a
própria agenda.”

**Tela:** Abrir `Agenda` e mostrar semana, filtros e status.

### 2. Criar uma consulta

**Narração:** “Clique em Nova Consulta. Selecione paciente, profissional, data,
hora, duração e unidade de execução. A unidade é definida aqui, e não durante
a triagem.”

**Tela:** Preencher o modal e salvar.

### 3. Conferir e filtrar

**Narração:** “A consulta aparece na semana correspondente. Use os filtros de
profissional, status e unidade, além das setas para mudar de semana.”

**Tela:** Demonstrar filtros e navegação.

### 4. Atualizar o status

**Narração:** “Use Confirmar quando o comparecimento estiver confirmado.
Depois do atendimento, marque Realizado. Se o paciente não comparecer,
registre Faltou, porque essa informação alimenta a fila e os indicadores.”

**Tela:** Demonstrar os botões sem alterar vários registros desnecessariamente.

### 5. Editar, remanejar ou cancelar

**Narração:** “Para alterar horário, duração, unidade ou profissional, clique em
Editar. Para desistências ou impedimentos, use Cancelar. Não use Faltou quando
a consulta foi cancelada previamente.”

**Tela:** Abrir a edição e mostrar os campos.

## Resultado esperado

Consulta registrada na unidade correta e com status operacional atualizado.

## Checklist da gravação

- [ ] explicar escopo do perfil Clínicos;
- [ ] criar consulta;
- [ ] definir unidade;
- [ ] mostrar filtros;
- [ ] explicar todos os status;
- [ ] diferenciar Faltou de Cancelado.
