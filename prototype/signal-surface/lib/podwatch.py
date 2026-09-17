#!/usr/bin/env python3
"""Sample pod memory, CPU and restart state to JSONL — items 7, 9 and 10.

Item 7: the email container's BASELINE RSS has never been measured here, and it
dominates every OOM estimate. Item 10: checkout sits at 18 Mi of a 20 Mi limit
with GOMEMLIMIT=16MiB and the payment Fault leaks a connection per failed order.
Item 9: after the first OOMKill, what a read-only Run can actually retrieve is
containerStatuses[].lastState.terminated.reason — not a Kubernetes Event.

    python3 lib/podwatch.py <label> <seconds> <interval> <prefix> [prefix...]
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAP = os.path.join(HERE, "capture")
NS = os.environ.get("NS", "otel-demo")


def kubectl_json(args):
    try:
        out = subprocess.run(["kubectl"] + args, capture_output=True, text=True,
                             timeout=45)
        return json.loads(out.stdout) if out.stdout.strip() else {}
    except Exception:  # noqa: BLE001
        return {}


def top():
    """pod -> (cpu_m, mem_mi). kubectl top needs metrics-server + --kubelet-insecure-tls."""
    out = {}
    try:
        r = subprocess.run(["kubectl", "top", "pod", "-n", NS, "--no-headers"],
                           capture_output=True, text=True, timeout=45)
        for line in r.stdout.splitlines():
            p = line.split()
            if len(p) >= 3:
                try:
                    out[p[0]] = (float(p[1].rstrip("m")), float(p[2].rstrip("Mi")))
                except ValueError:
                    pass
    except Exception:  # noqa: BLE001
        pass
    return out


def limits_for(pod_json, container):
    for c in pod_json.get("spec", {}).get("containers", []):
        if c["name"] == container:
            res = c.get("resources", {})
            env = {e["name"]: e.get("value") for e in c.get("env", []) if "value" in e}
            return {"limits": res.get("limits"), "requests": res.get("requests"),
                    "gomemlimit": env.get("GOMEMLIMIT"),
                    "probes": {k: bool(c.get(k)) for k in
                               ("livenessProbe", "readinessProbe", "startupProbe")}}
    return {}


def sample(prefixes, tops):
    pods = kubectl_json(["get", "pods", "-n", NS, "-o", "json"])
    rows = []
    for p in pods.get("items", []):
        name = p["metadata"]["name"]
        if not any(name.startswith(x) for x in prefixes):
            continue
        for cs in p.get("status", {}).get("containerStatuses") or []:
            term = (cs.get("lastState") or {}).get("terminated") or {}
            cur = (cs.get("state") or {}).get("running") or {}
            wait = (cs.get("state") or {}).get("waiting") or {}
            cpu, mem = tops.get(name, (None, None))
            rows.append({
                "pod": name, "container": cs["name"],
                "cpu_m": cpu, "mem_mi": mem,
                "ready": cs.get("ready"), "restarts": cs.get("restartCount", 0),
                "started_at": cur.get("startedAt"),
                "waiting_reason": wait.get("reason"),
                "last_terminated_reason": term.get("reason"),
                "last_exit_code": term.get("exitCode"),
                "last_started_at": term.get("startedAt"),
                "last_finished_at": term.get("finishedAt"),
                "spec": limits_for(p, cs["name"]),
            })
    return rows


def main(argv):
    if len(argv) < 4:
        print(__doc__)
        return 2
    label, total, interval, prefixes = argv[0], int(argv[1]), int(argv[2]), argv[3:]
    os.makedirs(CAP, exist_ok=True)
    path = os.path.join(CAP, "podwatch-%s.jsonl" % label)
    t0 = time.time()
    print("# podwatch %s: %s for %ss every %ss -> capture/podwatch-%s.jsonl"
          % (label, ",".join(prefixes), total, interval, label))
    print("%6s  %-34s %-10s %8s %8s %8s  %s"
          % ("t+s", "pod", "container", "cpu_m", "mem_Mi", "restarts", "lastTerminated"))
    peak = {}
    with open(path, "w") as f:
        while time.time() - t0 < total:
            el = int(time.time() - t0)
            tops = top()
            for r in sample(prefixes, tops):
                r["t_plus_seconds"] = el
                r["utc"] = time.strftime("%FT%TZ", time.gmtime())
                f.write(json.dumps(r) + "\n")
                key = (r["pod"], r["container"])
                if r["mem_mi"] is not None:
                    peak[key] = max(peak.get(key, 0), r["mem_mi"])
                print("%6d  %-34s %-10s %8s %8s %8s  %s"
                      % (el, r["pod"][:34], r["container"][:10],
                         r["cpu_m"] if r["cpu_m"] is not None else "-",
                         r["mem_mi"] if r["mem_mi"] is not None else "-",
                         r["restarts"],
                         "%s exit=%s at=%s" % (r["last_terminated_reason"],
                                               r["last_exit_code"],
                                               r["last_finished_at"])
                         if r["last_terminated_reason"] else ""))
            f.flush()
            sys.stdout.flush()
            time.sleep(interval)
    print("\n# peak memory observed")
    for (pod, c), m in sorted(peak.items()):
        print("   %-40s %-10s %.0f Mi" % (pod, c, m))
    print("# artifact: capture/podwatch-%s.jsonl" % label)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
