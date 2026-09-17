#!/usr/bin/env bash
# Flip a fault flag — the WHOLE flip, as ticket 26 found it actually works.
#
# The ConfigMap write alone is inert: the chart mounts flagd-config only into an
# init container that does a one-shot `cp` into an emptyDir, and the Deployment
# carries no checksum/config annotation. The working flip is the ConfigMap edit
# PLUS `kubectl rollout restart deploy/flagd`. This script does both and then
# proves the new variant is live INSIDE the pod, because ticket 10's trap list
# is explicit that verifying flagd is not verifying the caller — and the
# ConfigMap agreeing with itself is not evidence of anything.
#
# Timestamps for every step go to capture/timing-<flag>-<variant>.json, which is
# the injection -> rollout half of the timing budget.
set -euo pipefail

NS="${NS:-otel-demo}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CAP="$HERE/capture"
mkdir -p "$CAP"

now()  { date -u +%FT%T.%3NZ 2>/dev/null || date -u +%FT%TZ; }
epoch(){ date +%s; }

CM=$(kubectl get cm -n "$NS" -o json | python3 -c \
  'import json,sys;d=json.load(sys.stdin);print(next((c["metadata"]["name"] for c in d["items"] if any(k.endswith(".json") and "flags" in (c["data"][k] or "") for k in (c.get("data") or {}))),""))')
[ -n "$CM" ] || { echo "FATAL: no flagd ConfigMap in $NS" >&2; exit 1; }

KEY=$(kubectl get cm -n "$NS" "$CM" -o json | python3 -c \
  'import json,sys;d=json.load(sys.stdin);print(next(k for k in d["data"] if k.endswith(".json")))')

if [ "${1:-}" = "--list" ]; then
  echo "configmap=$CM key=$KEY"
  kubectl get cm -n "$NS" "$CM" -o json | python3 "$HERE/lib/list_flags.py"
  exit 0
fi

# --in-pod: what does flagd ACTUALLY hold right now? No flip.
if [ "${1:-}" = "--in-pod" ]; then
  echo "# flagd's own copy, read from the emptyDir inside the pod"
  kubectl exec -n "$NS" deploy/flagd -c flagd-ui -- cat /app/data/demo.flagd.json 2>/dev/null \
    | python3 "$HERE/lib/in_pod_flags.py" \
    || echo "  (flagd-ui exec failed — flagd v0.16.0 is distroless, there is no shell in the flagd container)"
  exit 0
fi

FLAG="${1:?usage: ./flag.sh <flagName> <variant|on|off>   (or --list / --in-pod)}"
STATE="${2:?usage: ./flag.sh <flagName> <variant|on|off>   (or --list / --in-pod)}"

T_START=$(epoch); TS_START=$(now)
RV_BEFORE=$(kubectl get cm -n "$NS" "$CM" -o jsonpath='{.metadata.resourceVersion}')
echo "configmap=$CM key=$KEY resourceVersion(before)=$RV_BEFORE"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
kubectl get cm -n "$NS" "$CM" -o json \
  | KEY="$KEY" FLAG="$FLAG" STATE="$STATE" python3 "$HERE/lib/flagd_config.py" > "$TMP/out.json"

OLD=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["old"])' "$TMP/out.json")
WANT=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["new"])' "$TMP/out.json")
WANTV=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["want_value"])' "$TMP/out.json")
python3 -c 'import json,sys;json.dump(json.load(open(sys.argv[1]))["config"],open(sys.argv[2],"w"),indent=2)' \
  "$TMP/out.json" "$TMP/$KEY"

kubectl create cm "$CM" -n "$NS" --from-file="$KEY=$TMP/$KEY" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null
T_CM=$(epoch); TS_CM=$(now)

RV_AFTER=$(kubectl get cm -n "$NS" "$CM" -o jsonpath='{.metadata.resourceVersion}')
echo "$FLAG: $OLD -> $WANT (value=$WANTV)"
echo "resourceVersion: $RV_BEFORE -> $RV_AFTER (changed: $([ "$RV_BEFORE" != "$RV_AFTER" ] && echo yes || echo NO))"

# --- the half ticket 26 found missing ---------------------------------------
echo
echo "=== rollout restart deploy/flagd (the ConfigMap write alone is inert) ==="
kubectl rollout restart -n "$NS" deploy/flagd
kubectl rollout status -n "$NS" deploy/flagd --timeout=5m
T_ROLLOUT=$(epoch); TS_ROLLOUT=$(now)

# --- prove it landed INSIDE the pod -----------------------------------------
echo
echo "=== flagd's own copy, after the rollout ==="
IN_POD=$(kubectl exec -n "$NS" deploy/flagd -c flagd-ui -- cat /app/data/demo.flagd.json 2>/dev/null || echo "")
if [ -n "$IN_POD" ]; then
  echo "$IN_POD" | FLAG="$FLAG" python3 "$HERE/lib/in_pod_flags.py"
  LIVE=$(echo "$IN_POD" | FLAG="$FLAG" python3 -c \
    'import json,os,sys;print(json.load(sys.stdin)["flags"][os.environ["FLAG"]].get("defaultVariant"))' 2>/dev/null || echo "?")
else
  echo "  (could not read the in-pod copy)"
  LIVE="?"
fi
echo "in-pod defaultVariant for $FLAG: $LIVE  (wanted: $WANT)"
[ "$LIVE" = "$WANT" ] && echo "VERIFIED: flagd holds the new variant" \
                      || echo "!! NOT VERIFIED: flagd does not hold $WANT"

cat > "$CAP/timing-$FLAG-$WANT.json" <<JSON
{
  "flag": "$FLAG", "from": "$OLD", "to": "$WANT", "value": "$WANTV",
  "configmap": "$CM", "rv_before": "$RV_BEFORE", "rv_after": "$RV_AFTER",
  "in_pod_variant": "$LIVE", "verified": $([ "$LIVE" = "$WANT" ] && echo true || echo false),
  "t_start_epoch": $T_START, "t_configmap_epoch": $T_CM, "t_rollout_done_epoch": $T_ROLLOUT,
  "ts_start": "$TS_START", "ts_configmap": "$TS_CM", "ts_rollout_done": "$TS_ROLLOUT",
  "configmap_write_seconds": $((T_CM - T_START)),
  "flagd_rollout_seconds": $((T_ROLLOUT - T_CM)),
  "injection_to_flagd_ready_seconds": $((T_ROLLOUT - T_START))
}
JSON
echo
echo "injection -> flagd ready: $((T_ROLLOUT - T_START))s (ConfigMap $((T_CM - T_START))s + rollout $((T_ROLLOUT - T_CM))s)"
echo "timing artifact: capture/timing-$FLAG-$WANT.json"
echo
echo "NOTE: flagd holding the variant is NOT the caller holding it. The .NET and Go"
echo "      providers' reconnect after a flagd rollout has never been verified here."
echo "      Confirm one real symptom (./symptom.sh) before starting any clock."
