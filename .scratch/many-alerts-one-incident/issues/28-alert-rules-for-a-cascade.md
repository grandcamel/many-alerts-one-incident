# Alert rules for a Cascade

Type: grilling
Status: open
Blocked by: 10, 27

## Question

Graduated from the map's fog on 2026-09-17, once
[Faults and their Cascades](10-faults-and-their-cascades.md) fixed the Faults and the
alertable conditions each one raises. That ticket owns **what is true of the system when a
Fault fires**; this one owns **when we agree to call it an Alert**.

So: for each of the three Faults, what are the actual Grafana rules — thresholds, `for`
durations, labels, and the grouping that makes a Cascade arrive together?

- **Thresholds.** The conditions are written; the numbers are not. Several are already
  known to be delicate: cart's error ratio straddles 0.05 and needs an absolute rate
  against a measured baseline instead; the email memory rule had to move off 90%/`for:1m`
  because 90 → 100 MiB takes 56 s; frontend-proxy's ratio has a denominator nobody has
  measured. [Verify the signal surface](27-verify-the-signal-surface-and-settle-the-fault-gates.md)
  supplies the baselines — do not pick numbers before it reports.
- **NoData is the real decision, not the threshold.** Every `> 0` rule here is written on
  an error-only series that does not exist at steady state, and Grafana puts an empty
  vector in **NoData**, not Normal. Whether the Cascade misses entirely or fires before
  injection is decided by NoData handling and by whether each rule wraps in `or vector(0)`.
- **Instantiation is where the breadth comes from.** Two to four conditions with
  `by (service_name)` should give six to nine Alerts, each with its own Fingerprint. Which
  label set does each rule carry, and does every Alert still carry what ADR 0004's
  Fingerprint label and the Skill expect?
- **Grouping.** Grafana groups by `grafana_folder` and `alertname` with a 10 s group wait
  and a 1 m repeat, so a Cascade of N rules is N Notifications today. Widening that is
  [Many-to-one under a Cascade](14-many-to-one-under-a-cascade.md)'s decision, not this
  one — but this ticket must hand it a rule set whose labels make the intended grouping
  expressible.
- **Resolution.** Each Fault's undo restarts a service. What does the Resolved edge look
  like, and does a rule that goes NoData on recovery ever send a Resolved at all?

Every query these rules are built on is **proposed, not verified**, until
[Verify the signal surface](27-verify-the-signal-surface-and-settle-the-fault-gates.md)
runs. The trap list in [Faults and their Cascades](10-faults-and-their-cascades.md) —
the `service_namespace` selector, cross-language metric families, `span_kind` on ratio
denominators, `collector_instance_id` cardinality, gauge-versus-counter on restarts — is
this ticket's checklist, not background reading.
