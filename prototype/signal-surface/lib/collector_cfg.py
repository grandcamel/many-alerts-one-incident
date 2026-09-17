"""Grep every ConfigMap's collector config for event-receiver evidence."""
import json, re, sys
d = json.load(sys.stdin)
found = False
for cm in d.get("items", []):
    for k, v in (cm.get("data") or {}).items():
        if not isinstance(v, str) or "receivers" not in v:
            continue
        hits = [l for l in v.splitlines() if re.search(r"k8sobjects|k8s_events|kubernetesEvents|k8s_cluster", l)]
        if hits:
            found = True
            print(f"  {cm['metadata']['name']}/{k}:")
            for h in hits:
                print("     ", h.strip())
if not found:
    print("  NO k8sobjects / k8s_events receiver in any ConfigMap -> Kubernetes Events are NOT being collected")
