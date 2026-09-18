# Ticket 14 evidence and accepted round 2

Local planning artifacts. No Skill or runtime implementation changes. No live Jira writes, demo, cluster or model Runs. One Terra worker was reused sequentially for Grafana, replay and stage work; boss reviewed the conclusions. The human accepted all seven round-2 recommendations; ticket 14 is resolved as a planning decision.

- [Jira objections](jira/report.md): six claims, local v2 CLI evidence and committed capture extracts.
- [Grafana objections](grafana.md): six claims; historical-count updates linked at the end.
- [Replay reconciliation](replay/report.md): exact selected predicate and explanation of 8 versus 10.
- [Stage objections](stage.md): six claims with boss corrections recorded.
- [Completeness](completeness.md): original Question mapped to decisions and missing choices.
- [Round 2](round-2.md): all seven recommendations accepted; original question wording preserved.

Reproduce the selected historical delivery filter from this repository root:

```sh
python3 .scratch/many-alerts-one-incident/reviews/ticket-14/replay/filter.py .scratch/many-alerts-one-incident/reviews/ticket-14/jira
```

Results are in replay/results.txt. Source capture bytes retain committed source line numbering and hashes recorded in replay/report.md. replay/originals preserves the prior scripts cited for provenance; those originals retain historical absolute paths and are not the portable reproduction entry point.

Evidence boundary: source/CLI request construction is not live OPS edit acceptance. Filtering 60-second delivery captures is not an actual changed-policy scheduler or a post-threshold-change forecast. Matched-Run speed remains unmeasured. These limits remain explicit in the reports.

Earlier report statements that the repository was unchanged describe their individual read-only verification passes. This session subsequently added this evidence directory and appended WIP findings and the accepted Answer to ticket 14, synchronized the map/ADR/glossary and graduated fixture planning to ticket 31; it changed no Skill or runtime source.
