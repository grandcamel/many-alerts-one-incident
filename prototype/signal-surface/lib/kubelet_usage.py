"""Per-pod memory/CPU from the kubelet's own /metrics/resource endpoint.

DOKS 1.36.3-do.5 ships no metrics-server, so `kubectl top` returns
"Metrics API not available". The kubelet still exports the same underlying
numbers, so this reads them directly and needs nothing installed.

stdin: output of `kubectl get --raw /api/v1/nodes/<node>/proxy/metrics/resource`
"""
import collections, re, sys

mem = collections.defaultdict(float)
cpu = collections.defaultdict(float)
node_mem = node_cpu = 0.0
pat = re.compile(r'^(\w+)(?:\{([^}]*)\})?\s+([0-9.e+-]+)')


def labels(s):
    return dict(re.findall(r'(\w+)="([^"]*)"', s))


for line in sys.stdin:
    m = pat.match(line)
    if not m:
        continue
    name, lab, val = m.group(1), labels(m.group(2) or ""), float(m.group(3))
    if name == "container_memory_working_set_bytes":
        mem[(lab.get("namespace"), lab.get("pod"))] += val
    elif name == "container_cpu_usage_seconds_total":
        cpu[(lab.get("namespace"), lab.get("pod"))] += val
    elif name == "node_memory_working_set_bytes":
        node_mem = val

total = sum(mem.values())
print(f"  node working set: {node_mem/2**30:.2f} GiB")
print(f"  sum of containers: {total/2**30:.2f} GiB across {len(mem)} pods")
print()
print("  top 25 pods by memory working set:")
for (ns, pod), v in sorted(mem.items(), key=lambda kv: -kv[1])[:25]:
    print(f"    {v/2**20:8.0f} Mi  {ns}/{pod}")
