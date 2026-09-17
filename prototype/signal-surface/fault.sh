#!/usr/bin/env bash
# One Fault window, end to end — ticket 27 items 7 to 13 plus the timing half
# that needs no Alert rules.
#
#   ./fault.sh inject <flag> <variant> <window_min> <pod_prefix...>
#   ./fault.sh undo   <flag> <service_to_restart>
#
# The order is deliberate and is item 13's whole point: flip, prove flagd holds
# it, then prove a REAL SYMPTOM before any clock is trusted. Only the Java flagd
# provider's reconnect after a rollout has ever been verified here; a wedged .NET
# or Go channel falls back to the code default and the Fault silently never
# fires, which would make every number after it a measurement of nothing.
set -euo pipefail

NS="${NS:-otel-demo}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CAP="$HERE/capture"
mkdir -p "$CAP"
say() { echo; echo "=== $* ==="; }

case "${1:-help}" in

inject)
  FLAG="${2:?flag}"; VARIANT="${3:?variant}"; WINDOW_MIN="${4:-12}"; shift 4 || true
  PREFIXES=("$@"); [ ${#PREFIXES[@]} -gt 0 ] || PREFIXES=("checkout")
  WINDOW=$((WINDOW_MIN * 60))
  LOG="$CAP/window-$FLAG-$VARIANT.log"
  exec > >(tee "$LOG") 2>&1

  say "FAULT WINDOW: $FLAG -> $VARIANT for ${WINDOW_MIN} min; watching ${PREFIXES[*]}"
  echo "utc: $(date -u +%FT%TZ)"

  # A baseline sample BEFORE the flip. Item 7 says the email container's
  # baseline RSS has never been measured and dominates every OOM estimate.
  say "pre-flip baseline for ${PREFIXES[*]} (60 s)"
  python3 "$HERE/lib/podwatch.py" "$FLAG-baseline" 60 20 "${PREFIXES[@]}" || true

  T0=$(date +%s)
  say "injecting"
  "$HERE/flag.sh" "$FLAG" "$VARIANT"

  # podwatch runs for the whole window in the background; the symptom watch and
  # the probes run against the same window in the foreground.
  python3 "$HERE/lib/podwatch.py" "$FLAG-window" "$WINDOW" 20 "${PREFIXES[@]}" \
    > "$CAP/podwatch-$FLAG-window.log" 2>&1 &
  PW=$!
  trap 'kill $PW 2>/dev/null || true' EXIT

  say "item 13 — confirm one real symptom before trusting any clock"
  python3 "$HERE/lib/symptom.py" "$FLAG" "$T0" $((WINDOW > 900 ? 900 : WINDOW)) 15 || true

  # The alertable conditions are written on [5m] rates, so a probe fired the
  # instant a symptom appears reads a window that is mostly pre-fault. Wait for
  # the rate window to fill before recording the numbers ticket 28 will use.
  say "letting the [5m] rate windows fill before probing"
  sleep 300

  say "items 9 to 12 — ticket 10's queries, run against the live Fault"
  python3 "$HERE/lib/faultprobe.py" "$FLAG" "on" || true

  say "waiting out the rest of the window"
  wait $PW 2>/dev/null || true
  trap - EXIT

  say "end-of-window state"
  python3 "$HERE/lib/faultprobe.py" "$FLAG" "end" || true
  echo "window log: capture/window-$FLAG-$VARIANT.log"
  ;;

undo)
  FLAG="${2:?flag}"; SVC="${3:-}"
  say "undo: $FLAG -> off"
  "$HERE/flag.sh" "$FLAG" off
  if [ -n "$SVC" ]; then
    # Ticket 10: nothing is idempotent across flips. Every chosen Fault leaves
    # undisposed connections or a poisoned in-process cache behind, so each
    # undo restarts its service — the flip alone does not clear it.
    say "rollout restart deploy/$SVC (the flip alone does not clear it)"
    kubectl rollout restart -n "$NS" "deploy/$SVC"
    kubectl rollout status -n "$NS" "deploy/$SVC" --timeout=5m
  fi
  say "recovery check (90 s)"
  sleep 90
  python3 "$HERE/lib/faultprobe.py" "$FLAG" "recovered" || true
  ;;

help|*)
  sed -n '2,14p' "$0"
  ;;
esac
