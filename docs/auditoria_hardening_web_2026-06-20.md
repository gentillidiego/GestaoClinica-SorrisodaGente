# Auditoria de Hardening Web — 20/06/2026

Escopo: `P0-WEB-01` e `P0-WEB-02`.

## Controles Aplicados

- cookie de sessão com `Secure`, `HttpOnly` e `SameSite=Lax`;
- cookie de lembrança, se usado futuramente, com os mesmos atributos;
- renovação do identificador da sessão após login e primeiro acesso;
- limpeza integral da sessão no logout;
- logout aceito somente por `POST`, protegido pelo CSRF global;
- HSTS de um ano com `includeSubDomains` nas respostas HTTPS;
- CSP aplicada em modo de bloqueio;
- bloqueio de iframe por `frame-ancestors 'none'` e `X-Frame-Options: DENY`;
- `X-Content-Type-Options: nosniff`;
- `Referrer-Policy: strict-origin-when-cross-origin`;
- `Permissions-Policy` bloqueando câmera, microfone, geolocalização, pagamento
  e USB;
- `Cross-Origin-Opener-Policy: same-origin`;
- `Cross-Origin-Resource-Policy: same-origin`;
- referência aleatória por requisição em `X-Request-ID`;
- páginas seguras para erros 400/403/404/500;
- exceções genéricas removidas das mensagens HTML e JSON;
- detalhes técnicos e traceback mantidos apenas nos logs e registros internos;
- mensagens persistidas de falha do Drive/e-SUS neutralizadas antes de chegar
  às telas.

## CSP

Política aplicada:

- origem padrão restrita a `'self'`;
- `base-uri 'self'`, `object-src 'none'`, `form-action 'self'`;
- imagens e mídia limitadas a origem própria, `data:` e `blob:` conforme uso;
- scripts externos limitados aos três provedores já usados pelas telas:
  jsDelivr, unpkg e cdnjs;
- estilos/fontes externos limitados a Google Fonts e Bootstrap já existentes;
- frames limitados à própria origem e `blob:`;
- requisições inseguras promovidas por `upgrade-insecure-requests`.

As telas existentes ainda possuem scripts, manipuladores e estilos inline.
Por compatibilidade, a política mantém `'unsafe-inline'` em `script-src` e
`style-src`. A remoção gradual de inline e adoção de nonce/hash fica como
hardening incremental; as demais diretivas estão ativas e bloqueantes.

## Evidências Automatizadas

Arquivo: `tests/test_web_security.py`.

Os testes verificam:

- atributos efetivos do `Set-Cookie`;
- HSTS, CSP, iframe, MIME sniffing, referrer, permissions e isolamento;
- referência de requisição;
- exceção simulada contendo URL de banco, segredo e caminho local sem vazamento
  na resposta;
- rejeição de POST sem CSRF;
- aceitação de POST com CSRF e `Referer` HTTPS válidos;
- rota de logout somente por POST e formulário com token CSRF.

Resultado da suíte completa local:

```text
279 passed
```

## Evidências em Docker e HTTPS

- rebuild completo com `docker compose up -d --build`;
- web, PostgreSQL, Redis, Celery, Beat, backup e mail ativos;
- compilação Python dentro do container sem erros;
- Celery respondeu `pong`;
- `https://sorrisodagentealagoas.com/health` respondeu
  `status=healthy` e `database=ok`;
- resposta pública de `/login` confirmou todos os headers;
- `Set-Cookie` público confirmou `Secure; HttpOnly; SameSite=Lax`;
- `GET /logout` respondeu `405`;
- `POST /logout` sem CSRF respondeu `400`;
- POST com cookie, CSRF e `Referer` HTTPS válidos passou pela validação;
- logs recentes sem `ERROR`, `CRITICAL` ou traceback da aplicação.

## Arquivos Principais

- `services/web_security_service.py`;
- `app.py`;
- `blueprints/auth.py`;
- `templates/base.html`;
- `templates/error.html`;
- `tests/test_web_security.py`.
