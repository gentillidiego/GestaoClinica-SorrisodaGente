#!/bin/sh
set -eu

BACKUP_DIR="${BACKUP_DIR:-/backups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
BACKUP_OFFSITE_RETENTION_DAYS="${BACKUP_OFFSITE_RETENTION_DAYS:-90}"
BACKUP_RCLONE_REMOTE="${BACKUP_RCLONE_REMOTE:-}"
BACKUP_OFFSITE_ENABLED="${BACKUP_OFFSITE_ENABLED:-false}"
BACKUP_SCHEDULE_HOUR="${BACKUP_SCHEDULE_HOUR:-2}"
BACKUP_SCHEDULE_MINUTE="${BACKUP_SCHEDULE_MINUTE:-30}"
BACKUP_RUN_ON_START="${BACKUP_RUN_ON_START:-true}"
RCLONE_CONFIG="${RCLONE_CONFIG:-/config/rclone/rclone.conf}"

log() {
    printf '[backup] %s %s\n' "$(date '+%Y-%m-%d %H:%M:%S%z')" "$*"
}

is_true() {
    case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
        1|true|yes|sim|on) return 0 ;;
        *) return 1 ;;
    esac
}

run_backup() {
    timestamp="$(date +%Y%m%d_%H%M%S)"
    dump_name="gestao_saude_oral_${timestamp}.dump"
    uploads_name="uploads_${timestamp}.tar.gz"
    manifest_name="manifest_${timestamp}.sha256"
    dump_partial="${BACKUP_DIR}/.${dump_name}.partial"
    uploads_partial="${BACKUP_DIR}/.${uploads_name}.partial"

    mkdir -p "${BACKUP_DIR}"
    rm -f "${dump_partial}" "${uploads_partial}"
    log "Iniciando backup ${timestamp}."

    PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump \
        --host "${POSTGRES_HOST:-postgres}" \
        --port "${POSTGRES_PORT:-5432}" \
        --username "${POSTGRES_USER:-clinica_user}" \
        --dbname "${POSTGRES_DB:-clinica}" \
        --format=custom \
        --no-owner \
        --no-privileges \
        --file "${dump_partial}"

    pg_restore --list "${dump_partial}" >/dev/null
    tar -czf "${uploads_partial}" -C /uploads .
    tar -tzf "${uploads_partial}" >/dev/null

    mv "${dump_partial}" "${BACKUP_DIR}/${dump_name}"
    mv "${uploads_partial}" "${BACKUP_DIR}/${uploads_name}"
    (
        cd "${BACKUP_DIR}"
        sha256sum "${dump_name}" "${uploads_name}" > "${manifest_name}"
    )

    if is_true "${BACKUP_OFFSITE_ENABLED}"; then
        if [ -z "${BACKUP_RCLONE_REMOTE}" ]; then
            log "BACKUP_RCLONE_REMOTE não configurado."
            return 1
        fi
        staging_dir="$(mktemp -d)"
        cp \
            "${BACKUP_DIR}/${dump_name}" \
            "${BACKUP_DIR}/${uploads_name}" \
            "${BACKUP_DIR}/${manifest_name}" \
            "${staging_dir}/"
        rclone mkdir "${BACKUP_RCLONE_REMOTE}" --config "${RCLONE_CONFIG}"
        rclone copy "${staging_dir}" "${BACKUP_RCLONE_REMOTE}" \
            --config "${RCLONE_CONFIG}" \
            --retries 5 \
            --low-level-retries 10 \
            --stats 0
        rclone check "${staging_dir}" "${BACKUP_RCLONE_REMOTE}" \
            --config "${RCLONE_CONFIG}" \
            --one-way \
            --download \
            --retries 5 \
            --low-level-retries 10
        rm -rf "${staging_dir}"
        rclone delete "${BACKUP_RCLONE_REMOTE}" \
            --config "${RCLONE_CONFIG}" \
            --min-age "${BACKUP_OFFSITE_RETENTION_DAYS}d" \
            --rmdirs || true
        log "Cópia externa validada em ${BACKUP_RCLONE_REMOTE}."
    fi

    find "${BACKUP_DIR}" -type f -mtime "+${BACKUP_RETENTION_DAYS}" \
        \( -name 'gestao_saude_oral_*.dump' -o -name 'uploads_*.tar.gz' -o -name 'manifest_*.sha256' \) \
        -delete

    {
        printf 'timestamp=%s\n' "${timestamp}"
        printf 'database=%s\n' "${dump_name}"
        printf 'uploads=%s\n' "${uploads_name}"
        printf 'manifest=%s\n' "${manifest_name}"
        printf 'offsite=%s\n' "${BACKUP_OFFSITE_ENABLED}"
    } > "${BACKUP_DIR}/LAST_SUCCESS"

    log "Backup, integridade e retenção concluídos: ${dump_name}."
}

schedule_loop() {
    last_attempt_day=''
    if [ -f "${BACKUP_DIR}/LAST_SUCCESS" ]; then
        last_timestamp="$(
            awk -F= '/^timestamp=/{print $2; exit}' "${BACKUP_DIR}/LAST_SUCCESS"
        )"
        if [ "${#last_timestamp}" -ge 8 ]; then
            last_attempt_day="$(
                printf '%s-%s-%s' \
                    "$(printf '%s' "${last_timestamp}" | cut -c1-4)" \
                    "$(printf '%s' "${last_timestamp}" | cut -c5-6)" \
                    "$(printf '%s' "${last_timestamp}" | cut -c7-8)"
            )"
        fi
    fi
    while true; do
        today="$(date +%Y-%m-%d)"
        hour="$(date +%H)"
        minute="$(date +%M)"
        current_minutes=$((10#${hour} * 60 + 10#${minute}))
        target_minutes=$((10#${BACKUP_SCHEDULE_HOUR} * 60 + 10#${BACKUP_SCHEDULE_MINUTE}))

        should_run=false
        if [ "${last_attempt_day}" != "${today}" ] && [ "${current_minutes}" -ge "${target_minutes}" ]; then
            should_run=true
        fi
        if is_true "${BACKUP_RUN_ON_START}" && [ ! -f "${BACKUP_DIR}/LAST_SUCCESS" ]; then
            should_run=true
        fi

        if [ "${should_run}" = true ]; then
            last_attempt_day="${today}"
            if ! run_backup; then
                log "ERRO: rotina de backup falhou; nova tentativa ocorrerá após reinício ou no próximo dia."
            fi
        fi
        sleep 60
    done
}

case "${1:-schedule}" in
    once) run_backup ;;
    schedule) schedule_loop ;;
    *)
        printf 'Uso: gso-backup [once|schedule]\n' >&2
        exit 2
        ;;
esac
