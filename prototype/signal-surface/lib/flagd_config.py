"""Flip a flag's defaultVariant in the flagd ConfigMap JSON. stdin: the ConfigMap.

STATE is either an exact variant name ("1000x", "70", "on", "off") or the word
"on", which picks the largest non-off variant. Ticket 27 needs exact variants —
`emailMemoryLeak` at `1000x` and `cartFailure` at a percentage — so an exact
name wins over the heuristic whenever the flag actually has it.
"""
import json, os, sys
d = json.load(sys.stdin)
key, flag, state = os.environ["KEY"], os.environ["FLAG"], os.environ["STATE"]
cfg = json.loads(d["data"][key])
flags = cfg["flags"]
if flag not in flags:
    sys.exit(f"FATAL: flag {flag!r} not in config. have: {', '.join(sorted(flags))}")
variants = flags[flag]["variants"]
if state in variants:
    want = state
elif state == "on":
    cands = [v for v in variants if v != "off"]
    if not cands:
        sys.exit(f"FATAL: flag {flag!r} has no non-off variant: {variants}")
    try:
        want = max(cands, key=lambda v: float(variants[v]))
    except (TypeError, ValueError):
        want = cands[0]
elif state == "off":
    want = "off"
else:
    sys.exit(f"FATAL: variant {state!r} not on flag {flag!r}. have: {list(variants)}")
old = flags[flag].get("defaultVariant")
flags[flag]["defaultVariant"] = want
json.dump({"old": old, "new": want, "want_value": variants.get(want),
           "variants": variants, "targeting": flags[flag].get("targeting"),
           "config": cfg}, sys.stdout)
