"""The harness's own readiness gate. stdin: `kubectl get pods -n <ns> -o json`.

Ticket 26: `helm upgrade --install --wait --timeout 20m` exited 0 after 90
seconds with a collector in CrashLoopBackOff. helm's exit code is not proof of
health, so this asks the cluster directly: every container Ready, nothing
waiting on a backoff, nothing restarting.

Prints one status line, and ALL-READY on the last line when it is true.
"""
import json
import sys

d = json.load(sys.stdin)
total = ready = 0
bad = []
for p in d.get("items", []):
    name = p["metadata"]["name"]
    st = p.get("status", {})
    css = st.get("containerStatuses") or []
    if not css:
        bad.append("%s: no containerStatuses (phase=%s)" % (name, st.get("phase")))
        total += 1
        continue
    for cs in css:
        total += 1
        if cs.get("ready"):
            ready += 1
        else:
            w = (cs.get("state") or {}).get("waiting") or {}
            t = (cs.get("state") or {}).get("terminated") or {}
            bad.append("%s/%s: ready=false %s%s restarts=%s"
                       % (name, cs["name"],
                          w.get("reason", ""), t.get("reason", ""),
                          cs.get("restartCount", 0)))
        if cs.get("restartCount", 0) > 0:
            bad.append("%s/%s: restarts=%s" % (name, cs["name"], cs["restartCount"]))

for b in bad[:25]:
    print("  " + b)
print("  %d/%d containers ready, %d complaint(s)" % (ready, total, len(bad)))
if total and ready == total and not bad:
    print("ALL-READY")
