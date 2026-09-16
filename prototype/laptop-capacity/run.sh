#!/usr/bin/env bash
# PROTOTYPE — throwaway. Ticket 08, "Can the laptop hold it".
# One command. Usage: ./run.sh pull | up | down | flag <name> <on|off>
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DEMO="${DEMO:-/private/tmp/claude-501/-Users-jasonkrueger-projects-many-alerts-one-incident/643337f8-fd73-44db-b4b7-9ca3d8bbf38e/scratchpad/otel-demo}"
mapfile -t SERVICES < <(grep -v '^[[:space:]]*$' "$HERE/services.txt")
export DEMO_VERSION=3.0.0
COMPOSE=(docker compose -f "$DEMO/compose.yaml" -f "$HERE/compose.lgtm.yaml")

case "${1:-}" in
  pull)
    # Chain the demo's collector into LGTM via the documented extras seam.
    cp "$HERE/otelcol-config-extras.yml" "$DEMO/src/otel-collector/otelcol-config-extras.yml"
    cd "$DEMO" && "${COMPOSE[@]}" pull "${SERVICES[@]}"
    ;;
  up)
    cp "$HERE/otelcol-config-extras.yml" "$DEMO/src/otel-collector/otelcol-config-extras.yml"
    cd "$DEMO" && "${COMPOSE[@]}" up -d --no-build "${SERVICES[@]}"
    ;;
  down)
    cd "$DEMO" && "${COMPOSE[@]}" down --remove-orphans
    ;;
  flag)
    # Flip a fault flag: ./run.sh flag adServiceFailure on
    f="${2:?flag name}"; v="${3:?on|off}"
    [ "$v" = on ] && d=on || d=off
    yq e -i ".flags.\"${f}\".defaultVariant = \"${d}\"" "$DEMO/src/flagd/demo.flagd.json"
    echo "set ${f} -> ${d}"; yq e ".flags.\"${f}\"" "$DEMO/src/flagd/demo.flagd.json"
    ;;
  *) echo "usage: $0 pull|up|down|flag <name> <on|off>"; exit 1 ;;
esac
