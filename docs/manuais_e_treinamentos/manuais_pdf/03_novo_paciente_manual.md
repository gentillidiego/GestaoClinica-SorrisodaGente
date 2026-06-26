# Manual 03 — Novo paciente

Status: **modelo para validação**  
Versão de referência: **4.0.0-rc.1**  
Público: **Recepção e Clínicos autorizados**  
Revisão: **22/06/2026**

## Objetivo

Orientar o cadastro seguro de um paciente, com pesquisa prévia de duplicidade,
identificação SUS, endereço estruturado e responsável legal quando necessário.

## Antes de começar

- pesquise o paciente por nome, CPF e CNS;
- confirme CPF, CNS, nascimento e contato;
- tenha o CEP e o número do endereço;
- identifique o responsável legal quando aplicável;
- utilize dados conferidos diretamente com o paciente.

## Passo 1 — Pesquisar antes de cadastrar

Abra **Pacientes / Prontuários** e pesquise por nome, CPF ou CNS. Somente
prossiga para **Novo Cadastro** quando tiver certeza de que não existe outro
prontuário para a mesma pessoa.

## Passo 2 — Preencher a identificação

Informe CNS, nome completo e CPF. Complete RG, profissão, gênero, nascimento,
nacionalidade, celular, e-mail, estado civil e unidade de atendimento.

CPF e CNS são obrigatórios e apoiam identificação e integrações do SUS.

## Passo 3 — Preencher o endereço

Comece pelo CEP. Quando localizado, o sistema preenche rua, bairro, cidade,
estado e código IBGE. Revise os dados e informe o número.

Se o CEP não for localizado, selecione estado, cidade e bairro e complete o
endereço manualmente.

## Passo 4 — Informar responsável legal

Para criança, adolescente ou paciente que dependa de responsável, registre
nome, RG e e-mail do responsável legal.

## Passo 5 — Salvar e conferir

Clique em **Efetuar cadastro** e confira a identificação no prontuário.
O cadastro nasce **sem triagem**: a senha será criada e vinculada depois, na
ação de Triagem.

## Problemas comuns

- **Paciente já cadastrado:** utilize o prontuário existente.
- **CPF inválido:** confira os onze dígitos.
- **CNS ausente:** confirme o Cartão Nacional de Saúde.
- **CEP não localizado:** preencha o endereço manualmente.
- **Paciente sem senha:** faça o vínculo dentro da ação de Triagem.

## Resultado esperado

Paciente único, corretamente identificado, com endereço estruturado e
disponível para triagem, agenda e prontuário.
