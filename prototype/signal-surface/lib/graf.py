#!/usr/bin/env python3
"""Grafana datasource-proxy client for ticket 27.

Every query goes through Grafana's datasource proxy rather than straight at
Loki/Prometheus/Tempo, because that is the only door a Run has (ADR 0007) and
this ticket is meant to verify what a Run can actually retrieve.

Standard library only. No heredoc-on-stdin (ticket 26's harness bug: a
`cmd | python3 - <<'PY'` lets the heredoc win stdin and the pipe is lost).

CLI:
    python3 lib/graf.py datasources
    python3 lib/graf.py prom-names [substr]
    python3 lib/graf.py prom <query>
    python3 lib/graf.py prom-label <label> [matcher]
    python3 lib/graf.py loki-label <label>
    python3 lib/graf.py loki <logql> [minutes] [limit]
    python3 lib/graf.py tempo-search <traceql> [minutes]
    python3 lib/graf.py tempo-tags
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("GRAFANA_BASE", "http://localhost:3000")
AUTH = os.environ.get("GRAFANA_AUTH", "admin:admin")
TIMEOUT = float(os.environ.get("GRAFANA_TIMEOUT", "30"))


def _req(path, params=None):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    tok = base64.b64encode(AUTH.encode()).decode()
    req.add_header("Authorization", "Basic " + tok)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read().decode("utf-8", "replace")
            code = r.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        code = e.code
    except Exception as e:  # noqa: BLE001 - surface the failure, do not mask it
        return {"ok": False, "error": repr(e), "ms": (time.time() - t0) * 1000}
    ms = (time.time() - t0) * 1000
    out = {"ok": 200 <= code < 300, "code": code, "ms": ms, "url": url}
    try:
        out["json"] = json.loads(body)
    except Exception:  # noqa: BLE001 - keep the raw text when it is not JSON
        out["text"] = body[:4000]
    return out


_DS_CACHE = None


def datasources():
    """type -> uid, as Grafana reports them."""
    global _DS_CACHE
    if _DS_CACHE is None:
        r = _req("/api/datasources")
        _DS_CACHE = {}
        for d in r.get("json", []) or []:
            _DS_CACHE.setdefault(d["type"], d["uid"])
            _DS_CACHE[d["name"].lower()] = d["uid"]
    return _DS_CACHE


def uid(kind):
    ds = datasources()
    for k in (kind, kind.lower()):
        if k in ds:
            return ds[k]
    return kind


def proxy(kind, path, params=None):
    return _req("/api/datasources/proxy/uid/%s%s" % (uid(kind), path), params)


# --- Prometheus -------------------------------------------------------------

def prom_query(q, when=None):
    p = {"query": q}
    if when:
        p["time"] = when
    return proxy("prometheus", "/api/v1/query", p)


def prom_range(q, start, end, step=30):
    return proxy("prometheus", "/api/v1/query_range",
                 {"query": q, "start": start, "end": end, "step": step})


def prom_names(matcher=None):
    p = {}
    if matcher:
        p["match[]"] = matcher
    r = proxy("prometheus", "/api/v1/label/__name__/values", p)
    return r.get("json", {}).get("data", []) or []


def prom_label(label, matcher=None):
    p = {}
    if matcher:
        p["match[]"] = matcher
    r = proxy("prometheus", "/api/v1/label/%s/values" % label, p)
    return r.get("json", {}).get("data", []) or []


def prom_scalars(q):
    """[(labels_dict, float_value)] from an instant query, or []."""
    r = prom_query(q)
    out = []
    for s in r.get("json", {}).get("data", {}).get("result", []) or []:
        try:
            out.append((s.get("metric", {}), float(s["value"][1])))
        except Exception:  # noqa: BLE001 - a NaN or missing sample is not fatal
            out.append((s.get("metric", {}), None))
    return out


# --- Loki -------------------------------------------------------------------

def loki_label(label, minutes=60):
    now = int(time.time() * 1e9)
    r = proxy("loki", "/loki/api/v1/label/%s/values" % label,
              {"start": now - minutes * 60 * int(1e9), "end": now})
    return r.get("json", {}).get("data", []) or []


def loki_labels(minutes=60):
    now = int(time.time() * 1e9)
    r = proxy("loki", "/loki/api/v1/labels",
              {"start": now - minutes * 60 * int(1e9), "end": now})
    return r.get("json", {}).get("data", []) or []


def loki_query(logql, minutes=10, limit=20):
    now = int(time.time() * 1e9)
    r = proxy("loki", "/loki/api/v1/query_range",
              {"query": logql, "limit": limit, "direction": "backward",
               "start": now - minutes * 60 * int(1e9), "end": now})
    return r


def loki_lines(logql, minutes=10, limit=20):
    """[(ns, line, stream_labels)] newest first, or []."""
    r = loki_query(logql, minutes, limit)
    out = []
    for s in r.get("json", {}).get("data", {}).get("result", []) or []:
        for v in s.get("values", []):
            out.append((v[0], v[1], s.get("stream", {})))
    out.sort(key=lambda x: x[0], reverse=True)
    return out


# --- Tempo ------------------------------------------------------------------

def tempo_search(traceql, minutes=15, limit=20):
    now = int(time.time())
    return proxy("tempo", "/api/search",
                 {"q": traceql, "start": now - minutes * 60, "end": now,
                  "limit": limit})


def tempo_tags():
    return proxy("tempo", "/api/v2/search/tags")


def tempo_trace(tid):
    return proxy("tempo", "/api/traces/%s" % tid)


# --- CLI --------------------------------------------------------------------

def _p(obj):
    print(json.dumps(obj, indent=2, default=str))


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "datasources":
        _p(datasources())
    elif cmd == "prom-names":
        names = prom_names()
        sub = rest[0] if rest else None
        if sub:
            names = [n for n in names if sub in n]
        print("\n".join(names))
        print("# %d names" % len(names), file=sys.stderr)
    elif cmd == "prom":
        _p(prom_query(rest[0]))
    elif cmd == "prom-label":
        print("\n".join(prom_label(rest[0], rest[1] if len(rest) > 1 else None)))
    elif cmd == "loki-label":
        print("\n".join(loki_label(rest[0])))
    elif cmd == "loki-labels":
        print("\n".join(loki_labels()))
    elif cmd == "loki":
        mins = int(rest[1]) if len(rest) > 1 else 10
        lim = int(rest[2]) if len(rest) > 2 else 20
        for ns, line, stream in loki_lines(rest[0], mins, lim):
            print("%s  %s" % (ns, line[:400]))
    elif cmd == "loki-raw":
        _p(loki_query(rest[0], int(rest[1]) if len(rest) > 1 else 10))
    elif cmd == "tempo-search":
        _p(tempo_search(rest[0], int(rest[1]) if len(rest) > 1 else 15))
    elif cmd == "tempo-tags":
        _p(tempo_tags())
    elif cmd == "tempo-trace":
        _p(tempo_trace(rest[0]))
    else:
        print("unknown: %s" % cmd, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
