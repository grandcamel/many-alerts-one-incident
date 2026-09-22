# Change recipe source check

Read-only check on 2026-09-22 of local Git object
`557153bf531222dec1751f4bb5ac31adefcfa323`, currently named
`prototype/cascade-timing`. No historical script was executed and no cluster
was contacted.

| File within that commit | Source observation | Contract consequence |
| --- | --- | --- |
| `prototype/signal-surface/lib/flagd_config.py` | Parses JSON from `ConfigMap.data[KEY]`, changes `flags[flag].defaultVariant`, then serializes the document. | A flag is not a top-level ConfigMap data key. Validate the pinned document structure, change one allowed nested field, and preserve unrelated data under a fresh resource-version precondition. |
| `prototype/signal-surface/flag.sh` | Historically discovers the ConfigMap/key, applies the rewritten document, rolls flagd, and reads its copied file via flagd-ui exec. | Historical mechanism only. Discovery, generic apply, exec and the script's timeout are not the proposed coordinator authority or deadline contract. |
| `prototype/cascade-timing/capture/cascade-cartFailure-100%.log`, lines 66–81 | Records ConfigMap `flagd-config`, key `demo.flagd.json`, cartFailure `off` to `100%`, numeric value 1, and the in-pod variant observation. | Pin the historical cart recipe to `100%`; independently verify actual deployment identity and supported read-back before enabling it. |
| Same capture, lines 140–155 | Records `100%` to `off`, value 0 and in-pod `off`. | The historical baseline was off. The future undo must verify the expected post-injection value and restore the recorded pre-injection value rather than assuming current state already equals off. |

The retained [upstream flag document](../ticket-40/upstream/demo.flagd.json.txt)
also contains the nested flag structure and permitted variants. Its
[source receipt](../ticket-40/upstream/receipt.json) pins that different upstream
source; it is not the local historical capture commit or current deployed image.
Neither source proves effective Kubernetes grants, live served/evaluated behavior,
or current image/source correspondence.
