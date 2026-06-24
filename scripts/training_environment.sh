#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.training.yml"
ENV_FILE="$ROOT_DIR/.env.training"
PROJECT_NAME="gso-training"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Arquivo .env.training ausente."
  echo "Copie .env.training.example e defina as credenciais locais."
  exit 1
fi

compose() {
  docker compose \
    --project-name "$PROJECT_NAME" \
    --env-file "$ENV_FILE" \
    --file "$COMPOSE_FILE" \
    "$@"
}

case "${1:-status}" in
  start)
    compose up -d --build
    compose exec -T training-web python scripts/seed_training_data.py
    ;;
  seed)
    compose exec -T training-web python scripts/seed_training_data.py
    ;;
  reset)
    compose down --volumes --remove-orphans
    compose up -d --build
    compose exec -T training-web python scripts/seed_training_data.py
    ;;
  stop)
    compose down
    ;;
  status)
    compose ps
    ;;
  logs)
    compose logs --since 15m training-web training-postgres training-redis training-mail
    ;;
  *)
    echo "Uso: $0 {start|seed|reset|stop|status|logs}"
    exit 1
    ;;
esac
