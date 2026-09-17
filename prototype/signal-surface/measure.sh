#!/usr/bin/env bash
# Snapshot the cluster's state into results/<stage>.txt. One file per stage,
# same shape as ticket 08's harness so the two are readable side by side.
set -uo pipefail

STAGE="${1:?usage: ./measure.sh <stage-label>}"
NS="${NS:-otel-demo}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$HERE/results/$STAGE.txt"

exec > >(tee "$OUT") 2>&1

echo "# stage: $STAGE"
echo "# utc:   $(date -u +%FT%TZ)"

echo
echo "=== node capacity / allocatable ==="
kubectl get nodes -o custom-columns=\
'NAME:.metadata.name,CPU-CAP:.status.capacity.cpu,CPU-ALLOC:.status.allocatable.cpu,MEM-CAP:.status.capacity.memory,MEM-ALLOC:.status.allocatable.memory,PODS:.status.allocatable.pods,KUBELET:.status.nodeInfo.kubeletVersion'

echo
echo "=== allocated (requests/limits vs allocatable) ==="
for n in $(kubectl get nodes -o name); do
  kubectl describe "$n" | sed -n '/Allocated resources/,/^Events/p' | head -20
done

echo
echo "=== node usage (metrics-server) ==="
kubectl top nodes 2>&1 || echo "(kubectl top nodes unavailable)"

echo
echo "=== pod usage, top 30 by memory ==="
kubectl top pods -A --sort-by=memory 2>&1 | head -31 || echo "(kubectl top pods unavailable)"

echo
echo "=== total container memory in use (all namespaces) ==="
kubectl top pods -A --no-headers 2>/dev/null \
  | awk '{gsub(/Mi/,"",$4); s+=$4} END {printf "%.0f Mi across %d pods\n", s, NR}' \
  || echo "(unavailable)"

echo
echo "=== pod phases ==="
kubectl get pods -A --no-headers 2>/dev/null | awk '{print $4}' | sort | uniq -c | sort -rn

echo
echo "=== not Running/Completed ==="
kubectl get pods -A 2>/dev/null | awk 'NR==1 || ($4!="Running" && $4!="Completed")'

echo
echo "=== restarts > 0 ==="
kubectl get pods -A --no-headers 2>/dev/null | awk '$5+0 > 0 {print $1"/"$2"  restarts="$5"  "$4}' || true

echo
echo "=== OOMKilled / Evicted / FailedScheduling ==="
kubectl get pods -A -o json 2>/dev/null | python3 "$HERE/lib/pod_health.py" || echo "  (unavailable)"

echo
echo "=== recent warning events ==="
kubectl get events -A --field-selector type=Warning \
  --sort-by=.lastTimestamp -o custom-columns=\
'TIME:.lastTimestamp,NS:.metadata.namespace,REASON:.reason,OBJECT:.involvedObject.name,MSG:.message' 2>/dev/null | tail -25

echo
echo "=== disk on the node ==="
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"  ephemeral-storage allocatable="}{.status.allocatable.ephemeral-storage}{"\n"}{end}'
kubectl describe nodes 2>/dev/null | grep -E 'DiskPressure|MemoryPressure|PIDPressure' | sort | uniq -c

echo
echo "# end $STAGE"

echo
echo "=== kubelet working set (no metrics-server needed) ==="
for n in $(kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}'); do
  echo "  node $n:"
  kubectl get --raw "/api/v1/nodes/$n/proxy/metrics/resource" 2>/dev/null \
    | python3 "$HERE/lib/kubelet_usage.py" || echo "    (kubelet metrics unavailable)"
done

echo
echo "# end $STAGE (kubelet pass)"

echo
echo "=== NODE-level truth (kubelet /stats/summary, not a container sum) ==="
for n in $(kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}'); do
  kubectl get --raw "/api/v1/nodes/$n/proxy/stats/summary" 2>/dev/null \
    | python3 "$HERE/lib/node_summary.py" || echo "  (unavailable)"
done
