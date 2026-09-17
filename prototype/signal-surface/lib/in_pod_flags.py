"""Print flagd's in-pod flag config. stdin: /app/data/demo.flagd.json.

With FLAG set, prints that one flag in full — variants, defaultVariant and any
targeting rule — because `productCatalogFailure` proved that a defaultVariant
can be shadowed by a targeting rule that returns "off" on both branches.
"""
import json, os, sys

d = json.load(sys.stdin)
flags = d.get("flags", {})
one = os.environ.get("FLAG")
if one and one in flags:
    f = flags[one]
    print("  %s" % one)
    print("    defaultVariant: %s" % f.get("defaultVariant"))
    print("    variants: %s" % json.dumps(f.get("variants")))
    print("    state: %s" % f.get("state"))
    if f.get("targeting"):
        print("    targeting: %s" % json.dumps(f.get("targeting")))
        print("    !! a targeting rule shadows defaultVariant when it returns a variant")
else:
    print("  %d flags in flagd's own copy" % len(flags))
    for name in sorted(flags):
        f = flags[name]
        t = " targeting=yes" if f.get("targeting") else ""
        print("    %-32s default=%-8s variants=%s%s"
              % (name, f.get("defaultVariant"), list(f.get("variants", {})), t))
