# Ambiente Isolado de Treinamento

Status: **disponível**

Aplicação: **4.0.0-rc.1-training**

Validação: **22/06/2026**

## Acessos

- aplicação: `http://127.0.0.1:5103`;
- caixa de e-mails local: `http://127.0.0.1:5125`;
- produção permanece em `http://127.0.0.1:5003`, atrás do domínio oficial.

O treinamento usa PostgreSQL, Redis, uploads, e-mails e volumes próprios. Não
possui Celery worker, Celery Beat, backup externo ou envio automático e-SUS.
O Google Drive está desabilitado.

Se o navegador estiver em outro computador, abra um túnel SSH:

```bash
ssh -L 5103:127.0.0.1:5103 \
    -L 5125:127.0.0.1:5125 \
    diego@srv1403247.hstgr.cloud
```

Mantenha o terminal conectado durante a gravação e acesse os mesmos endereços
`127.0.0.1` no navegador local. As portas não estão publicadas na internet.

## Usuários

A senha padrão dos usuários com acesso concluído está na variável
`TRAINING_DEFAULT_PASSWORD` do arquivo local `.env.training`.

```bash
grep '^TRAINING_DEFAULT_PASSWORD=' .env.training
```

| Login | Perfil |
|---|---|
| `treino.admin` | Administrador |
| `treino.coordenacao` | Coordenação |
| `treino.clinico` | Clínicos |
| `treino.recepcao` | Recepção |
| `treino.cme` | CME / Estoque |
| `treino.radiologia` | Radiologia |
| `treino.comunicacao` | Comunicação |
| `treino.ssa` | SSA/SMS |
| `treino.auditoria` | Auditoria |

Primeiro acesso:

- login: `treino.primeiro`;
- data de nascimento: `15/01/1990`;
- a senha anterior é aleatória e não é utilizada;
- para repetir a videoaula depois de concluir esse acesso, restaure o ambiente.

## Pacientes preparados

| Paciente | Uso recomendado |
|---|---|
| Paciente Triagem Treinamento | geração de senha na atividade de Triagem |
| Paciente Agenda Treinamento | agendamento após demanda vinculada |
| Paciente TCLE Treinamento | prontuário ainda sem TCLE |
| Paciente Anamnese Treinamento | TCLE concluído e anamnese pendente |
| Paciente Plano Treinamento | TCLE e anamnese concluídos; plano pendente |

Há também oito pacientes fictícios completos para Central de Comando, BI,
Epidemiologia e relatórios.

## Operação

```bash
# Consultar estado
scripts/training_environment.sh status

# Iniciar e garantir a carga fictícia
scripts/training_environment.sh start

# Reexecutar a carga de forma idempotente
scripts/training_environment.sh seed

# Apagar somente os volumes de treinamento e recriar o cenário inicial
scripts/training_environment.sh reset

# Consultar logs
scripts/training_environment.sh logs

# Parar sem apagar os dados
scripts/training_environment.sh stop
```

O comando `reset` remove apenas recursos do projeto Docker `gso-training`.
Mesmo assim, confirme sempre o nome do script e evite executar comandos Docker
manuais com remoção de volumes.

## Ordem para gravação

1. execute `reset` antes de iniciar uma rodada completa;
2. grave Primeiro acesso;
3. grave Novo usuário e Novo paciente;
4. use os pacientes preparados nos demais roteiros;
5. repita `reset` quando precisar restaurar o primeiro acesso ou desfazer as
   alterações da gravação.

## Segurança

- não use o endereço de produção durante a gravação;
- não copie dados reais para o treinamento;
- não altere `.env` ou `docker-compose.yml` de produção;
- a senha de treinamento não pode ser reutilizada em nenhuma conta real;
- e-mails enviados pela aplicação ficam somente no Mailpit local.
