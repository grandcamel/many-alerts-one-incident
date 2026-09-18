import json, sys

CAP="/private/tmp/claude-501/-Users-jasonkrueger-projects-many-alerts-one-incident/091819f5-bb4c-41c7-a2e6-c2c6e2590647/scratchpad/cap/"

def load(f):
    out=[]
    for line in open(CAP+f):
        line=line.strip()
        if not line: continue
        out.append(json.loads(line))
    return out

def gkey(d):
    gl=d["groupLabels"]
    return (gl.get("grafana_folder"), gl.get("alertname"))

def sets(d):
    firing=set(); resolved=set()
    for a in d["body"]["alerts"]:
        if a["status"]=="firing": firing.add(a["fingerprint"])
        else: resolved.add(a["fingerprint"])
    return firing, resolved

def needs_update(entry, firing, resolved, repeat, now):
    if entry is None:
        return len(firing)>0, "first"
    if not firing <= entry["firing"]:
        return True, "new-firing"
    if len(firing)==0:
        return len(entry["firing"])>0, "all-resolved"
    if not resolved <= entry["resolved"]:
        return True, "new-resolved"
    if entry["ts"] < now - repeat:
        return True, "repeat"
    return False, "-"

def replay(f, repeat, t0=None, tundo=None, verbose=False):
    ds=load(f)
    entries={}
    kept=[]
    for d in ds:
        k=gkey(d); firing,resolved=sets(d); now=d["t"]
        ok,why=needs_update(entries.get(k), firing, resolved, repeat, now)
        if ok:
            entries[k]={"firing":set(firing),"resolved":set(resolved),"ts":now}
            kept.append((d,why,firing,resolved))
    if verbose:
        for d,why,firing,resolved in kept:
            rel = f"{d['t']-t0:+.0f}" if t0 else d["utc"]
            print(f"  {rel:>8} {d['groupLabels']['alertname'][:34]:34} st={d['status']:8} n={d['n_alerts']} F={len(firing)} R={len(resolved)} why={why}")
    return len(ds), len(kept)

for f,t0,tundo in [("notifications-paymentUnreachable.jsonl",1789681945,1789682809),
                   ("notifications-emailMemoryLeak.jsonl",1789683484,1789684585)]:
    print("="*70); print(f)
    for r in (60,300,600):
        tot,k=replay(f,r)
        print(f"  repeat={r:4}s : {tot} -> {k}")
    for r in (300,600):
        print(f"  --- detail repeat={r}s (fault-relative, undo at +{tundo-t0}) ---")
        replay(f,r,t0=t0,verbose=True)
