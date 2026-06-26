# Auditoria Go/No-Go — Gestão Saúde Oral

Data: 21/06/2026

Janela técnica: 09h03–09h10, `America/Maceio`

Branch avaliada: `main`

Commit-base: `493ff73`

Decisão: **NO-GO para produção plena**

## Resumo executivo

A candidata atual passou nos critérios técnicos de teste, dependências,
rebuild, saúde, portas, OAuth, backup e restauração. A base operacional
permaneceu no baseline esperado, sem pacientes e com dois usuários
administrativos.

A release não foi aprovada porque `P0-REL-01` exige todos os P0 anteriores
concluídos e ainda existem três bloqueadores:

1. o token temporário da API Hostinger ainda precisa ser revogado no hPanel e
   removido da VPS (`P0-INF-06`);
2. 2FA, recuperação institucional, custodiantes e revisão de sessões/apps da
   conta Google ainda precisam de confirmação humana (`P0-GDRIVE-02`);
3. a política de governança precisa do aceite formal da Dra. Cibely e da
   indicação do responsável clínico/jurídico (`P0-GOV-01`).

Por consequência, não foi criada uma tag de produção aprovada. Uma versão
candidata pode ser publicada para revisão técnica, desde que identificada como
pré-release e sem alterar a decisão **NO-GO**.

## Testes

- `.venv/bin/pytest -q`: `285 passed in 44.82s`.
- Suíte na imagem reconstruída, usando PostgreSQL temporário isolado:
  `285 passed in 7.50s`.
- `git diff --check`: aprovado.
- `docker compose config --quiet`: aprovado.

Na primeira tentativa de executar a suíte dentro do contêiner, a configuração
herdada apontava para a rede operacional. Duas gravações de auditoria com IDs
sintéticos foram rejeitadas pelo PostgreSQL por chave estrangeira; não houve
alteração clínica. A execução foi repetida com banco temporário isolado e
passou integralmente. Testes de release não devem voltar a usar a URL do banco
operacional.

Baseline confirmado após os testes:

```text
patients=0
users=2
attendances=0
audit_logs=3
```

## Dependências

Auditorias com `pip-audit 2.10.1`:

- pins diretos de `requirements.txt`: nenhuma vulnerabilidade conhecida;
- resolução direta e transitiva no Python 3.11: nenhuma vulnerabilidade
  conhecida;
- ambiente instalado na imagem: nenhuma vulnerabilidade conhecida;
- `python -m pip check`: nenhuma dependência quebrada.

Uma tentativa inicial da resolução transitiva no Python 3.13 falhou ao compilar
`gevent==24.2.1`. Ela foi descartada porque o `Dockerfile` da produção usa
Python 3.11; a auditoria foi repetida no runtime correto e aprovada.

## Rebuild e saúde

Comando:

```bash
docker compose up -d --build
```

Imagem web avaliada:

```text
sha256:99cebeebd3fc94e7f163cf2f401eb1dae4c0fceffac19cc22ddb0df9c0c5eea5
```

Resultados:

- web, PostgreSQL, Redis, Celery worker, Celery beat, mail e backup ativos;
- PostgreSQL, Redis e backup saudáveis;
- `/health` local: `status=healthy`, `database=ok`;
- `/health` HTTPS: `status=healthy`, `database=ok`;
- Celery: `pong`, um nó online;
- login público: HTTP `200`;
- rotas administrativas e clínicas sem sessão: HTTP `302`;
- tentativa de acesso a `/uploads/arquivo-inexistente.jpg` e `/.env`: HTTP
  `404`;
- logs posteriores à execução isolada sem `Traceback`, `CRITICAL`, `ERROR`,
  `FATAL` ou `panic`.

## Portas e firewall

Verificação TCP no IPv4 `72.60.248.85` e no IPv6
`2a02:4780:66:8599::1`:

- abertas: `22`, `80`, `443`;
- fechadas: `3025`, `3333`, `5000`, `5002`, `5003`, `5432`, `8000`, `8080`,
  `8443`, `9443`, `9090`, `10000`.

A API Hostinger confirmou:

- firewall associado: `315250`;
- nome: `srv1403247-producao-minimo-20260620`;
- sincronização: ativa;
- regras: TCP `22/80/443` e UDP `41641`.

O `tailscale netcheck` confirmou UDP, IPv4 e IPv6 funcionais.

## Segredos e OAuth

- `.env`, chave DKIM privada e diretório `secrets/` estão fora do Git.
- O arquivo temporário `secrets/hostinger-api-token` ainda está presente e
  impede o fechamento de `P0-INF-06`.
- A configuração rclone está em diretório gravável.
- Renovação OAuth persistida com sucesso.
- `rclone about`: aprovado.

Nenhum segredo foi registrado nesta auditoria.

## Backup e restauração

Backup final:

```text
timestamp=20260621_090722
database=gestao_saude_oral_20260621_090722.dump
uploads=uploads_20260621_090722.tar.gz
manifest=manifest_20260621_090722.sha256
offsite=true
```

Resultados:

- hashes do dump e dos uploads: aprovados;
- cópia no Google Drive: `0 differences found`;
- três arquivos externos correspondentes;
- restore isolado: aprovado;
- tabelas públicas restauradas: `54`;
- pacientes restaurados: `0`.

## Condições para repetir a decisão

1. Revogar o token temporário no hPanel e apagar o arquivo local.
2. Confirmar 2FA, recuperação, custódias e revisão da conta Google.
3. Obter o aceite formal da política de governança e indicar o responsável
   clínico/jurídico.
4. Registrar a aprovação da coordenação.
5. Repetir os checks finais, usando banco temporário isolado para os testes.
6. Somente após decisão **GO**, criar a tag da versão de produção aprovada.

## Consolidação posterior

Após esta auditoria, o estado técnico foi consolidado como
`4.0.0-rc.1`. Essa identificação é uma pré-release para revisão e
rastreabilidade; não representa autorização de produção plena.
