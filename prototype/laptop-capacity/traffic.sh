#!/usr/bin/env bash
# PROTOTYPE — throwaway. Light traffic, since the core layer has no load generator.
# Usage: ./traffic.sh <seconds>
set -u
END=$(( $(date +%s) + ${1:-120} ))
ok=0; err=0
while [ "$(date +%s)" -lt "$END" ]; do
  for ctx in binoculars telescopes accessories assembly; do
    c=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:8080/api/data?contextKeys=${ctx}" 2>/dev/null)
    [ "$c" = "200" ] && ok=$((ok+1)) || err=$((err+1))
  done
  curl -s -o /dev/null "http://localhost:8080/api/products" 2>/dev/null
  curl -s -o /dev/null "http://localhost:8080/api/recommendations?productIds=0PUK6V6EV0" 2>/dev/null
  sleep 1
done
echo "ad endpoint: ok=${ok} err=${err}"
