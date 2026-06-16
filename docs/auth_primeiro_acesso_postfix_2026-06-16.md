# Autenticacao, Primeiro Acesso e Recuperacao de Senha

Data: 2026-06-16

## Visao geral

Este projeto usa autenticacao por sessao com `Flask-Login`, nao JWT. Por isso, o fluxo abaixo adapta a regra de negocio pedida para o stack real da aplicacao:

1. `Pre-cadastro profissional`
   O profissional envia os dados em `/cadastro/`.

2. `Aprovacao administrativa do pre-cadastro`
   A equipe aprova a solicitacao em `Admin > Pre-cadastros`. A aprovacao cria o usuario automaticamente com `is_first_access = true`, usando o login escolhido e a data de nascimento informada.

3. `Primeiro acesso`
   O usuario valida `login + data de nascimento` em `/primeiro-acesso` e define a senha definitiva em `/primeiro-acesso/definir-senha`.

4. `Login normal`
   Depois disso, o acesso ocorre em `/login`.

5. `Recuperacao de senha`
   O usuario solicita o link em `/esqueci-senha` e redefine em `/redefinir-senha?token=...`.

## Campos de banco

Tabela `users`:

- `email`
- `celular`
- `data_nascimento`
- `is_first_access`
- `first_access_completed_at`
- `email_confirmed_at`
- `password_changed_at`
- `password_reset_token_hash`
- `password_reset_expires_at`
- `password_reset_used_at`

Tabela `professional_registration_requests`:

- `full_name`
- `cpf`
- `data_nascimento`
- `email`
- `celular`
- `desired_username`
- `requested_role`
- `cns`
- `cbo`
- `cro`
- `cro_uf`
- `notes`
- `truth_accepted`
- `lgpd_accepted`
- `status`
- `review_notes`
- `reviewed_by`
- `reviewed_at`
- `created_user_id`
- `source_ip`
- `user_agent`
- `submitted_payload`
- `created_at`
- `updated_at`

## Rotas

Frontend e backend:

- `GET/POST /cadastro/`
  Recebe o pre-cadastro profissional.

- `GET/POST /login`
  Login comum com senha definitiva.

- `GET/POST /primeiro-acesso`
  Valida `login + data de nascimento`.

- `GET/POST /primeiro-acesso/definir-senha`
  Define a senha definitiva e confirma o e-mail.

- `GET/POST /esqueci-senha`
  Solicita o envio do link de redefinicao.

- `GET/POST /redefinir-senha`
  Consome o token temporario e troca a senha.

- `GET /admin/professional-registrations`
  Lista os pre-cadastros recebidos.

- `POST /admin/professional-registrations/<id>/approve`
  Aprova o pre-cadastro e cria o usuario para primeiro acesso.

- `POST /admin/professional-registrations/<id>/reject`
  Recusa o pre-cadastro com observacao administrativa.

## Regras aplicadas

- Usuario com `is_first_access = true` nao entra pelo login comum.
- Primeiro acesso depende de `data_nascimento` cadastrada.
- A senha definitiva precisa de pelo menos 8 caracteres, com letra e numero.
- O token de redefinicao fica salvo em hash `SHA-256`, com expiracao de 2 horas.
- Depois do uso, o token fica inutilizado.

## Postfix send-only

### Cenario Docker

Opcao 1: Postfix no host Linux e a aplicacao apontando para o host.

- `SMTP_HOST=host.docker.internal` ou IP interno do host
- `SMTP_PORT=25`
- `SMTP_USE_TLS=false`
- `MAIL_FROM=nao-responda@sorrisodagentealagoas.com`
- `APP_BASE_URL=https://sorrisodagentealagoas.com`

Opcao 2: Postfix em servico separado no `docker-compose` (modelo implantado).

Exemplo de variaveis:

```env
SMTP_HOST=mail
SMTP_PORT=25
SMTP_USE_TLS=false
SMTP_USE_SSL=false
MAIL_FROM=nao-responda@sorrisodagentealagoas.com
APP_BASE_URL=https://sorrisodagentealagoas.com
```

### Cenario Linux host

Pacotes:

```bash
apt-get update
apt-get install -y postfix mailutils opendkim opendkim-tools
```

Modo sugerido:

- `Internet Site`
- hostname: `mail.sorrisodagentealagoas.com`
- uso `send-only`

Trechos de `main.cf`:

```conf
myhostname = mail.sorrisodagentealagoas.com
myorigin = /etc/mailname
inet_interfaces = loopback-only
mydestination = localhost
relayhost =
mynetworks = 127.0.0.0/8 [::1]/128
smtpd_recipient_restrictions = permit_mynetworks,reject_unauth_destination

# DKIM
milter_default_action = accept
milter_protocol = 6
smtpd_milters = inet:localhost:8891
non_smtpd_milters = inet:localhost:8891
```

Arquivo `/etc/mailname`:

```text
sorrisodagentealagoas.com
```

### DKIM com OpenDKIM

Geracao da chave:

```bash
mkdir -p /etc/opendkim/keys/sorrisodagentealagoas.com
opendkim-genkey -D /etc/opendkim/keys/sorrisodagentealagoas.com/ -d sorrisodagentealagoas.com -s mail
chown -R opendkim:opendkim /etc/opendkim/keys/sorrisodagentealagoas.com
```

Mapeamentos:

- `KeyTable`
- `SigningTable`
- `TrustedHosts`

Depois reiniciar:

```bash
systemctl restart opendkim
systemctl restart postfix
```

## DNS obrigatorio

### SPF

```dns
v=spf1 ip4:SEU_IP_PUBLICO -all
```

### DKIM

Publicar o TXT gerado em:

```dns
mail._domainkey.sorrisodagentealagoas.com
```

### DMARC

Inicialmente publicado em modo de observacao:

```dns
_dmarc.sorrisodagentealagoas.com  TXT  "v=DMARC1; p=none; adkim=s; aspf=s"
```

Depois da validacao em Gmail/Outlook, evoluir para `p=quarantine` e, por fim, `p=reject`.

### PTR / rDNS

Configurar na operadora da VPS:

- IP publico `-> mail.sorrisodagentealagoas.com`

E no DNS direto:

- `mail.sorrisodagentealagoas.com -> SEU_IP_PUBLICO`

## Frontend

Passos de UX:

1. Tela `/login` com tres entradas claras:
   `Entrar`, `Primeiro acesso`, `Esqueci minha senha`.

2. Tela `/primeiro-acesso`:
   `login + data de nascimento`.

3. Tela `/primeiro-acesso/definir-senha`:
   confirmar e-mail e criar senha.

4. Tela `/esqueci-senha`:
   login ou e-mail.

5. Tela `/redefinir-senha`:
   token oculto + nova senha + confirmacao.

## Pendencias naturais

- Integrar envio de e-mail em background com Celery, se o volume crescer.
- Monitorar reputacao do IP e entregar testes reais em Gmail e Outlook.
