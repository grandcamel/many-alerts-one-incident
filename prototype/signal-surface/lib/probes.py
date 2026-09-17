"""Every probe the chart declares, from `kubectl get deploy -o json`."""
import json, sys

def fmt(p):
    if not p:
        return "-"
    for k in ("httpGet", "grpc", "tcpSocket", "exec"):
        if k in p:
            v = p[k]
            detail = v.get("path") or v.get("command") or ""
            return f"{k}:{detail}@{v.get('port')}"
    return "?"

d = json.load(sys.stdin)
shared = []
for dep in d.get("items", []):
    name = dep["metadata"]["name"]
    for c in dep["spec"]["template"]["spec"]["containers"]:
        r, l, s = c.get("readinessProbe"), c.get("livenessProbe"), c.get("startupProbe")
        if not (r or l or s):
            continue
        print(f"  {name}/{c['name']}")
        print(f"     readiness={fmt(r)}")
        print(f"     liveness ={fmt(l)}")
        print(f"     startup  ={fmt(s)}")
        if r and l and fmt(r) == fmt(l):
            print("     !! liveness SHARES the readiness endpoint -> a failed readiness probe WILL restart this container")
            shared.append(f"{name}/{c['name']}")
print()
print(f"  containers where liveness shares the readiness endpoint: {shared or 'NONE'}")
print("  (if NONE, the restart count is the wrong signal to hunt for failedReadinessProbe)")
