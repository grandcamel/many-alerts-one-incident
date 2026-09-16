# Quotations in the research documents

Type: task
Status: open
Blocked by: none

## Question

The pre-publish audit of 2026-09-15 found about eleven passages across the research documents where a third-party source is reproduced at length rather than cited. Every one is attributed and carries a source link, and none is a licensing violation on its face, but together they read as republication rather than research notes, and the tree is public now. Trim them.

This ticket does work; it decides nothing and produces no ADR. It is here so the frontier carries it rather than a reviewer's memory.

The heaviest first, all on their own `research/*` branches:

- `docs/research/model-and-effort-on-a-headless-run-2026-09.md` carries most of it: a twenty-two-row table whose "Documented behaviour" column is quoted prose from code.claude.com, several cells of it over twenty-five words; about 120 words restating the benchmark-results section of the cost-optimization page across five back-to-back quotes; about 73 words reproducing two bullet lists from the effort page; a 38-word block on SIGTERM and SIGINT from the headless page; and a 27-word quote from `shared/model-migration.md` inside the `claude-api` skill, which a reader of this repository cannot look up at all and should be replaced by a public citation or dropped.
- `docs/research/eyes-into-grafana-2026-09.md` pastes four lines of `run-grafana.sh` from `grafana/docker-otel-lgtm` with no license line, and compares four third-party binaries for bundling into the image while naming no licence for any of them. The repository's NOTICE covers `docker/rolldice/` from that same upstream and nothing else.
- `docs/research/claude-code-run-telemetry-2026-09.md` quotes three consecutive sentences, about 63 words, on TRACEPARENT handling.
- `docs/research/where-a-real-kubernetes-could-run-2026-09.md` quotes 36 words from the kind quick-start and 28 from the k3s cluster-access page.
- `docs/research/otel-demo-as-the-system-2026-09.md` quotes a 29-word collector warning.
- `docs/research/harness-sandbox-containers-2026-09.md`, already on `main` from chapter one, has the same shape: a 39-word block from Anthropic's secure-deployment page and several others of 33 to 50 words.

The rule to apply: keep the shortest quote that carries the load, paraphrase the rest in the document's own voice, and keep every citation. Where the finding is the exact wording, such as a precedence rule, quoting is right and stays. Two things travel with it: a licence line above any pasted third-party code, and a note in the Eyes comparison that copying a binary into a distributed image adds it to NOTICE.

The answer records which passages were rewritten, which were judged load-bearing and kept, and whether NOTICE changed.
