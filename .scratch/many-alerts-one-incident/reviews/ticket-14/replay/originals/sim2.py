import json
S = "/tmp/claude-501/-Users-jasonkrueger-projects-many-alerts-one-incident/091819f5-bb4c-41c7-a2e6-c2c6e2590647/scratchpad"
FAULTS = ["paymentUnreachable", "emailMemoryLeak", "cartFailure", "adFailure"]

def load(f): return [json.loads(l) for l in open(f"{S}/n-{f}.jsonl")]
def gkey(r):
    g = r["groupLabels"]; return (g.get("grafana_folder"), g.get("alertname"))

def simulate(rows, repeat, group_interval=10, deflap=False):
    """Count deliveries. deflap=True suppresses a resolve that is followed by the same
    fingerprint firing again later in the same Fault -- i.e. what C1 at 0.03/s would give."""
    if deflap:
        # fingerprints that resolve then fire again = flappers; treat them as firing throughout
        seen_resolved, flappers = set(), set()
        for r in rows:
            for a in r["body"]["alerts"]:
                if a["status"] == "resolved": seen_resolved.add(a["fingerprint"])
                elif a["fingerprint"] in seen_resolved: flappers.add(a["fingerprint"])
    last_sent, last_set, kept = {}, {}, 0
    final_resolve = {}
    if deflap:
        for i, r in enumerate(rows):
            for a in r["body"]["alerts"]:
                if a["fingerprint"] in flappers and a["status"] == "resolved": final_resolve[a["fingerprint"]] = i
    for i, r in enumerate(rows):
        alerts = r["body"]["alerts"]
        if deflap:
            s = frozenset((a["fingerprint"],
                           "firing" if (a["fingerprint"] in flappers and a["status"] == "resolved"
                                        and i != final_resolve[a["fingerprint"]]) else a["status"])
                          for a in alerts)
        else:
            s = frozenset((a["fingerprint"], a["status"]) for a in alerts)
        k, t = gkey(r), r["t"]
        if k not in last_sent:
            kept += 1; last_sent[k] = t; last_set[k] = s; continue
        if s != last_set[k] and t - last_sent[k] >= group_interval:
            kept += 1; last_sent[k] = t; last_set[k] = s
        elif t - last_sent[k] >= repeat:
            kept += 1; last_sent[k] = t; last_set[k] = s
    return kept

print("Notifications (= Runs, one per Notification) with repeats OFF:")
print(f"{'':>26} | " + " | ".join(f"{f[:14]:>14}" for f in FAULTS) + " | worst @370s")
for deflap, label in [(False,"C1 at 0.1/s (as measured)"), (True,"C1 at 0.03/s (flap gone)")]:
    c = [simulate(load(f), 10**9, deflap=deflap) for f in FAULTS]
    print(f"{label:>26} | " + " | ".join(f"{x:>14}" for x in c) + f" | {max(c)*370/60:>7.0f} min")
