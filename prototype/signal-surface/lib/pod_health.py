"""OOMKilled / Evicted / Pending, read from `kubectl get pods -A -o json`."""
import json, sys
d = json.load(sys.stdin)
hits = 0
for p in d.get("items", []):
    ns, name = p["metadata"]["namespace"], p["metadata"]["name"]
    st = p.get("status", {})
    for cs in (st.get("containerStatuses") or []) + (st.get("initContainerStatuses") or []):
        for key in ("state", "lastState"):
            t = (cs.get(key) or {}).get("terminated") or {}
            if t.get("reason") in ("OOMKilled", "Error", "ContainerStatusUnknown"):
                print(f"  {ns}/{name}/{cs['name']}: {key}.terminated={t['reason']} exit={t.get('exitCode')}")
                hits += 1
        w = (cs.get("state") or {}).get("waiting") or {}
        if w.get("reason") in ("CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull"):
            print(f"  {ns}/{name}/{cs['name']}: waiting={w['reason']}")
            hits += 1
    if st.get("reason") == "Evicted":
        print(f"  EVICTED {ns}/{name}: {st.get('message','')}")
        hits += 1
    for c in (st.get("conditions") or []):
        if c.get("reason") == "Unschedulable":
            print(f"  UNSCHEDULABLE {ns}/{name}: {c.get('message','')}")
            hits += 1
print("  none" if not hits else f"  ({hits} hit(s))")
