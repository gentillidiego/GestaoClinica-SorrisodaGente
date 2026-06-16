# Backup e Restauração - 08/06/2026

Documento de evidência técnica da etapa de backup e restauração do sistema Gestão Saúde Oral / Programa Sorriso da Gente.

## Resultado Executivo

Status: aprovado após correção operacional.

Foi identificado que o backup gerado pelo container da aplicação usava `pg_dump` 17 contra um banco PostgreSQL 16. Esse dump era criado, mas falhava ao restaurar em PostgreSQL 16 por conter configuração incompatível.

A correção foi criar um fluxo Docker de backup e restore usando `postgres:16-alpine`, compatível com o banco atual do projeto.

## Problema Encontrado

Comando antigo:

```bash
docker compose exec -T gestaoclinica python scripts/backup_postgres.py
```

Problema observado no restore:

```text
ERROR: unrecognized configuration parameter "transaction_timeout"
```

Causa:

- O serviço do banco usa PostgreSQL 16.
- O container da aplicação possuía cliente `pg_dump` 17.
- O dump criado pelo cliente 17 incluía instrução incompatível com PostgreSQL 16.

## Correções Aplicadas

Arquivos criados:

- `scripts/docker_backup_postgres.sh`
- `scripts/docker_restore_verify.sh`

Arquivo ajustado:

- `scripts/backup_postgres.py`

O script Python antigo agora valida a compatibilidade entre versão principal do `pg_dump` e versão principal do servidor antes de criar o backup.

O fluxo recomendado passou a ser:

```bash
scripts/docker_backup_postgres.sh
scripts/docker_restore_verify.sh
```

## Evidência de Backup

Backup compatível gerado:

```text
gestao_saude_oral_20260608_082856.dump
uploads_20260608_082856.tar.gz
```

O backup foi criado no volume Docker:

```text
gestaosaudeoral_backups_oral
```

## Evidência de Restore

Restore validado em container PostgreSQL temporário, separado do banco principal.

Resultado:

```text
Restore validado com sucesso: gestao_saude_oral_20260608_082856.dump
Tabelas públicas restauradas: 46
Pacientes restaurados: 100
```

O container temporário foi removido ao final da validação.

## Limpeza Realizada

Foram removidos apenas os backups incompatíveis gerados durante esta etapa de teste:

- `gestao_saude_oral_20260608_112559.dump`
- `uploads_20260608_112559.tar.gz`
- `gestao_saude_oral_20260608_112926.dump`
- `uploads_20260608_112926.tar.gz`

## Comandos Operacionais

Gerar backup:

```bash
scripts/docker_backup_postgres.sh
```

Validar restore do backup mais recente:

```bash
scripts/docker_restore_verify.sh
```

Validar restore de um arquivo específico:

```bash
scripts/docker_restore_verify.sh gestao_saude_oral_YYYYMMDD_HHMMSS.dump
```

## Recomendações

- Executar backup diário automatizado antes da produção.
- Agendar restore de verificação periódico.
- Definir retenção local e retenção externa.
- Replicar backups fora do servidor principal.
- Registrar evidência de restore antes da implantação.
- Não considerar backup válido sem restore testado.

## Conclusão

A etapa de backup e restauração está aprovada para o estágio atual. O projeto agora possui geração de backup compatível com PostgreSQL 16 e verificação automatizada de restauração em banco temporário.

Próxima etapa sugerida: Hardening LGPD.
