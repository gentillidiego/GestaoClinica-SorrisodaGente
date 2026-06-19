# e-SUS APS — Envelope XML LEDI — 18/06/2026

## Resultado

A integração foi corrigida para gerar o envelope oficial `dadoTransporteTransportXml`
contendo a Ficha de Atendimento Odontológico.

## Regras implementadas

- Consulta baseada nas colunas reais `patients.genero` e `tratamento_procedimentos.data_sessao`.
- Procedimentos agrupados por paciente e data clínica.
- Um arquivo por período e profissional.
- Elementos oficiais `coMsProcedimento` e `lotacaoFormPrincipal`.
- Envelope com município IBGE, CNES, INE, lote, remetente, originadora e versão LEDI.
- Validação do envelope por `dadotransporte.xsd` e validação explícita da ficha por
  `fichaatendimentoodontologicomaster.xsd`; isso evita que o `xs:any` em modo
  `lax` do envelope aceite uma ficha interna inválida.
- XML inválido não é gravado no disco nem registrado no banco.
- O arquivo é validado novamente e tem o SHA-256 conferido antes do envio.
- Índice único de idempotência para `período inicial + período final + profissional`.
- Procedimentos vinculados à remessa recebem estado `generated` e, após envio, `sent`.

## Testes

- Fixture golden: `tests/fixtures/esus/atendimento_odontologico_golden.xml`.
- Testes específicos: `tests/test_phase3_sigtap_esus.py`.
- A fixture usa UUID e lote determinísticos e é comparada em XML canônico.

## Pendência externa

Antes de ativar `ESUS_REMESSA_ATIVA`, o TI municipal deve fornecer e confirmar:

- CNES e INE;
- código IBGE do município;
- contra-chave e UUID da instalação;
- CPF/CNPJ e nome/razão social da instalação;
- versão LEDI aceita pelo PEC;
- e-mail operacional de destino.

O primeiro arquivo deve ser importado de forma assistida no PEC municipal. A validação
XSD local comprova estrutura, mas não substitui o aceite do ambiente da Secretaria.
