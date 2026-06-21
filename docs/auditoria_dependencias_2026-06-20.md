# Auditoria de Dependências — 20/06/2026

## Escopo

Atualização e validação do pacote `P0-DEP-01`, cobrindo dependências Python,
imagem Docker, imagens/WebP, PDF/WeasyPrint, XML/XSD e Celery.

O `pip-audit 2.10.1` foi executado em contêineres efêmeros e não foi adicionado
às dependências de runtime da aplicação.

## Situação inicial

A auditoria inicial de `requirements.txt` encontrou 15 ocorrências conhecidas:

| Pacote | Versão anterior | Ocorrências | Versão corrigida |
|---|---:|---:|---:|
| Flask | 3.0.3 | 1 | 3.1.3 |
| Werkzeug | 3.0.3 | 5 | 3.1.8 |
| Pillow | 12.1.1 | 6 | 12.2.0 |
| lxml | 5.3.1 | 2 | 6.1.1 |
| python-dotenv | 1.0.1 | 1 | 1.2.2 |

Também havia duas linhas idênticas para `redis==5.0.8`.

## Alterações aplicadas

- Flask atualizado para `3.1.3`;
- Werkzeug atualizado para `3.1.8`;
- Pillow atualizado para `12.2.0`;
- lxml atualizado para `6.1.1`;
- python-dotenv atualizado para `1.2.2`;
- duplicidade de `redis==5.0.8` removida;
- `pip` da imagem atualizado de `24.0` para `26.1.2`;
- `wheel` da imagem atualizado de `0.45.1` para `0.46.2`.

As versões de `pip` e `wheel` foram fixadas no `Dockerfile` porque a primeira
auditoria do ambiente instalado encontrou seis ocorrências adicionais nesses
dois componentes de build.

## Resultado da auditoria

Foram executadas três modalidades:

1. pins diretos de `requirements.txt`, com `--no-deps`;
2. resolução completa de dependências diretas e transitivas;
3. ambiente efetivamente instalado na imagem Docker, com `--local`.

Resultado final das três modalidades:

```text
No known vulnerabilities found
```

`python -m pip check` na imagem final:

```text
No broken requirements found.
```

## Validações de regressão

- suíte completa dentro da imagem atualizada: `273 passed`;
- testes focados em imagens, exames, arquivos protegidos e e-SUS/XML:
  `57 passed`;
- JPEG aberto e verificado pelo Pillow;
- conversão e reabertura de derivado WebP concluídas;
- PDF real gerado pelo WeasyPrint;
- PDF assíncrono gerado pelo worker Celery com estado `SUCCESS`;
- XML validado por XSD com lxml;
- cadeia e-SUS/SIGTAP coberta pela suíte automatizada;
- leitura de variáveis por python-dotenv validada;
- worker Celery respondeu `pong` e registrou as sete tarefas esperadas;
- rebuild Docker concluído;
- `pip check` sem dependências quebradas;
- `/health` local e HTTPS responderam `status=healthy` e `database=ok`;
- logs recentes de web, worker e beat sem `ERROR`, `CRITICAL` ou traceback.

O aviso de worker Celery executando como root permanece uma pendência P1 já
prevista no plano e não foi introduzido por esta atualização.

## Fontes oficiais de versão

- Flask: <https://pypi.org/project/Flask/>
- Werkzeug: <https://pypi.org/project/Werkzeug/>
- Pillow: <https://pypi.org/project/pillow/>
- lxml: <https://pypi.org/project/lxml/>
- python-dotenv: <https://pypi.org/project/python-dotenv/>
- pip-audit: <https://pypi.org/project/pip-audit/>
