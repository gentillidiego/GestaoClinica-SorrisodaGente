#!/usr/bin/env bash
set -euo pipefail

if [ -f .env ]; then
    set -a
    . ./.env
    set +a
fi

PROJECT_NAME="${COMPOSE_PROJECT_NAME:-gestaosaudeoral}"
POSTGRES_IMAGE="${POSTGRES_BACKUP_IMAGE:-postgres:16-alpine}"
BACKUP_VOLUME="${BACKUP_VOLUME:-${PROJECT_NAME}_backups_oral}"
DOCKER_NETWORK="${DOCKER_NETWORK:-${PROJECT_NAME}_default}"

requested_dump="${1:-}"

if [ -n "${requested_dump}" ]; then
    dump_name="$(basename "${requested_dump}")"
else
    dump_name="$(
        docker run --rm \
            -v "${BACKUP_VOLUME}:/backups:ro" \
            "${POSTGRES_IMAGE}" \
            sh -lc "ls -t /backups/gestao_saude_oral_*.dump 2>/dev/null | head -n 1 | xargs -r basename"
    )"
fi

if [ -z "${dump_name}" ]; then
    echo "Nenhum arquivo gestao_saude_oral_*.dump encontrado no volume ${BACKUP_VOLUME}." >&2
    exit 1
fi

container_name="gso-restore-verify-$(date +%Y%m%d%H%M%S)"

cleanup() {
    docker rm -f "${container_name}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker run -d \
    --name "${container_name}" \
    --network "${DOCKER_NETWORK}" \
    -e POSTGRES_USER=restore_user \
    -e POSTGRES_PASSWORD=restore_pass \
    -e POSTGRES_DB=restore_db \
    "${POSTGRES_IMAGE}" >/dev/null

ready=false
for _ in $(seq 1 30); do
    if docker exec "${container_name}" pg_isready -U restore_user -d restore_db >/dev/null 2>&1; then
        ready=true
        break
    fi
    sleep 1
done

if [ "${ready}" != true ]; then
    docker logs "${container_name}" >&2
    echo "PostgreSQL temporário não ficou pronto para validar o restore." >&2
    exit 1
fi

docker run --rm \
    --network "${DOCKER_NETWORK}" \
    -v "${BACKUP_VOLUME}:/backups:ro" \
    -e PGPASSWORD=restore_pass \
    "${POSTGRES_IMAGE}" \
    pg_restore \
        --exit-on-error \
        --no-owner \
        --no-privileges \
        --dbname "postgresql://restore_user:restore_pass@${container_name}:5432/restore_db" \
        "/backups/${dump_name}"

table_count="$(
    docker run --rm \
        --network "${DOCKER_NETWORK}" \
        -e PGPASSWORD=restore_pass \
        "${POSTGRES_IMAGE}" \
        psql \
            --host "${container_name}" \
            --username restore_user \
            --dbname restore_db \
            --tuples-only \
            --no-align \
            --command "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';"
)"

patient_count="$(
    docker run --rm \
        --network "${DOCKER_NETWORK}" \
        -e PGPASSWORD=restore_pass \
        "${POSTGRES_IMAGE}" \
        psql \
            --host "${container_name}" \
            --username restore_user \
            --dbname restore_db \
            --tuples-only \
            --no-align \
            --command "SELECT count(*) FROM patients;"
)"

echo "Restore validado com sucesso: ${dump_name}"
echo "Tabelas públicas restauradas: ${table_count}"
echo "Pacientes restaurados: ${patient_count}"
