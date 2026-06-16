# Email de Producao - sorrisodagentealagoas.com

Data: 2026-06-16

## Status implantado

O envio transacional da aplicacao foi configurado com um servico Docker dedicado:

- Servico SMTP: `mail`
- Container: `gestaosaudeoral-mail`
- Stack: Postfix send-only + OpenDKIM
- Remetente: `nao-responda@sorrisodagentealagoas.com`
- Base URL dos links: `https://sorrisodagentealagoas.com`

O servico nao expoe a porta 25 publicamente no `docker-compose`; ele recebe mensagens apenas pela rede interna do compose e entrega para os MX externos dos destinatarios.

## DNS publicado na Hostinger

Registros confirmados nos nameservers autoritativos `artemis.dns-parking.com` e `hermes.dns-parking.com`:

```dns
mail.sorrisodagentealagoas.com.          A    72.60.248.85
sorrisodagentealagoas.com.               MX   10 mail.sorrisodagentealagoas.com.
sorrisodagentealagoas.com.               TXT  "v=spf1 ip4:72.60.248.85 -all"
_dmarc.sorrisodagentealagoas.com.        TXT  "v=DMARC1; p=none; adkim=s; aspf=s"
mail._domainkey.sorrisodagentealagoas.com. TXT "v=DKIM1; h=sha256; k=rsa; p=..."
```

O DMARC esta em `p=none` para observacao inicial. Depois de validar recebimento em Gmail/Outlook, pode evoluir para `p=quarantine` e, por ultimo, `p=reject`.

## Configuracao da aplicacao

Variaveis ativas no `.env`:

```env
APP_BASE_URL=https://sorrisodagentealagoas.com
SMTP_HOST=mail
SMTP_PORT=25
SMTP_USE_TLS=false
SMTP_USE_SSL=false
SMTP_USERNAME=
SMTP_PASSWORD=
MAIL_FROM=nao-responda@sorrisodagentealagoas.com
```

## DKIM

A chave privada foi gerada em:

```text
deploy/mail/dkim/mail.private
```

Esse diretorio esta ignorado pelo Git. Nao publicar nem enviar a chave privada.

Validacao executada:

```bash
docker exec gestaosaudeoral-mail opendkim-testkey -d sorrisodagentealagoas.com -s mail -k /dkim/mail.private -vvv
```

Resultado relevante:

```text
key OK
```

O aviso `key not secure` significa apenas que a zona nao esta assinada com DNSSEC.

## Testes executados

DNS publico:

```bash
dig +short A mail.sorrisodagentealagoas.com
dig +short MX sorrisodagentealagoas.com
dig +short TXT sorrisodagentealagoas.com
dig +short TXT _dmarc.sorrisodagentealagoas.com
dig +short TXT mail._domainkey.sorrisodagentealagoas.com
```

Envio pela aplicacao:

```bash
docker exec -i gestaosaudeoral-web python - <<'PY'
from services.mail_service import send_email
send_email(
    'Teste DKIM controlado - Sorriso da Gente',
    'teste-dkim@sorrisodagentealagoas.com',
    'Teste tecnico para conferir assinatura DKIM.',
    html_body='<p>Teste tecnico para conferir assinatura DKIM.</p>',
)
PY
```

O item enfileirado no Postfix continha:

```text
DKIM-Signature: v=1; a=rsa-sha256; c=relaxed/simple;
    d=sorrisodagentealagoas.com; s=mail;
```

## PTR / rDNS

A API da Hostinger foi atualizada para:

```text
72.60.248.85 -> mail.sorrisodagentealagoas.com
```

No momento da implantacao, a consulta publica ainda podia retornar o valor antigo por propagacao/cache:

```text
72.60.248.85 -> srv1403247.hstgr.cloud.
```

Validar depois com:

```bash
dig +short -x 72.60.248.85
```

## Operacao

Subir ou recriar o servico:

```bash
docker compose up -d --build mail gestaoclinica celery-worker celery-beat
```

Logs:

```bash
docker logs -f gestaosaudeoral-mail
```

Fila:

```bash
docker exec gestaosaudeoral-mail postqueue -p
```
