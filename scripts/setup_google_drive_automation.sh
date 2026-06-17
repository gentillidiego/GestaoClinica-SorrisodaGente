#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PROJECT_ID="${GDRIVE_GCP_PROJECT_ID:-sorriso-da-gente-drive-prod}"
PROJECT_NAME="${GDRIVE_GCP_PROJECT_NAME:-Sorriso da Gente Drive}"
SERVICE_ACCOUNT_NAME="${GDRIVE_SERVICE_ACCOUNT_NAME:-sorriso-drive}"
SERVICE_ACCOUNT_DISPLAY_NAME="${GDRIVE_SERVICE_ACCOUNT_DISPLAY_NAME:-Sorriso da Gente Drive}"
SHARE_EMAIL="${GDRIVE_SHARE_EMAIL:-sorrisodagentealagoas@gmail.com}"
FOLDER_NAME="${GDRIVE_PATIENTS_FOLDER_NAME:-Prontuários}"
ENV_FILE="${ENV_FILE:-.env}"
KEY_HOST_PATH="${GDRIVE_KEY_HOST_PATH:-secrets/sorriso-google-drive-service-account.json}"
KEY_CONTAINER_PATH="${GDRIVE_KEY_PATH:-/run/secrets/sorriso/sorriso-google-drive-service-account.json}"

log() {
    printf '[google-drive-setup] %s\n' "$*"
}

fail() {
    printf '[google-drive-setup] ERRO: %s\n' "$*" >&2
    exit 1
}

sudo_cmd() {
    if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
        "$@"
    else
        sudo "$@"
    fi
}

install_gcloud_if_missing() {
    if command -v gcloud >/dev/null 2>&1; then
        return
    fi

    if [[ "${INSTALL_GCLOUD_IF_MISSING:-true}" != "true" ]]; then
        fail "gcloud não está instalado. Defina INSTALL_GCLOUD_IF_MISSING=true ou instale Google Cloud CLI."
    fi

    if ! command -v apt-get >/dev/null 2>&1; then
        fail "gcloud não está instalado e este script só instala automaticamente em sistemas Debian/Ubuntu com apt-get."
    fi

    log "Instalando Google Cloud CLI via apt."
    sudo_cmd apt-get update
    sudo_cmd apt-get install -y apt-transport-https ca-certificates gnupg curl
    curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg \
        | sudo_cmd gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg
    printf 'deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main\n' \
        | sudo_cmd tee /etc/apt/sources.list.d/google-cloud-sdk.list >/dev/null
    sudo_cmd apt-get update
    sudo_cmd apt-get install -y google-cloud-cli
}

ensure_gcloud_auth() {
    local active_account
    active_account="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null | head -n 1 || true)"
    if [[ -n "$active_account" ]]; then
        log "Google Cloud autenticado como $active_account."
        return
    fi

    log "Nenhuma conta Google Cloud autenticada. Abrindo fluxo oficial de login."
    log "Esta é a única autorização humana inevitável; o restante do setup é automático."
    gcloud auth login --update-adc --no-launch-browser
}

ensure_env_var() {
    local key="$1"
    local value="$2"
    local file="$3"
    local tmp_file

    touch "$file"
    tmp_file="$(mktemp)"
    awk -v key="$key" -v value="$value" '
        BEGIN { updated = 0 }
        $0 ~ "^" key "=" {
            print key "=" value
            updated = 1
            next
        }
        { print }
        END {
            if (!updated) {
                print key "=" value
            }
        }
    ' "$file" > "$tmp_file"
    mv "$tmp_file" "$file"
}

extract_client_email() {
    python3 - "$1" <<'PY'
import json
import sys

with open(sys.argv[1], 'r', encoding='utf-8') as file_obj:
    print(json.load(file_obj).get('client_email', ''))
PY
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "Comando obrigatório não encontrado: $1"
}

require_command docker
require_command python3

if ! docker compose version >/dev/null 2>&1; then
    fail "Docker Compose v2 não está disponível. Verifique a instalação do Docker."
