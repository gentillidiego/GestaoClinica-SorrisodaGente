# Auditoria Administrativa - 08/06/2026

Documento de evidência técnica da melhoria de auditoria administrativa do sistema Gestão Saúde Oral / Programa Sorriso da Gente.

## Resultado Executivo

Status: aprovado.

A tela de auditoria recebeu filtros adicionais para facilitar investigação operacional, segurança e LGPD.

## Escopo Executado

- Filtro por período inicial e final.
- Filtro por IP.
- Filtro por severidade.
- Coluna visual de severidade na tabela de auditoria.
- Classificação automática de severidade sem migração de banco.
- Testes automatizados para a consulta de auditoria.

## Arquivos Ajustados

- `services/security_service.py`
- `blueprints/admin.py`
- `templates/admin/audit_logs.html`
- `tests/test_phase1_security.py`

## Regra de Severidade

Alta:

- Eventos com `status` igual a `denied` ou `failed`.

Média:

- Ações sensíveis como exclusão, bloqueio, download, exportação, assinatura ou eventos dos módulos `auth` e `security`.

Baixa:

- Demais eventos operacionais comuns.

## Validação Técnica

Testes automatizados:

```text
114 passed
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
/admin/audit: 200
/admin/audit?created_from=2026-06-01&created_to=2026-06-08&severity=alta: 200
/admin/audit?ip_address=172.&status=success: 200
```

## Achado Corrigido Durante a Validação

A primeira versão da consulta de severidade usava `%` em expressões `ILIKE` sem escape. O driver PostgreSQL interpretou esses sinais como placeholders e a tela retornou HTTP 500.

Correção aplicada:

- Escapados os `%` da expressão SQL calculada.
- Adicionado teste para garantir que a consulta mantenha o padrão correto.

## Pendências Relacionadas

- Auditoria plena de visualização sensível em todos os documentos clínicos específicos.
- Rotina formal de revisão de logs.
- Exportação controlada de auditoria, se a gestão solicitar.
- Política institucional de retenção dos logs.

## Conclusão

A auditoria administrativa agora permite investigação por período, IP, status, severidade, módulo, ação, usuário e paciente. A pendência de filtro por período, IP e severidade foi concluída.

Próxima etapa sugerida: Preparação e-SUS/SIGTAP.
