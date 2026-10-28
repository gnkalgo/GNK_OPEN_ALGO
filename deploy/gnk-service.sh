#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_FILES=(-f compose.yaml -f compose.production.yaml)
COMPOSE=(docker compose "${COMPOSE_FILES[@]}")

command="${1:-help}"
if (($# > 0)); then
    shift
fi

usage() {
    cat <<'EOF'
Usage: ./deploy/gnk-service.sh COMMAND [SERVICE...]

Commands:
  start [service...]    Start the stack without rebuilding
  stop [service...]     Stop the stack without removing containers or data
  restart [service...]  Restart running services
  build [service...]    Build images without starting services
  deploy                Fast-forward pull origin/main, then build and start all
  update                Build and start all using the current local source
  status                Show service state
  logs [service...]     Follow logs (defaults to all services)
  health                Check the public readiness endpoint
  config                Validate the production Compose configuration
  help                  Show this help

Set GNK_HEALTH_URL to override the URL checked by the health command.
EOF
}

for file in compose.yaml compose.production.yaml; do
    if [[ ! -f "$ROOT_DIR/$file" ]]; then
        echo "Error: $ROOT_DIR/$file was not found. Run this script from a GNK ALGO checkout." >&2
        exit 1
    fi
done

case "$command" in
    help|-h|--help|health)
        ;;
    *)
        if ! command -v docker >/dev/null 2>&1; then
            echo "Error: docker is required but was not found in PATH." >&2
            exit 127
        fi

        if ! docker compose version >/dev/null 2>&1; then
            echo "Error: Docker Compose v2 is required." >&2
            exit 127
        fi
        ;;
esac

if [[ "$command" == "help" || "$command" == "-h" || "$command" == "--help" ]]; then
    usage
    exit 0
fi

case "$command" in
    start)
        "${COMPOSE[@]}" up -d "$@"
        ;;
    stop)
        "${COMPOSE[@]}" stop "$@"
        ;;
    restart)
        "${COMPOSE[@]}" restart "$@"
        ;;
    build)
        "${COMPOSE[@]}" build "$@"
        ;;
    deploy)
        if (($# > 0)); then
            echo "Error: deploy updates and rebuilds the full stack; it does not accept service names." >&2
            exit 2
        fi
        if ! command -v git >/dev/null 2>&1; then
            echo "Error: git is required for deploy. Use 'update' to deploy local source." >&2
            exit 127
        fi
        git pull --ff-only origin main
        "${COMPOSE[@]}" up -d --build
        ;;
    update)
        "${COMPOSE[@]}" up -d --build "$@"
        ;;
    status|ps)
        "${COMPOSE[@]}" ps "$@"
        ;;
    logs)
        "${COMPOSE[@]}" logs --follow --tail=100 "$@"
        ;;
    health)
        if ! command -v curl >/dev/null 2>&1; then
            echo "Error: curl is required for the health check." >&2
            exit 127
        fi
        curl --fail --show-error --silent "${GNK_HEALTH_URL:-https://gnkalgo.com/api/health/ready}"
        printf '\n'
        ;;
    config)
        "${COMPOSE[@]}" config --quiet
        ;;
    help|-h|--help)
        usage
        ;;
    *)
        echo "Error: unknown command '$command'." >&2
        usage >&2
        exit 2
        ;;
esac
