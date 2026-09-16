#!/usr/bin/env bash
# PROTOTYPE — throwaway. Ticket 08, "Can the laptop hold it".
# Records one stage's numbers. Usage: ./measure.sh <stage-label>
set -u
STAGE="${1:?usage: measure.sh <stage-label>}"
OUT="$(cd "$(dirname "$0")" && pwd)/results/${STAGE}.txt"

{
  echo "# stage: ${STAGE}"
  echo "# recorded: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo
  echo "## docker desktop kubernetes"
  docker desktop kubernetes status 2>&1 | sed 's/^/  /'
  echo
  echo "## VM memory (/proc/meminfo as seen from inside the VM)"
  docker run --rm alpine:3.20 sh -c 'grep -E "^(MemTotal|MemFree|MemAvailable|Cached|SwapTotal|SwapFree):" /proc/meminfo' 2>&1 | sed 's/^/  /'
  echo
  echo "## VM cpu count"
  docker run --rm alpine:3.20 nproc 2>&1 | sed 's/^/  /'
  echo
  echo "## containers running: $(docker ps -q | wc -l | tr -d ' ')"
  echo
  echo "## docker stats"
  docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.CPUPerc}}' 2>&1 | sed 's/^/  /'
  echo
  echo "## container memory total (MiB, sum of docker stats usage)"
  docker stats --no-stream --format '{{.MemUsage}}' 2>/dev/null \
    | awk -F' / ' '{print $1}' \
    | awk '/GiB/{s+=$1*1024; next} /MiB/{s+=$1; next} /KiB/{s+=$1/1024; next} /B$/{s+=$1/1048576} END{printf "  %.0f MiB across NR=%d\n", s, NR}'
} > "$OUT" 2>&1

echo "wrote $OUT"
grep -E 'MemTotal|MemAvailable|containers running|across NR' "$OUT"
