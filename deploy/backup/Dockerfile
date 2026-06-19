FROM postgres:16-alpine

RUN apk add --no-cache rclone tzdata

COPY deploy/backup/backup.sh /usr/local/bin/gso-backup
RUN chmod 0755 /usr/local/bin/gso-backup

ENTRYPOINT ["/usr/local/bin/gso-backup"]
CMD ["schedule"]
