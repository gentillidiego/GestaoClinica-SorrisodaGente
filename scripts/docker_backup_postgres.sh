#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

docker compose run --rm backup once

echo
echo "Último backup validado:"
docker compose run --rm --no-deps --entrypoint sh backup -lc \
    'cat /backups/LAST_SUCCESS && cd /backups && sha256sum -c "$(awk -F= '"'"'/^manifest=/{print $2}'"'"' LAST_SUCCESS)"'
