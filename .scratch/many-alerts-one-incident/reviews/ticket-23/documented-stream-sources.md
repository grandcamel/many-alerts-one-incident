# Claude Code stream-json source map (documented subset)

Retrieved 2026-09-22. This is source-only research for an offline normalizer. It
does not identify, execute, authenticate, or qualify any installed `claude` binary;
it establishes neither a native launch, schema compatibility, cost, nor event origin.

## Primary sources

1. [Claude Code headless / print-mode documentation](https://code.claude.com/docs/en/headless), retrieved 2026-09-22. It documents `--output-format stream-json` as one JSON object per event, the final `result` message, init/retry/plugin events, and print-mode permission denial behavior.
2. [Claude Agent SDK streaming-output documentation](https://code.claude.com/docs/en/agent-sdk/streaming-output), retrieved 2026-09-22. It documents the partial-event wrapper, event ordering, complete assistant blocks, and terminal `ResultMessage`.
3. [Official Python Agent SDK types](https://github.com/anthropics/claude-agent-sdk-python/blob/f7547d7233527739ece8b12ed28c57be96c966b5/src/claude_agent_sdk/types.py), commit `f7547d7233527739ece8b12ed28c57be96c966b5` (main resolved 2026-09-22). It defines the public message/result/rate-limit shapes.
4. [Official Python Agent SDK message parser](https://github.com/anthropics/claude-agent-sdk-python/blob/f7547d7233527739ece8b12ed28c57be96c966b5/src/claude_agent_sdk/_internal/message_parser.py), same resolved commit. It records the CLI wire keys the SDK requires to build those public objects.

The two GitHub links are a reproducible source snapshot, not a claim about the
installed CLI version. The documentation pages are current pages and have no
immutable content version in their published URLs.

## Safe offline normalizer contract

Parse JSON objects one line at a time. Bound line/object depth, retained
fields, and total bytes outside this map. Reject malformed JSON and preserve an
unknown `type` as an opaque, non-success observation; do not silently treat it as
a terminal, tool, permission, rate-limit, or fallback event.

| Event | Require and map | Preserve / do not infer |
| --- | --- | --- |
| `system/init` | `type == "system"`, `subtype == "init"`. The official headless page says it reports session metadata, including model, tools, MCP servers, plugins, and optional `capabilities`. | Published docs do **not** give a closed required-field schema for init. Treat every additional field, including `session_id`, `model`, `tools`, `mcp_servers`, `plugins`, and `capabilities`, as optional typed observations. Do not require init to be first: plugin and hook startup events can precede it. |
| complete `assistant` | `type == "assistant"`; `message` object; `message.model` string; `message.content` array. Preserve optional outer `uuid`, `session_id`, `parent_tool_use_id`, `error`; preserve optional message `id`, `usage`, and `stop_reason`. | The SDK emits one complete `AssistantMessage` per nonempty completed content block, not necessarily one per model turn. Its `parent_tool_use_id` associates subagent output; `null` is main conversation, not a native identity assertion. |
| assistant tool call | A `message.content[]` item with `type == "tool_use"` requires string `id`, string `name`, and object `input`. Map it as a proposed tool call only. | Do not infer execution, permission, success, side effect, or tool-result pairing from this item alone. |
| `user` tool result | `type == "user"`; `message.content` may be text or array. For array item `type == "tool_result"`, require string `tool_use_id`; retain optional `content` (text, array or null) and `is_error` (boolean or null). | It is a returned tool-result block, not proof that a host tool ran or that its bytes are complete. |
| `stream_event` | Outside the minimal complete-message normalizer. If separately enabled, require wrapper `type == "stream_event"`, string `uuid`, string `session_id`, object `event`; keep it as partial evidence. | The documented raw inner event types are `message_start`, `content_block_start`, `content_block_delta`, `content_block_stop`, `message_delta`, and `message_stop`. Deltas are not accumulated complete messages. `text_delta.text` and `input_json_delta.partial_json` are only partial chunks. |
| final `result` | `type == "result"`; require string `subtype`, integer `duration_ms`, integer `duration_api_ms`, boolean `is_error`, integer `num_turns`, and string `session_id`. Retain optional `stop_reason`, `total_cost_usd`, `usage`, `result`, `structured_output`, `modelUsage`, `permission_denials`, `deferred_tool_use`, `errors`, `api_error_status`, `uuid`, `terminal_reason`, and `origin`. | Documented subtypes are `success`, `error_during_execution`, `error_max_turns`, `error_max_budget_usd`, and `error_max_structured_output_retries`. Only `success` can carry final text; `success` plus `is_error == true` is still an API-error outcome, not success. |

### Terminal, error, cancellation, permission, and fallback boundaries

* The documented headless contract calls `result` the last stream line. The Agent
  SDK flow places the final `ResultMessage` after complete messages and tool work.
  A normalizer should therefore accept one final result only after its own
  bounded stream-order checks; it must not reconstruct a result from an
  assistant message or a partial delta.
* `terminal_reason` is optional. The SDK describes `completed`, `max_turns`,
  `api_error`, `aborted_streaming`, and `aborted_tools`; the two `aborted_*`
  values are documented cancellation/interrupt outcomes. Their absence is not
  a completion guarantee, especially for older CLI paths.
* `system/api_retry` is documented with `attempt`, `max_retries`,
  `retry_delay_ms`, `error_status`, optional `no_response`, `error`, `uuid`,
  and `session_id`. It is retry progress only. It is neither a final error nor
  a documented model-fallback receipt.
* Print-mode `permission_denied` appears as a system message and final results
  list `permission_denials`, but the consulted official docs do not publish a
  closed raw `permission_denied` field schema. Keep the system event opaque and
  retain result `permission_denials` only as optional diagnostic data. Do not
  turn either into approval, denial provenance, or tool execution evidence.
* No consulted primary source defines a `fallback` stream event or a closed
  fallback-result schema. Do not recognize an observed fallback wrapper as a
  successful substitute model/run; record it as an unknown observation.

## Known mismatch and abstention rules

The Agent SDK documents a `RateLimitEvent`/wire `rate_limit_event` wrapper with
`rate_limit_info`, `uuid`, and `session_id`, but it is outside the minimal
print-stream normalizer contract above. Likewise, observed `thinking_tokens`,
wrapper-specific `usage`, extra rate-limit fields, or future event types are
not a basis for a permissive allowlist. Retain them only as bounded opaque
diagnostics, or reject them under a closed profile.

The sources distinguish raw partial stream events from complete assistant and
result messages. They do not define a complete, versioned JSON Schema for every
Claude Code `--print --output-format stream-json` family, nor a closed init or
permission-denial schema. An implementation should expose the documented subset
above and explicitly mark all other families `UNQUALIFIED`; it must not promote
documentation lookup into installed-CLI, native-event, authentication, billing,
tenant, or launch provenance.

## Retained primary-source bytes

The pinned types and parser were retrieved and SHA-256 indexed outside Git at
`/Users/jasonkrueger/maoi-ticket23-evidence/20260922-native-schema/primary-sources/`.
The types digest is `545a9f8a15fac2d7337346e45b8695b5536e3fa1ace60edc76b37f5ca8ef56b6`;
the parser digest is `febb1aee19e47e03433d89cd4b1f8c5636950e206df77e4f4ca2738b0c900393`.
Direct documentation snapshot retrieval returned HTTP 403; no local HTML snapshot
is claimed. Nullable SDK fields remain nullable in the offline subset. The pinned
SDK permits object-valued `origin` and `deferred_tool_use`, and arbitrary JSON
`structured_output`; none supplies authenticated origin, dispatch or effect evidence.