fi

[[ -f "$ENV_FILE" ]] || fail "Arquivo $ENV_FILE não encontrado. Este script completa o .env existente da VPS; ele não cria configuração de produção do zero."

mkdir -p "$(dirname "$KEY_HOST_PATH")"

if [[ ! -f "$KEY_HOST_PATH" ]]; then
    install_gcloud_if_missing
    ensure_gcloud_auth

    if gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1; then
        log "Projeto Google Cloud já existe: $PROJECT_ID."
    else
        log "Criando projeto Google Cloud: $PROJECT_ID."
        gcloud projects create "$PROJECT_ID" --name="$PROJECT_NAME"
    fi

    gcloud config set project "$PROJECT_ID" >/dev/null
    log "Habilitando Google Drive API no projeto $PROJECT_ID."
    gcloud services enable drive.googleapis.com --project "$PROJECT_ID"

    service_account_email="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
    if gcloud iam service-accounts describe "$service_account_email" --project "$PROJECT_ID" >/dev/null 2>&1; then
        log "Service Account já existe: $service_account_email."
    else
        log "Criando Service Account: $service_account_email."
        gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
            --display-name="$SERVICE_ACCOUNT_DISPLAY_NAME" \
            --project "$PROJECT_ID"
    fi

    log "Gerando chave JSON em $KEY_HOST_PATH."
    gcloud iam service-accounts keys create "$KEY_HOST_PATH" \
        --iam-account "$service_account_email" \
        --project "$PROJECT_ID"
    chmod 600 "$KEY_HOST_PATH"
else
    service_account_email="$(extract_client_email "$KEY_HOST_PATH")"
    log "Chave JSON já existe em $KEY_HOST_PATH."
fi

[[ -n "${service_account_email:-}" ]] || fail "Não foi possível identificar o client_email da Service Account."

ensure_env_var GDRIVE_KEY_PATH "$KEY_CONTAINER_PATH" "$ENV_FILE"
ensure_env_var GDRIVE_PATIENTS_FOLDER_NAME "$FOLDER_NAME" "$ENV_FILE"

log "Subindo/reconstruindo containers para garantir dependências do Google Drive."
docker compose up -d --build

log "Criando ou encontrando pasta '$FOLDER_NAME' no Drive e compartilhando com $SHARE_EMAIL."
if ! provision_output="$(
    docker compose exec -T \
        -e GDRIVE_ROOT_FOLDER_ID= \
        -e GDRIVE_PATIENTS_FOLDER_NAME="$FOLDER_NAME" \
        gestaoclinica \
        python scripts/provision_google_drive.py \
            --folder-name "$FOLDER_NAME" \
            --share-email "$SHARE_EMAIL" 2>&1
)"; then
    printf '%s\n' "$provision_output" >&2
    fail "Provisionamento da pasta no Google Drive falhou."
fi

printf '%s\n' "$provision_output"
root_folder_id="$(printf '%s\n' "$provision_output" | awk -F= '/^GDRIVE_ROOT_FOLDER_ID=/{print $2; exit}')"
[[ -n "$root_folder_id" ]] || fail "Não foi possível capturar GDRIVE_ROOT_FOLDER_ID."

ensure_env_var GDRIVE_ROOT_FOLDER_ID "$root_folder_id" "$ENV_FILE"

log "Recarregando containers com GDRIVE_ROOT_FOLDER_ID=$root_folder_id."
docker compose up -d

log "Validando conexão final."
docker compose exec -T gestaoclinica python scripts/check_google_drive.py

cat <<EOF

Setup do Google Drive concluído.

Service Account:
  $service_account_email

Pasta raiz:
  $FOLDER_NAME
  $root_folder_id

Conta compartilhada:
  $SHARE_EMAIL

Próximo teste automático após cadastrar um paciente:
  docker compose exec -T gestaoclinica python scripts/check_google_drive.py --patient-id ID_DO_PACIENTE
EOF
