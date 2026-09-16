# Ground truth for the canned Cascade

PROTOTYPE — throwaway. The Run never sees this file. It is what the Report is judged against.

## The Fault

`recommendationCacheFailure`, one of the OpenTelemetry Demo's runtime fault flags, was
flipped on at **14:02:00Z** on 2026-09-15. With it on, the `recommendation` service's
in-process cache list grows by about a quarter of itself on roughly half of
`ListRecommendations` calls, so it never serves a hit again and its heap climbs without
bound.

## The chain

Cache stops serving and starts growing → `recommendation` resident memory climbs from
188 MB to 947 MB in six minutes and GC pauses grow from 3 ms to 181 ms a minute → CPU
saturates at about one core → p99 of `ListRecommendations` goes from 42 ms to 2.38 s →
`frontend`, which calls it on every page and on `/api/recommendations`, inherits the
latency and starts hitting its upstream deadline → the edge proxy returns 504 →
`product-catalog` sees more `ListProducts` calls from the retrying recommendation path
and its p95 and backend count rise → whole-host CPU rises because one container is now
eating a core.

## What a correct Suggested root cause names

The `recommendationCache` feature flag being turned on at 14:02:00Z, and the
`recommendation` service's unbounded cache growth as the mechanism. Naming the flag is
the pass mark. Naming only "a memory leak in recommendation" is a near miss: right
service, right mechanism, cause not identified.

## The two red herrings

1. **`HostCpuHigh`** is a consequence, not a cause. A Report that blames host capacity,
   noisy neighbours or the need to scale the host has failed.
2. **`deploy: payment v1.8.3`** at 13:10:00Z, fifty-two minutes before the flip, on a
   service whose latency, memory and logs are flat throughout. It is the plausible wrong
   answer — "the recent deploy did it" — and citing it as the cause is a failure. The
   `frontend v2.1.0` deploy six hours earlier is the same trap, weaker.

## The evidence a good Report cites

- The Change at 14:02:00Z (annotation 412), which is the flip itself.
- Trace `3f5c1a90b7d4e2118a6c0f3e9d215b47`, whose `recommendation` span carries
  `demo.feature_flag.recommendation_cache=true`, `demo.recommendation.cache_hit=false`
  and `app.recommendation.cache_size=7816`.
- The baseline trace `bb70c4e2119d3a5f8e61c0742a9f3d16` from before the flip, with the
  same attributes inverted — the comparison is the proof.
- The `cache miss: recommendation cache size now N` log lines, N climbing 1043 → 9770.
- `container_memory_usage_bytes{service="recommendation"}` over the window.

## Blast radius

Affected: `recommendation` (cause), `frontend`, `frontend-proxy`, `product-catalog`
(secondary), the host (consequence). Unaffected, and a Report that says so is better for
it: `cart`, `payment`, `shipping`, `checkout`, `ad`.

## Scoring

| Grade | Meaning |
| --- | --- |
| pass | names the `recommendationCache` flag flip as the cause |
| near | names recommendation's cache or memory growth but not the flag |
| fail | names a red herring, another service, or nothing |

Cited: every claim in the root-cause section points at evidence the Run retrieved.
