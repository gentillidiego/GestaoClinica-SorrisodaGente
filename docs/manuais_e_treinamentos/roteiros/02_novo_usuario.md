# Roteiro 02 — Novo usuário

Status: **pronto para validar**  
Versão de referência: **4.0.0-rc.1**  
Público: **Administrador**  
Duração estimada: **6 minutos**

## Objetivo

Cadastrar um usuário, escolher corretamente seu perfil e encaminhá-lo ao
primeiro acesso.

## Preparação

- sessão de Administrador;
- dados totalmente fictícios;
- CNS e CBO fictícios para perfil profissional;
- CRO e UF fictícios se o exemplo for do perfil Clínicos.

## Sequência

### 1. Abrir a gestão da equipe

**Narração:** “No menu Administração, abra Usuários. Esta tela apresenta os
acessos ativos, inativos, pendentes de primeiro acesso e o último login.”

**Tela:** Abrir `Usuários` e selecionar `Novo Usuário`.

### 2. Preencher a identificação

**Narração:** “Informe nome completo, login, e-mail, celular e data de
nascimento. O login precisa ser único. A data de nascimento será usada para
validar o primeiro acesso.”

**Tela:** Preencher os campos.

### 3. Escolher o fluxo de acesso

**Narração:** “Para novos profissionais, mantenha Primeiro acesso pendente.
Assim, a pessoa define sua própria senha. A opção de senha definida agora deve
ser usada somente quando houver uma necessidade administrativa específica.”

**Tela:** Manter `Primeiro acesso pendente`.

### 4. Definir perfil e dados profissionais

**Narração:** “Escolha o perfil de acordo com a função real do usuário. O perfil
determina os menus e operações disponíveis. Para Clínicos, CME e Radiologia, o
sistema solicita dados profissionais. Para Clínicos, também são obrigatórios
CRO e CRO-UF.”

**Tela:** Selecionar um perfil e demonstrar os campos condicionais.

### 5. Salvar e conferir

**Narração:** “Mantenha o acesso ativo e clique em Criar Usuário. Depois,
confira se o nome aparece na lista com a indicação Primeiro acesso pendente.”

**Tela:** Salvar e localizar o novo registro.

### 6. Explicar edição, inativação e exclusão

**Narração:** “Usuários sem qualquer histórico podem ser excluídos. Depois do
primeiro acesso ou de qualquer vínculo operacional, use Inativar acesso. Essa
regra preserva a rastreabilidade dos atos realizados.”

**Tela:** Destacar `Editar`, `Inativar acesso` ou `Excluir`, conforme o cenário.

## Resultado esperado

Usuário ativo, com perfil correto e primeiro acesso pendente.

## Checklist da gravação

- [ ] explicar cada perfil apenas no nível necessário;
- [ ] demonstrar campos profissionais;
- [ ] não criar senha visível;
- [ ] mostrar o registro na lista;
- [ ] explicar inativação versus exclusão.
