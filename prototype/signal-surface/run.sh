#!/usr/bin/env bash
# PROTOTYPE harness for ticket 27 — verify the signal surface, settle the Fault
# gates. Extends ticket 26's harness (prototype/doks-chart-capacity) with the
# three fixes that ticket found: the flagd rollout restart, metrics-server with
# --kubelet-insecure-tls, and its own readiness gate, because helm --wait exited
# 0 over a crashlooping pod.
# Throwaway. Not production.
set -euo pipefail

CLUSTER="${CLUSTER:-maoi-signal}"
REGION="${REGION:-nyc3}"
SIZE="${SIZE:-s-8vcpu-16gb}"
NODES="${NODES:-1}"
K8S="${K8S:-1.36.3-do.5}"
CHART_VERSION="${CHART_VERSION:-0.41.2}"
NS="${NS:-otel-demo}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

die() { echo "FATAL: $*" >&2; exit 1; }
say() { echo; echo "=== $* ==="; }

case "${1:-help}" in

cluster-create)
  # ADR 0007's runbook rule, enforced rather than remembered: never without
  # --ha=false, --size and --count. Omitting --ha defaults HA ON at $40/mo,
  # prorated and irreversible; omitting the others gives 3x s-1vcpu-2gb-intel.
  say "creating $CLUSTER: $NODES x $SIZE, $K8S, $REGION, ha=false"
  time doctl kubernetes cluster create "$CLUSTER" \
    --region "$REGION" \
    --version "$K8S" \
    --ha=false \
    --node-pool "name=pool;size=$SIZE;count=$NODES;auto-scale=false" \
    --wait
  kubectl config current-context
  ;;

cluster-delete)
  say "DESTROYING $CLUSTER"
  doctl kubernetes cluster delete "$CLUSTER" --force --dangerous
  say "surviving DO resources (should be none of ours)"
  doctl kubernetes cluster list
  doctl compute load-balancer list
  doctl compute volume list
  ;;

repo)
  helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
  helm repo add grafana https://grafana.github.io/helm-charts
  helm repo update
  ;;

show-values)
  helm show values open-telemetry/opentelemetry-demo --version "$CHART_VERSION"
  ;;

install-demo)
  say "installing opentelemetry-demo $CHART_VERSION into $NS"
  kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -
  time helm upgrade --install otel-demo open-telemetry/opentelemetry-demo \
    --version "$CHART_VERSION" \
    --namespace "$NS" \
    --values "$HERE/values-demo.yaml" \
    --timeout 20m --wait
  ;;

install-lgtm)
  say "installing the LGTM stack into $NS"
  kubectl apply -n "$NS" -f "$HERE/lgtm.yaml"
  kubectl rollout status -n "$NS" deploy/lgtm --timeout=15m
  ;;

install-receiver)
  # Stands in for the Receiver + one Run at this repo's own 2 GiB cap.
  say "installing the receiver/run placeholder (2Gi cap)"
  kubectl apply -n "$NS" -f "$HERE/receiver.yaml"
  kubectl rollout status -n "$NS" deploy/receiver --timeout=10m
  ;;

metrics-server)
  # DOKS 1.36.3-do.5 ships NO metrics-server, and the upstream manifest is not
  # sufficient on its own — it rolls out and still fails. It needs
  # --kubelet-insecure-tls (ticket 26). Without this, `kubectl top` is dead and
  # items 7 and 10 cannot be measured at all.
  say "installing metrics-server with --kubelet-insecure-tls"
  kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
  kubectl patch -n kube-system deploy/metrics-server --type=json \
    -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
  kubectl rollout status -n kube-system deploy/metrics-server --timeout=5m
  say "waiting for kubectl top to actually answer"
  for i in $(seq 1 30); do
    if kubectl top pod -n "$NS" --no-headers >/dev/null 2>&1; then
      echo "kubectl top answers after ${i} attempt(s)"; break
    fi
    sleep 10
  done
  kubectl top node
  ;;

ready)
  # Ticket 26: `helm upgrade --install --wait --timeout 20m` exited 0 after 90
  # seconds with a collector in CrashLoopBackOff. helm's exit code is not proof
  # of health, so this is the harness's own gate.
  say "readiness gate: every pod Ready, zero restarts, nothing waiting"
  for i in $(seq 1 60); do
    OUT=$(kubectl get pods -n "$NS" -o json | python3 "$HERE/lib/pod_ready.py") || true
    echo "$OUT" | tail -1
    if echo "$OUT" | grep -q '^ALL-READY'; then
      echo "$OUT"; exit 0
    fi
    sleep 15
  done
  echo "!! not all pods ready after 15 minutes"
  kubectl get pods -n "$NS"
  exit 1
  ;;

pf)
  # One long-lived port-forward for the whole session. Grafana is the only door
  # a Run has (ADR 0007), so every query in this harness goes through it.
  pkill -f "port-forward.*svc/lgtm" 2>/dev/null || true
  sleep 1
  kubectl port-forward -n "$NS" svc/lgtm 3000:3000 >/tmp/maoi-pf.log 2>&1 &
  echo $! > /tmp/maoi-pf.pid
  sleep 4
  curl -sS -u admin:admin -o /dev/null -w 'grafana /api/health: %{http_code} in %{time_total}s\n' \
    http://localhost:3000/api/health
  ;;

pf-stop)
  pkill -f "port-forward.*svc/lgtm" 2>/dev/null || true
  rm -f /tmp/maoi-pf.pid
  echo "port-forward stopped"
  ;;

flag)
  # $2 = flag name, $3 = variant|on|off. The ConfigMap write ALONE IS INERT —
  # flag.sh does the rollout restart and verifies the in-pod copy.
  "$HERE/flag.sh" "${2:?flag name}" "${3:?variant|on|off}"
  ;;

help|*)
  cat <<USAGE
usage: ./run.sh <cmd>
  cluster-create    doctl create, guarded (COSTS MONEY)
  cluster-delete    doctl delete + orphan sweep
  repo              helm repo add/update
  show-values       dump the chart's real values
  install-demo      chart $CHART_VERSION with values-demo.yaml
  install-lgtm      the LGTM stack in-cluster
  install-receiver  receiver/Run placeholder at 2Gi
  metrics-server    metrics-server + --kubelet-insecure-tls (kubectl top)
  ready             our own readiness gate; helm --wait is not one
  pf / pf-stop      port-forward Grafana to localhost:3000
  flag NAME VARIANT flip a flag: ConfigMap write + flagd rollout + verify
USAGE
  ;;
esac
