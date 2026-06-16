#!/bin/sh
set -eu

MAIL_DOMAIN="${MAIL_DOMAIN:-sorrisodagentealagoas.com}"
MAIL_HOSTNAME="${MAIL_HOSTNAME:-mail.sorrisodagentealagoas.com}"
DKIM_SELECTOR="${DKIM_SELECTOR:-mail}"
DKIM_SOURCE="/dkim/${DKIM_SELECTOR}.private"
DKIM_RUNTIME="/run/opendkim/keys/${DKIM_SELECTOR}.private"

if [ ! -s "$DKIM_SOURCE" ]; then
  echo "DKIM private key not found at ${DKIM_SOURCE}" >&2
  exit 1
fi

install -d -o opendkim -g opendkim -m 0750 /run/opendkim /run/opendkim/keys /etc/opendkim
install -o opendkim -g opendkim -m 0400 "$DKIM_SOURCE" "$DKIM_RUNTIME"

cat > /etc/opendkim/SigningTable <<EOF
*@${MAIL_DOMAIN} ${DKIM_SELECTOR}._domainkey.${MAIL_DOMAIN}
EOF

cat > /etc/opendkim/KeyTable <<EOF
${DKIM_SELECTOR}._domainkey.${MAIL_DOMAIN} ${MAIL_DOMAIN}:${DKIM_SELECTOR}:${DKIM_RUNTIME}
EOF

postconf -e "myhostname = ${MAIL_HOSTNAME}"
postconf -e "mydomain = ${MAIL_DOMAIN}"
postconf -e "myorigin = ${MAIL_DOMAIN}"
postconf -e "mydestination = localhost"
postconf -e "relayhost ="
postconf -e "inet_interfaces = all"
postconf -e "inet_protocols = ipv4"
postconf -e "mynetworks = 127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16"
postconf -e "smtpd_relay_restrictions = permit_mynetworks, reject_unauth_destination"
postconf -e "smtpd_recipient_restrictions = permit_mynetworks, reject_unauth_destination"
postconf -e "smtp_tls_security_level = may"
postconf -e "smtp_tls_CAfile = /etc/ssl/certs/ca-certificates.crt"
postconf -e "milter_default_action = accept"
postconf -e "milter_protocol = 6"
postconf -e "smtpd_milters = inet:127.0.0.1:8891"
postconf -e "non_smtpd_milters = inet:127.0.0.1:8891"
postconf -e "maillog_file = /dev/stdout"

opendkim -x /etc/opendkim.conf
exec postfix start-fg
