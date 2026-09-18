# Ticket 20 temporary editorial edits

Prepared from `origin/research/model-and-effort` (`2f640aa`) and
`origin/research/eyes-into-grafana` (`9dc705f`). These are temporary copies only; no repository
file, branch, or remote was changed.

## `model-and-effort-on-a-headless-run-2026-09.md`

- Replaced extended third-party quotations in the method, model/effort resolution discussion,
  controls table, signal handling, tool-call explanation, benchmark comparison, and latency section
  with cited paraphrases.
- Preserved the public source citations supporting each historical finding.
- Removed the private `claude-api` skill and migration-guide citations and their source-list entries.
  The affected model, pricing, effort, and latency statements now rely only on the existing public
  Anthropic documentation citations; no new claim was added.

## `eyes-into-grafana-2026-09.md`

- Replaced the copied `run-grafana.sh` block with a concise statement of its historical default and
  retained `[local-image]`, `[otel-lgtm-run-grafana]`, and `[otel-lgtm-run-prometheus]` citations.
- Added a narrow distribution boundary below the comparison table: any selected third-party binary
  needs a pinned-binary/dependency license and `NOTICE` review before image distribution.

## Uncertainties retained

- This is historical research, not a current product or runtime verification.
- The temporary Eyes note identifies no license: this document did not itself evidence a license or
  an applicable `NOTICE` obligation for a pinned binary and its dependency set.
- No network lookup, package install, model call, container/cluster run, or repository edit occurred.
