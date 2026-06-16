# Preparação e-SUS/SIGTAP - 08/06/2026

Documento de evidência técnica da etapa de preparação SIGTAP/e-SUS APS do sistema Gestão Saúde Oral / Programa Sorriso da Gente.

## Resultado Executivo

Status: aprovado para preparação local.

A transmissão real continua desativada e dependente da prefeitura. A melhoria desta etapa fortalece a validação interna antes da homologação, impedindo que registros com identificadores em formato inválido sejam tratados como prontos para lote.

## Escopo Executado

- Validação de formato de CNS/CPF do paciente.
- Validação de CNS profissional.
- Validação de CBO.
- Validação de CNES.
- Validação de INE/equipe.
- Validação de CRO-UF.
- Contagem de pacientes com CNS/CPF inválido no painel de homologação.
- Bloqueio de prontidão quando CNES/INE de configuração têm tamanho inválido.
- Download JSON de lote e-SUS protegido com cabeçalhos de arquivo sensível.

## Arquivos Ajustados

- `services/esus_export_service.py`
- `blueprints/admin.py`
- `tests/test_phase3_sigtap_esus.py`

## Regras de Formato Aplicadas

| Campo | Regra |
|---|---|
| CNS paciente | 15 dígitos |
| CPF paciente | 11 dígitos |
| CNS profissional | 15 dígitos |
| CBO | 6 dígitos |
| CNES | 7 dígitos |
| INE/equipe | 10 dígitos |
| CRO-UF | 2 letras |

Para o paciente, o sistema considera pronto quando há ao menos um identificador válido: CNS ou CPF.

## Validação Técnica

Testes automatizados:

```text
116 passed
```

Checagem de diff:

```text
git diff --check: sem erros
```

Docker:

```text
docker compose up -d --build: concluído
/health: status=healthy, database=ok
```

Rotas validadas no container:

```text
/admin/integrations/esus: 200
/admin/integrations/esus?month=2026-06: 200
/admin/integrations/esus/homologation-report?month=2026-06: 200
```

Dashboard e-SUS validado no container:

```text
patients_total: 100
missing_cns_or_cpf: 0
invalid_cns_or_cpf: 0
homologation_ready: false
blocking_count: 8
```

## O Que Continua Dependendo da Prefeitura

- Endpoint PEC/e-SUS.
- Tipo de autenticação.
- Credenciais.
- CNES/INE oficiais.
- Versão PEC/e-SUS APS.
- Compatibilidade LEDI.
- Ambiente de homologação ou produção.
- Regras municipais de transmissão real.

## Conclusão

A preparação local SIGTAP/e-SUS foi reforçada. O sistema identifica campos ausentes e, agora, também bloqueia formatos inválidos antes de considerar registros prontos para lote.

Próxima etapa sugerida: aguardar validação da Contratante para retomar manuais ou avançar em pendências de produção específicas.
