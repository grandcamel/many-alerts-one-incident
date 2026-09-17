"""Node-level truth from the kubelet's /stats/summary.

The container sum is NOT node usage: it excludes kubelet, containerd, the OS,
cilium's datapath and page cache. This reads the node's own numbers.
"""
import json, sys
d = json.load(sys.stdin)
n = d["node"]
g = 2**30
mem, cpu, fs = n["memory"], n.get("cpu", {}), n.get("fs", {})
print(f"  node:             {n['nodeName']}")
print(f"  memory workingSet {mem['workingSetBytes']/g:.2f} GiB")
print(f"  memory available  {mem.get('availableBytes',0)/g:.2f} GiB")
print(f"  memory usage      {mem.get('usageBytes',0)/g:.2f} GiB")
print(f"  memory rss        {mem.get('rssBytes',0)/g:.2f} GiB")
print(f"  cpu               {cpu.get('usageNanoCores',0)/1e9:.2f} cores of 8")
print(f"  ephemeral fs      {fs.get('usedBytes',0)/g:.1f} GiB of {fs.get('capacityBytes',0)/g:.1f} GiB")
pods = sorted(d.get("pods", []), key=lambda p: -p.get("memory", {}).get("workingSetBytes", 0))
print("  top 8 pods by workingSet:")
for p in pods[:8]:
    print(f"    {p['memory']['workingSetBytes']/2**20:7.0f} Mi  {p['podRef']['namespace']}/{p['podRef']['name']}")
