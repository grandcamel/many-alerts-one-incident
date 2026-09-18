# Ticket 20 editorial cleanup

## Placement and provenance

The five branch-only documents are brought into `docs/research/` as edited reading copies alongside the existing harness document. The user was offered a placement preference; absent a reply, the stated default was to keep one reviewable main-branch change and preserve historical refs. `source-manifest.json` records each exact source commit. No historical refs or immutable line-cited evidence captures were rewritten, and nothing was pushed or published.

Each reading copy identifies this as a 2026-09-18 editorial pass, not a fresh verification of the original September findings. Old model names, versions, examples and measured boundaries remain historical evidence. The original source commits remain available for existing `git show` citations.

## Passage disposition

- Harness/container research: paraphrased the proxy/credential guidance, devcontainer warning, Bash-only boundary, masking description, nested-container workaround, whole-process sandbox description, proxy network/API explanation, E2B isolation/secret handling and bare-mode guidance. Replaced the copied deployment command with cited prose, so no unattributed command block remains there.
- Run telemetry: paraphrased the three-sentence trace-context passage, child-process telemetry/precedence discussion and privacy-default summary. Kept API field names and source references.
- Kubernetes venue: paraphrased kind's build-memory guidance and K3s remote-kubeconfig instructions. Kept quantities and the distinction between build requirements and unmeasured runtime footprint.
- OTel system: paraphrased the span-metrics connector startup warning. Kept the short exact array-replacement phrase because it explains a configuration precedence trap.
- Model/effort: paraphrased the quoted controls table, effort/tool-use discussion, benchmark and signal-handling passages; removed the private migration quote and citations. Kept all control rows and restored the full reported benchmark figures during review. Eyes: replaced the copied shell block with cited prose and added the tagged upstream license table and distribution/NOTICE note. The accompanying worker report records its bounded edits.

## Attribution boundary

No binaries were added. Copied shell excerpts identified by this ticket are replaced with cited prose rather than assigning an unverified documentation license. The Eyes document includes a separately dated upstream repository-license lookup and requires verifying the pinned distribution and dependencies before bundling. Adding a distributed binary requires updating this repository's NOTICE and carrying the applicable license/notice material; a NOTICE entry alone is not claimed to satisfy every license condition.

NOTICE is unchanged: this editorial task introduces no distributed binary or copied third-party code. Frozen historical evidence, including ticket 15's byte-for-byte source capture, remains unchanged to preserve its provenance and line citations.

## Verification

All six documents passed source-label preservation checks: only the two explicitly retired private skill labels were removed. See citation-check.json. All public source labels remain; diff whitespace checks passed. No runtime code changed; no model, container, cluster or demo ran.
