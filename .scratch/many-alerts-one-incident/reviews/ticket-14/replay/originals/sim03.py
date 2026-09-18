import json
BASE="/private/tmp/claude-501/-Users-jasonkrueger-projects-many-alerts-one-incident/091819f5-bb4c-41c7-a2e6-c2c6e2590647/scratchpad/cap/"
T0=1789681945; TU=1789682809
# C1 condition-true windows at 0.03, from the replay channel (measured), plus C2's observed Alerting window
# C1 firing = condition true + for(1m) + one eval interval(10s)
C1=[("frontend",176,1137),("frontend-proxy",176,1137),("checkout",176,1137)]
C2=[("payment",426,907),("accounting",426,907),("email",426,907),("fraud-detection",426,907)]
alerts=[]
for s,a,b in C1: alerts.append(("C1 Service error rate is elevated",s,a+70,b+10,"critical"))
for s,a,b in C2: alerts.append(("C2 Service request rate has dropped to zero",s,a,b,"warning"))
print("alert firing windows (t+s):")
for n,s,a,b,sev in alerts: print(f"   {n[:3]} {s:16s} [{a:.0f},{b:.0f})  {sev}")

def dispatch(repeat, group_by_alertname=True, gw=10.0, gi=10.0):
    ticks=[i*5.0 for i in range(0,400)]
    state={}; sends=[]; prev=set()
    for rel in ticks:
        firing={(n,s) for n,s,a,b,_ in alerts if a<=rel<b}
        res=prev-firing
        groups={}
        for n,s in firing|res:
            gk=(n if group_by_alertname else "demo",)
            g=groups.setdefault(gk,{"f":set(),"r":set()})
            (g["f"] if (n,s) in firing else g["r"]).add((n,s))
        for gk,g in groups.items():
            e=state.get(gk); f=frozenset(g["f"]); r=frozenset(g["r"])
            if e is None:
                if f: state[gk]={"t":rel+gw,"f":f,"r":r}; sends.append((rel+gw,gk,sorted(f),sorted(r)))
                continue
            need = (not f<=e["f"]) or (not f and e["f"]) or (r and not r<=e["r"]) or (rel-e["t"]>=repeat)
            if need and rel-e["t"]>=gi:
                state[gk]={"t":rel,"f":f,"r":r}; sends.append((rel,gk,sorted(f),sorted(r)))
        prev=firing
    return sends

for rep,lab in ((60.0,"repeat 1m (today)"),(600.0,"repeat 10m (D1)")):
    s=dispatch(rep)
    print(f"\n### C1@0.03, group_by keeps alertname, {lab}: {len(s)} Notifications")
    for t,gk,f,r in s: print(f"   t+{t:6.0f}  {gk[0][:3]}  firing={[x[1] for x in f]} resolved={[x[1] for x in r]}")
    # Run schedule: serialized, coalescing (D3c), duration D
    for D in (370.0,300.0):
        busy=0.0; runs=[]; pend=[]
        i=0
        events=sorted(s)
        clock=0.0
        while i<len(events) or pend:
            if not pend:
                t,gk,f,r=events[i]; i+=1; pend=[(t,gk,f,r)]
                start=max(t,busy)
            else:
                start=max(busy,pend[0][0])
            # absorb everything arriving before start
            while i<len(events) and events[i][0]<=start:
                pend.append(events[i]); i+=1
            merged={}
            for t,gk,f,r in pend:
                for x in f: merged[x]="firing"
                for x in r: merged[x]="resolved"
            end=start+D
            runs.append((start,end,dict(merged)))
            pend=[]
            while i<len(events) and events[i][0]<end:
                pend.append(events[i]); i+=1
            busy=end
        print(f"\n   --- Run schedule, Run duration {D:.0f}s (coalescing D3c), C1@0.03, {lab}")
        for k,(a,b,m) in enumerate(runs,1):
            nf=sum(1 for v in m.values() if v=="firing"); nr=len(m)-nf
            print(f"      Run{k}: t+{a:5.0f} -> t+{b:5.0f}  ({a/60:.1f}->{b/60:.1f} min)  firing={nf} resolved={nr}  set={[ (x[0][:2],x[1],v) for x,v in sorted(m.items())]}")
