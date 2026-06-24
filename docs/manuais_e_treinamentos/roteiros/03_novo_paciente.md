# Roteiro 03 — Novo paciente

Status: **pronto para validar**  
Versão de referência: **4.0.0-rc.1**  
Público: **Recepção e Clínicos autorizados**  
Duração estimada: **6 minutos**

## Objetivo

Cadastrar corretamente um paciente, incluindo CPF, CNS e endereço estruturado.

## Preparação

- paciente inteiramente fictício;
- CPF e CNS válidos para demonstração;
- CEP de teste;
- confirmar previamente que o paciente não está cadastrado.

## Sequência

### 1. Pesquisar antes de cadastrar

**Narração:** “Antes de criar um cadastro, pesquise em Pacientes e Prontuários
por nome, CPF ou CNS. Isso evita prontuários duplicados.”

**Tela:** Fazer uma busca sem resultado e abrir `Novo Paciente`.

### 2. Preencher identificação

**Narração:** “Informe CNS, nome completo e CPF. CPF e CNS são essenciais para
as integrações do SUS. Complete nascimento, gênero, contato e os demais dados
disponíveis.”

**Tela:** Preencher a identificação fictícia.

### 3. Preencher endereço

**Narração:** “No endereço residencial, comece pelo CEP. Quando localizado, o
sistema preenche logradouro, bairro, cidade e estado. Revise as informações e
complete o número e o complemento.”

**Tela:** Informar o CEP e completar o endereço.

**Narração:** “Se o CEP não for encontrado, selecione estado, cidade e bairro e
preencha o endereço manualmente.”

### 4. Informar responsável quando necessário

**Narração:** “Para menores de idade ou pacientes que dependam de responsável,
preencha também a identificação e o contato do responsável.”

**Tela:** Destacar a seção sem usar dados reais.

### 5. Salvar e conferir

**Narração:** “Clique em Efetuar cadastro. O sistema cria o prontuário. A senha
de triagem não é informada nesta tela; ela será vinculada depois, dentro da
ação de triagem.”

**Tela:** Salvar e mostrar o prontuário criado.

## Resultado esperado

Paciente único, identificado e disponível para triagem, agenda e prontuário.

## Checklist da gravação

- [ ] pesquisar duplicidade;
- [ ] explicar CPF e CNS;
- [ ] demonstrar endereço por CEP;
- [ ] mencionar preenchimento manual;
- [ ] explicar que a senha pertence à Triagem;
- [ ] mostrar o prontuário final.
