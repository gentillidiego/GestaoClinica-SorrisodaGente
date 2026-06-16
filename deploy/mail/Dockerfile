FROM debian:13-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN set -eux; \
    echo "postfix postfix/mailname string mail.sorrisodagentealagoas.com" | debconf-set-selections; \
    echo "postfix postfix/main_mailer_type string Internet Site" | debconf-set-selections; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        opendkim \
        opendkim-tools \
        postfix; \
    rm -rf /var/lib/apt/lists/*

COPY deploy/mail/opendkim.conf /etc/opendkim.conf
COPY deploy/mail/TrustedHosts /etc/opendkim/TrustedHosts
COPY deploy/mail/entrypoint.sh /entrypoint.sh

RUN chmod 0755 /entrypoint.sh

EXPOSE 25

CMD ["/entrypoint.sh"]
