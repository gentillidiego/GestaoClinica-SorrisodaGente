# Auditoria OAuth do Google Drive e governança mínima

Data técnica: 21/06/2026

Horário operacional da VPS: 20/06/2026, 23h, `America/Maceio`

## Resultado executivo

`P0-GDRIVE-01` foi concluído. A configuração OAuth do rclone deixou de ser um
bind mount de arquivo e passou a ser um diretório gravável protegido,
permitindo a substituição atômica de `rclone.conf`.

`P0-GDRIVE-02` depende de confirmação humana da gestão para
ativação/verificação de 2FA e recuperação institucional. Em `P0-GOV-01`, os
papéis institucionais e técnicos e a política v1.0 foram definidos; faltam o
aceite formal e a indicação do responsável clínico/jurídico.

Nenhum token, senha, refresh token ou código de recuperação foi registrado
neste documento.

## Falha reproduzida antes da correção

- O mesmo arquivo host `secrets/sorriso-rclone.conf` era montado diretamente
  em web, worker e backup.
- A expiração persistida era `2026-06-18T16:44:17.164547197-03:00`.
- `rclone about` funcionava após refresh em memória, porém registrava:

```text
Failed to save config after 10 tries
rename .../rclone.conf .../rclone.conf.old: device or resource busy
```

## Correção aplicada

- Novo diretório host: `secrets/rclone`, modo `0700`.
- Arquivo: `secrets/rclone/rclone.conf`, modo `0600`.
- Bind mount do diretório inteiro em `/run/secrets/rclone` para:
  - `gestaosaudeoral-web`;
  - `gestaosaudeoral-celery`;
  - `gestaosaudeoral-backup`.
- Web, worker e backup usam
  `/run/secrets/rclone/rclone.conf`.
- Variável de implantação alterada de `RCLONE_CONFIG_HOST_PATH` para
  `RCLONE_CONFIG_HOST_DIR`.
- Criado `scripts/check_rclone_oauth.py`, que verifica diretório gravável,
  expiração, persistência e ausência do erro de bind sem exibir credenciais.

## Renovação persistente

O teste exigiu renovação de um token já expirado.

```text
Expiração anterior: 2026-06-18T16:44:17.164547197-03:00
Expiração atual: 2026-06-21T03:17:14.460988535Z
Renovação persistida: sim
rclone about: OK
```

Após o reinício completo da pilha, a mesma expiração permaneceu disponível e
web, worker e backup executaram `rclone about` com retorno zero. Os logs não
continham `device or resource busy` nem `failed to save config`.

## Upload, leitura e remoção

O smoke test `scripts/check_google_drive.py` confirmou:

- modo de upload `rclone`;
- conta OAuth e proprietária:
  `sorrisodagentealagoas@gmail.com`;
- pasta raiz `Prontuários`;
- upload de arquivo descartável;
- leitura integral do mesmo conteúdo;
- remoção do arquivo de teste.

Resultado: `Escrita/leitura/remoção: OK`.

## Compartilhamento da pasta raiz

A pasta `Prontuários` possui duas permissões:

- uma conta `user:owner`;
- uma conta `user:writer`.

As duas correspondem aos principais esperados — conta institucional e Service
Account — e não foram encontrados compartilhamentos adicionais inesperados.

## Backup, cópia externa e restore

Backup executado:

```text
gestao_saude_oral_20260620_231912.dump
uploads_20260620_231912.tar.gz
manifest_20260620_231912.sha256
```

Validação externa:

```text
0 differences found
3 matching files
```

Restore isolado:

```text
Tabelas públicas restauradas: 54
Pacientes restaurados: 0
```

## Reinício

Toda a pilha Docker foi reiniciada. Após o restart:

- aplicação: `status=healthy`, `database=ok`;
- PostgreSQL, Redis e backup: saudáveis;
- Celery worker/beat, mail e web: ativos;
- OAuth persistido: válido;
- leitura do Drive: aprovada;
- logs: sem erro de persistência do rclone.

## Governança

O procedimento mínimo está em
`docs/governanca_minima_2026-06-21.md`.

Pendências humanas antes de marcar `P0-GDRIVE-02` e `P0-GOV-01` como concluídos:

1. confirmar e registrar 2FA da conta Google;
2. confirmar dois meios/custodiantes de recuperação;
3. guardar códigos de recuperação fora da VPS;
4. obter aceite formal da Dra. Cibely para a política de governança;
5. indicar o responsável clínico/jurídico para decisões de descarte;
6. registrar os contatos e substitutos temporários acionáveis.

## Arquivos alterados

- `docker-compose.yml`
- `.env.example`
- `deploy/backup/backup.sh`
- `scripts/check_rclone_oauth.py`
- `README.md`
- `docs/governanca_minima_2026-06-21.md`
