#!/usr/bin/env bash
set -euo pipefail

if [ -f .env ]; then
    set -a
    . ./.env
    set +a
fi

PROJECT_NAME="${COMPOSE_PROJECT_NAME:-gestaosaudeoral}"
POSTGRES_IMAGE="${POSTGRES_BACKUP_IMAGE:-postgres:16-alpine}"
POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-clinica}"
POSTGRES_USER="${POSTGRES_USER:-clinica_user}"
BACKUP_VOLUME="${BACKUP_VOLUME:-${PROJECT_NAME}_backups_oral}"
UPLOADS_VOLUME="${UPLOADS_VOLUME:-${PROJECT_NAME}_uploads_oral}"
DOCKER_NETWORK="${DOCKER_NETWORK:-${PROJECT_NAME}_default}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD não está definida. Configure .env antes do backup.}"

timestamp="$(date +%Y%m%d_%H%M%S)"
dump_name="gestao_saude_oral_${timestamp}.dump"
uploads_name="uploads_${timestamp}.tar.gz"

docker run --rm \
    --network "${DOCKER_NETWORK}" \
    -v "${BACKUP_VOLUME}:/backups" \
    -e PGPASSWORD="${POSTGRES_PASSWORD}" \
    "${POSTGRES_IMAGE}" \
    pg_dump \
        --host "${POSTGRES_HOST}" \
        --port "${POSTGRES_PORT}" \
        --username "${POSTGRES_USER}" \
        --dbname "${POSTGRES_DB}" \
        --format=custom \
        --no-owner \
        --no-privileges \
        --file "/backups/${dump_name}"

docker run --rm \
    -v "${UPLOADS_VOLUME}:/uploads:ro" \
    -v "${BACKUP_VOLUME}:/backups" \
    "${POSTGRES_IMAGE}" \
    sh -lc "tar -czf /backups/${uploads_name} -C /uploads ."

docker run --rm \
    -v "${BACKUP_VOLUME}:/backups" \
    "${POSTGRES_IMAGE}" \
    sh -lc "find /backups -type f -mtime +${BACKUP_RETENTION_DAYS} -delete"

echo "Backup PostgreSQL criado: ${dump_name}"
echo "Backup uploads criado: ${uploads_name}"
