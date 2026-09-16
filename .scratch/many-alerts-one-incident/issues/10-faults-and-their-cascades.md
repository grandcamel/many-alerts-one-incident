# Faults and their Cascades

Type: grilling
Status: open
Blocked by: 09

## Question

Which Faults can the simulation inject, including the one Kubernetes-native Fault the story needs? For each: its Ground truth, the Cascade of Alerts it should raise, the signals that show it (which logs, metrics, traces, Kubernetes Events and Changes), and its timing inside the slot from injection to the last Alert. Which Fault the live demo uses, and which are rehearsal-only. Every Fault added here writes its Ground truth, per the map's standing rule.

Start from the Demo's fifteen fault flags (two need the Kafka layer or Kubernetes). Decide here how each Fault's injection becomes a Change: the research found a flip emits nothing collectable, so a small watcher on flagd's event stream posting a Grafana annotation and an OTLP log record is the candidate, with the flag file as the source of truth. The Kubernetes-native Fault presents as a restart loop with a pod-status signal, not a reliable Kubernetes Event.
