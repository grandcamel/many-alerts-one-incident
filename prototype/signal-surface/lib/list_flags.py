"""Every flag the chart ships, with its variants and current default."""
import json, sys
d = json.load(sys.stdin)
key = next(k for k in d["data"] if k.endswith(".json"))
flags = json.loads(d["data"][key])["flags"]
print(f"  {len(flags)} flags in {key}")
for name in sorted(flags):
    f = flags[name]
    print(f"    {name}: default={f.get('defaultVariant')} variants={list(f.get('variants', {}))}")
