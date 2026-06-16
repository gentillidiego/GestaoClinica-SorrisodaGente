# QA Técnico - 08/06/2026

Documento de evidência técnica do estado atual do sistema Gestão Saúde Oral / Programa Sorriso da Gente.

Este QA foi executado enquanto os manuais aguardam validação conceitual da Contratante. O objetivo foi verificar saúde técnica, testes automatizados, Docker, rotas críticas e pontos de atenção que não dependem de aprovação de fluxo.

## Resultado Executivo

Status: aprovado com observações.

O sistema passou nos testes automatizados, respondeu saudável no Docker e abriu as rotas críticas autenticadas com HTTP 200 dentro do container.

## Comandos Executados

```bash
.venv/bin/pytest -q
git diff --check
docker compose ps
curl http://localhost:5003/health
docker compose logs --tail=1200 gestaoclinica
docker compose exec -T gestaoclinica flask --app app:app routes
```

## Evidências

- Testes automatizados: `112 passed`.
- `git diff --check`: sem erros.
- `/health`: `status=healthy`, `database=ok`.
- Docker: web, PostgreSQL, Redis, Celery Worker e Celery Beat em execução.
- PostgreSQL e Redis: containers saudáveis.
- Logs recentes avaliados: sem `ERROR`, `Traceback` ou HTTP 500 nas últimas linhas analisadas.

## Rotas Públicas Validadas

| Rota | Resultado |
|---|---|
| `/` | HTTP 200 |
| `/login` | HTTP 200 |
| `/health` | HTTP 200 |

## Rotas Protegidas Validadas sem Sessão

As rotas protegidas redirecionaram corretamente para login quando acessadas sem autenticação.

| Rota | Resultado esperado |
|---|---|
| `/dashboard` | HTTP 302 para login |
| `/triagem/` | HTTP 302 para login |
| `/triagem/senhas` | HTTP 302 para login |
| `/agenda/` | HTTP 302 para login |
| `/command-center` | HTTP 302 para login |
| `/epidemiologia` | HTTP 302 para login |
| `/bi` | HTTP 302 para login |
| `/reports/institutional` | HTTP 302 para login |
| `/admin/inventory` | HTTP 302 para login |
| `/admin/execution-units` | HTTP 302 para login |
| `/admin/finance/cost-references` | HTTP 302 para login |
| `/admin/integrations/esus` | HTTP 302 para login |
| `/admin/audit` | HTTP 302 para login |

## Rotas Autenticadas Validadas no Container

Validação executada com sessão de teste autenticada via `Flask test_client`, sem alteração de dados operacionais.

| Rota | Resultado |
|---|---|
| `/dashboard` | HTTP 200 |
| `/triagem/` | HTTP 200 |
| `/triagem/acoes/nova` | HTTP 200 |
| `/triagem/senhas` | HTTP 200 |
| `/agenda/` | HTTP 200 |
| `/command-center` | HTTP 200 |
| `/command-center/daily-summary` | HTTP 200 |
| `/patients/list` | HTTP 200 |
| `/patients/register` | HTTP 200 |
| `/patients/red-alerts` | HTTP 200 |
| `/epidemiologia` | HTTP 200 |
| `/bi` | HTTP 200 |
| `/reports/institutional` | HTTP 200 |
| `/admin/inventory` | HTTP 200 |
| `/admin/execution-units` | HTTP 200 |
| `/admin/finance/cost-references` | HTTP 200 |
| `/admin/integrations/esus` | HTTP 200 |
| `/admin/audit` | HTTP 200 |

## Achados

1. A rota de referência de pacientes no README estava como `/patients`, mas a rota real é `/patients/list`.
   - Ação tomada: README corrigido.

2. Os logs mostram tentativas externas de acesso a caminhos comuns de scanner, como `.env`, WordPress e endpoints inexistentes.
   - Resultado atual: respostas HTTP 404, sem erro de aplicação.
   - Recomendação: tratar como ponto de hardening de produção, com revisão de exposição pública, Nginx, rate limit, bloqueio de padrões e monitoramento.

3. A venv local não conseguiu importar `redis` ao tentar abrir o app diretamente fora do container.
   - Impacto atual: baixo para operação Docker e testes automatizados executados.
   - Recomendação: revisar dependências locais em etapa técnica posterior, se o desenvolvimento local fora do Docker continuar sendo usado.

## Conclusão

A etapa de QA técnico básico está aprovada. Não foram encontrados erros de servidor, falhas de teste ou rotas críticas quebradas no ambiente Docker.

Próxima etapa sugerida: Backup e restauração.
