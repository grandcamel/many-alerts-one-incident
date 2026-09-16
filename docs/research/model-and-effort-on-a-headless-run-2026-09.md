# Which model, at what effort, on a headless Run (September 2026)

Written 2026-09-15. Question: how are the model and the effort set for a Claude Code print-mode
Run, and what does a high-effort Opus 5 Run cost in time and money against a Fable 5.1 one? The
next chapter wants a high-reasoning Run that fits a thirty-minute slot in which one Run may think
for about five minutes on screen, with "Opus 5 at high effort" as the hypothesis to test first.

**Method.** The `claude-api` skill was loaded first and its model table, `shared/models.md`,
`shared/model-migration.md` and `shared/cost-optimization.md` read; model ids and prices below come
from there and from the platform pages the skill points at, never from memory. The Claude Code
pages (CLI reference, model configuration, settings reference, environment variables, permission
modes, headless, costs, and the Agent SDK references) were fetched as raw markdown from
code.claude.com and grepped, so every quoted flag description is verbatim. The installed binary was
checked with `claude --version` and `claude --help` (2.1.272). This repo's
`grafana_jsm_sandbox/run_command.py` and the `result` line of `fixtures/run-transcript.jsonl`
supplied what chapter one already does and what a Run reports. Everything was fetched 2026-09-15.
No live Run was started; anything only a Run could confirm is listed under "Could not verify".

## Short answer

1. **The model is a session choice, and today the Run does not make it.** `--model <alias|id>`
   overrides the `model` settings key and the `ANTHROPIC_MODEL` environment variable; the flag,
   the variable and the key all accept an alias or a full id ([cli-reference], [settings-reference]).
   `run_command.py` passes none of them, so a Run starts on whatever the host's settings resolve to.
   On this laptop that resolved to `claude-fable-5-1` ([fixture]), although the account-type default
   for Max, Team Premium, Enterprise and API accounts is Opus 5 ([model-config]); a saved `/model`
   pick in user settings explains the difference. The full ids are `claude-opus-5` and
   `claude-fable-5-1`; the `opus` alias moves with releases ([models-overview], [model-config]).
2. **Effort is settable on a headless Run, by flag or by variable.** `--effort` takes `low`,
   `medium`, `high`, `xhigh`, `max` or `ultracode` and "Overrides the `modelSettings` and
   `effortLevel` settings for this session and does not persist"; `CLAUDE_CODE_EFFORT_LEVEL`
   "Takes precedence over `--effort`, `/effort`, and the `modelSettings` and `effortLevel` settings"
   ([cli-reference], [env-vars]). Neither is marked print-mode-only, and the model-configuration
   page's advice for `-p` runs is "pass `--effort` at launch" ([model-config]). `high` is the
   default on both models ([models-overview]), so "Opus 5 at high effort" is what `--model
   claude-opus-5` gives with no effort flag at all; `xhigh` is the first level that changes anything.
3. **Opus 5 costs half of Fable 5.1 per token on everything except cache reads, where it costs
   double.** $5/$25 against $10/$50 per million input/output tokens, both with a 1M context and
   128K max output ([pricing], [opus-5], [fable-5-1]). Re-priced at Opus 5 rates, the recorded
   chapter-one Run's tokens come to $0.28 against its actual $0.45 ([fixture], arithmetic below).
   What a *high-effort* Run costs is unmeasured: effort changes output and thinking tokens, and the
   fixture had none of the latter.
4. **There is no wall-clock limit on a print-mode Run; the only caps are turns and dollars.**
   `--max-turns` "Exits with an error when the limit is reached. No limit by default";
   `--max-budget-usd` stops "on API calls before stopping (print mode only)" ([cli-reference]). Both
   end the Run with a `result` line whose `subtype` is `error_max_turns` or `error_max_budget_usd`
   and which still carries `total_cost_usd`, `usage`, `modelUsage` and `permission_denials`
   ([sdk-typescript]). Nothing in the docs ties either cap to `dontAsk`; the recorded Run shows a
   denied tool call consumed a turn like any other ([fixture]).
5. **Raising effort is documented to change tool-call count, on the platform side.** "Lower
   effort also means fewer and terser tool calls"; higher effort levels "may: Make more tool calls"
   ([effort]). The Claude Code page describes effort as controlling "adaptive reasoning" only and
   says nothing about tool calls either way ([model-config]).

## The two models

| Model | Model id | Input | Output | 5m cache write | 1h cache write | Cache read | Context | Max output | Comparative latency | Default effort |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Claude Fable 5.1 | `claude-fable-5-1` | $10 / MTok | $50 / MTok | $12.50 / MTok | $20 / MTok | $0.25 / MTok | 1M tokens | 128K tokens | Slower | `high` |
| Claude Opus 5 | `claude-opus-5` | $5 / MTok | $25 / MTok | $6.25 / MTok | $10 / MTok | $0.50 / MTok | 1M tokens | 128K tokens | Moderate | `high` |

Sources: the skill's cached table (2026-06-24) and `shared/models.md` ([skill]); the pricing page
([pricing]); the models overview ([models-overview]); each model's page ([opus-5], [fable-5-1]).
All four agree. Notes that matter here:

- Fable 5.1's cache-read price is "0.025x the base input price" where "All other models use the
  standard 0.1x multiplier" ([pricing]). That is the one line where Fable 5.1 is cheaper per token
  than Opus 5.
- "Claude 4.6 and later models ... include the full 1M token context window at standard pricing"
  ([pricing]); no long-context premium applies to either model.
- Both support all five effort levels, `low` through `max` ([effort], [model-config]).
- Fable 5.1's thinking is "Adaptive (always on)"; Opus 5's is adaptive and on by default, and
  cannot be disabled at `xhigh` or `max` ([models-overview], [effort]).
- "The effort scale is calibrated per model, so the same level name does not represent the same
  underlying value across models" ([model-config]).
- The models overview's own routing advice: "start with Claude Opus 5 for most workloads. Use
  Claude Fable 5.1 for demanding reasoning and long-horizon agentic work, or when your evals on
  Claude Opus 5 at higher effort still fall short" ([models-overview]).

## How the model is chosen for a print-mode Run

Claude Code resolves the model in this order: `/model` in the session, `--model` at launch, the
`ANTHROPIC_MODEL` variable, the `model` settings key, then `ANTHROPIC_DEFAULT_MODEL` (v2.1.236+),
which applies "only when no file sets `model`" ([model-config], [settings]). The `model` key is "a
model alias or full model ID" with the default "unset, so Claude Code uses your account's default
model" ([settings-reference]).

What the aliases mean today, on the Anthropic API: `opus` is Opus 5 (v2.1.219+; before that Opus
4.8), `sonnet` is Sonnet 5, and `fable` "resolves to Fable 5.1" unless `ANTHROPIC_DEFAULT_FABLE_MODEL`
is set (v2.1.257+) ([model-config]). "Aliases point to the recommended version for your provider and
update over time. To pin to a specific version, use the full model name, for example
`claude-opus-5`" ([model-config]). The account-type default is "Opus 5" for "Max, Team Premium,
Enterprise, and Anthropic API" and "Sonnet 5" for "Pro and Team Standard"; "Fable models are not the
account-type default on any plan or provider. Choosing one with `/model` saves it as the selected
model in your user settings, so later sessions start on it" ([model-config]).

The recorded Run's `system/init` line says `"model": "claude-fable-5-1"` with `"apiKeySource":
"none"` ([fixture]). `run_command.py` sets no model, so the Run inherited the laptop's saved
selection. In the container the same command will inherit whatever `~/.claude/settings.json` the
image carries, which is nothing today, so it would start on the account default instead. The two
environments already disagree; the fix is a `--model` argument.

`--bare`, which the sandbox research recommended for a later ticket, does not change model
resolution; it skips hooks, skills, plugins, MCP servers, auto memory and CLAUDE.md and "Sets
`CLAUDE_CODE_SIMPLE`" ([cli-reference]).

## How effort is set, and whether it reaches a headless Run

Effort "control[s] adaptive reasoning, which lets the model decide whether and how much to think
on each step based on task complexity" ([model-config]). With `ultracode` off, the session's level
is resolved "in this order, taking the first that applies":

1. "An explicit choice: the `CLAUDE_CODE_EFFORT_LEVEL` environment variable, launching with
   `--effort`, or `/effort` in the session"
2. A hold on the model's default effort, which exists on "Fable 5, Opus 4.8, or Opus 4.7" and not
   on the two models in question: "Opus 5 and Fable 5.1 have no such hold"
3. Saved settings: `modelSettings` per model or the top-level `effortLevel`
4. "The model's default effort: `high` on every model that supports effort, except that Opus 4.7
   defaults to `xhigh`" ([model-config])

Everything a headless Run can use is in the first and third steps. On the print-mode question
specifically, the page has a paragraph on non-interactive sessions: "When you set a level with
`/effort` in a `-p` run, Claude Code applies it to that session only and doesn't save it as your
default ... so pass `--effort` at launch instead" ([model-config]). The organization-cap paragraph
also distinguishes "plain-text `--print` runs", where a clamp prints a warning, from "`json` or
`stream-json` output", where "the clamp applies silently" ([model-config]); both confirm the effort
machinery is live under `--print`. The Agent SDK, which wraps the same `-p` entry point, exposes
`effort: 'low' | 'medium' | 'high' | 'xhigh' | 'max'` as a query option ([sdk-typescript],
[sdk-python]). `claude --help` on the installed 2.1.272 lists `--effort <level>  Effort level for
the current session` ([help]).

Three details that affect the demo:

- **`max` is session-only by design.** "Unless you set it through the `CLAUDE_CODE_EFFORT_LEVEL`
  environment variable, Claude Code applies `max` to the current session only", and "`max` isn't
  accepted as a level in either key" (`effortLevel`, `modelSettings`) ([model-config]). For a Run
  that is fine: a flag or the variable is the natural carrier anyway.
- **The Transcript will not say which effort ran.** The `system/init` message has an `effort`
  field, but "Claude Code sets the field only on the init message it sends to Remote Control
  clients, and omits it from the init message your application reads" ([sdk-typescript]). The
  fixture's init line indeed has none ([fixture]). The observable is
  `usage.output_tokens_details.thinking_tokens` on the result line (0 in the fixture).
- **Thinking cannot be turned off on Fable, and on Opus 5 turning it off clamps effort.**
  `MAX_THINKING_TOKENS=0` "turns thinking off on the Anthropic API except on Fable models"; with
  thinking off, "Claude Code sends effort `high` instead of a higher level to models it knows don't
  accept that combination, such as Opus 5" ([env-vars], [model-config]). Nonzero values are ignored
  on adaptive-reasoning models ([env-vars]), so `MAX_THINKING_TOKENS` is not a lever for this demo.

## Flags, settings and variables, as documented

| Control | Documented behaviour | Source |
| --- | --- | --- |
| `--model <alias\|id>` | "Sets the model for the current session with a model alias such as `sonnet`, `opus`, `haiku`, or `fable`, or a model's full name. Overrides the `model` setting and `ANTHROPIC_MODEL`" | [cli-reference] |
| `ANTHROPIC_MODEL` | "Name of the model setting to use"; "exported in your shell applies over the `model` key from any file" | [env-vars], [settings] |
| `model` (settings key) | "string, a model alias or full model ID"; default "unset, so Claude Code uses your account's default model"; `--model` and `ANTHROPIC_MODEL` outrank it for one session | [settings-reference] |
| `ANTHROPIC_DEFAULT_MODEL` | "Model that new sessions start on by default. Requires Claude Code v2.1.236 or later"; used "only when nothing else selects a model" | [env-vars], [settings-reference] |
| `ANTHROPIC_DEFAULT_OPUS_MODEL` / `_FABLE_MODEL` | Pin what the `opus` / `fable` aliases resolve to; the value "must be a full model name" | [model-config] |
| `--effort <level>` | "Options: `low`, `medium`, `high`, `xhigh`, `max`, or `ultracode`. Available levels depend on the model ... Overrides the `modelSettings` and `effortLevel` settings for this session and does not persist" | [cli-reference] |
| `CLAUDE_CODE_EFFORT_LEVEL` | "Values: `low`, `medium`, `high`, `xhigh`, `max`, or `auto` to use the model default ... Takes precedence over `--effort`, `/effort`, and the `modelSettings` and `effortLevel` settings. A `maxEffortLevel` cap still applies" | [env-vars] |
| `effortLevel` (settings key) | Default level "for models you haven't saved a level for"; one of `low`, `medium`, `high`, `xhigh`; "`--effort` takes precedence over this key for one session, and `CLAUDE_CODE_EFFORT_LEVEL` takes precedence over both" | [settings-reference] |
| `modelSettings` (settings key) | Per-model `effortLevel` (and optional `maxEffortLevel`), keyed by canonical name "such as `claude-opus-5`"; outranks the top-level `effortLevel` in the same file; v2.1.251+ | [settings-reference] |
| `maxEffortLevel` (settings key) | "Cap the effort level a session can use ... Any higher level runs at the cap instead", including `--effort` and the env var; v2.1.267+ | [settings-reference] |
| `--max-turns <n>` | "Limit the number of agentic turns (print mode only). Exits with an error when the limit is reached. No limit by default" | [cli-reference] |
| `CLAUDE_CODE_MAX_TURNS` | "Cap the number of agentic turns when no explicit limit is passed. Equivalent to passing `--max-turns`, which takes precedence when both are set" | [env-vars] |
| `--max-budget-usd <amount>` | "Maximum dollar amount to spend on API calls before stopping (print mode only). Spend from subagents counts toward the cap"; cap enforcement v2.1.217+ | [cli-reference] |
| `--permission-mode dontAsk` | "Claude Code denies every call that would otherwise prompt, which is useful for locked-down CI runs" | [headless] |
| `--permission-prompts none` | In a `-p` run with no host, prompts "are denied either way, and the flag also tells Claude not to retry them"; v2.1.259+ | [headless] |
| `--fallback-model <m,...>` | "Enable automatic fallback to the specified model(s) when the primary model is overloaded or not available ... comma-separated list tried in order" | [cli-reference] |
| `CLAUDE_CODE_MAX_OUTPUT_TOKENS` | "Set the maximum number of output tokens for most requests. Defaults and caps vary by model"; the recorded Run reports `maxOutputTokens: 64000` for `claude-fable-5-1` | [env-vars], [fixture] |
| `MAX_THINKING_TOKENS` | Fixed budget for non-adaptive models; "Claude Code ignores nonzero values on adaptive reasoning models"; `0` disables thinking "except on Fable models" | [env-vars] |
| `API_TIMEOUT_MS` | "Timeout for API requests in milliseconds (default: 600000, or 10 minutes; maximum: 2147483647)" | [env-vars] |
| `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS` | Idle wait for background subagents after the final turn in `-p`; "Default: `600000`, or 10 minutes" | [env-vars] |

What `run_command.py` passes today: `--print`, `--permission-mode dontAsk`, `--allowedTools
"Bash(jira-as *)" Read`, `--output-format stream-json`, `--verbose`, `--add-dir`,
`--append-system-prompt`, and the prompt. No model, no effort, no turn or budget cap
([run_command]). `claude --help` on 2.1.272 lists `--effort`, `--model`, `--max-budget-usd`,
`--permission-mode` and `--permission-prompts`; it does not list `--max-turns`, though the CLI
reference and the `CLAUDE_CODE_MAX_TURNS` variable both document it ([help], [cli-reference],
[env-vars]).

## Limits on a print-mode Run, and what happens at each

**Turns.** A turn is "Maximum agentic turns (tool-use round trips)" in the SDK option table and
"Maximum number of agentic turns (API round-trips) before stopping" in the agent-definition table
([sdk-typescript]). The recorded Run has `num_turns: 3` for three assistant message ids: one that
ran `seq 1 40`, one whose `ls /etc` was denied by `dontAsk`, and the closing text ([fixture]). So a
denied call is a round trip and counts. At the limit, the result line's `subtype` is
`"error_max_turns"` and `terminal_reason` is `"max_turns"`; the error shape still carries
`duration_ms`, `duration_api_ms`, `num_turns`, `total_cost_usd`, `usage`, `modelUsage`,
`permission_denials` and an `errors: string[]` ([sdk-typescript]). The process exits non-zero:
"Claude Code exits with code 0 on success and a non-zero code when the run fails" ([headless]).
The Python SDK's rule of thumb applies to a Receiver reading the stream too: "when a limit you set
ends the run, such as `max_turns` or `max_budget_usd`, it reports an `error_*` subtype", whereas a
failed final request "reports `subtype` `"success"` with the cause in `terminal_reason`"
([sdk-python]).

**Dollars.** `--max-budget-usd` is "compared against the same estimate as `total_cost_usd`"
([sdk-typescript]), and that estimate is "client-side estimates, not authoritative billing data. The
SDK computes them locally from a price table bundled at build time" ([sdk-cost-tracking]). The check
is after the fact: on `error_max_budget_usd`, "`usage` leaves out the response that crossed the
budget, while `total_cost_usd` and `modelUsage` include it" ([sdk-cost-tracking]), so a Run can
overshoot by one response. The recorded Run's `modelUsage` entry says `"costBasis": "list"`
([fixture]): the figure is list price even though the Run authenticated with OAuth
(`apiKeySource: "none"`), so on a subscription it is a proxy for spend, not a bill.

**Time.** No variable or flag caps a Run's wall clock; the env-vars page has timeouts per API
request (`API_TIMEOUT_MS`, 10 minutes), per Bash command (`BASH_MAX_TIMEOUT_MS`, 10 minutes), per
WebFetch, and for the post-final-turn background wait, and nothing else ([env-vars]). A supervisor
that wants a deadline has two signals: "If you stop a `claude -p` run with SIGTERM ... Claude Code
exits with code 143. Claude Code leaves the turn that was in progress unfinished and records no
result for it. To end the turn instead, send SIGINT" ([headless]). SIGINT is the one that yields a
result line.

**`dontAsk` and the caps together.** The docs describe them separately. `dontAsk` "auto-denies
every tool call that would otherwise prompt you ... the session never waits for input"
([permission-modes]); denials "appear as `permission_denied` system messages, and the final result
message lists them in `permission_denials`" ([headless]). Without `--permission-prompts none`,
nothing tells Claude not to retry a denied call, and each retry is another round trip against
`--max-turns`. With it, "Claude is told that nobody can approve the request and not to retry it"
([headless]). The interaction, then, is arithmetic rather than a rule: a turn cap has to leave room
for the denials the skill's guardrails are expected to produce, or the retry has to be switched off.

## Does effort change how many tool calls a Run makes?

Yes, per the platform page that defines the parameter. "The effort parameter affects **all
tokens** in the response, including: Text responses and explanations; Tool calls and function
arguments; Thinking (when active) ... Lower effort also means fewer and terser tool calls"
([effort]). Its tool-use section lists what lower levels "tend to" do, "Combine multiple operations
into fewer tool calls; Make fewer tool calls; Proceed directly to action without preamble", and
what higher levels "may" do, "Make more tool calls; Explain the plan before taking action; Provide
detailed summaries of changes" ([effort]). It also says "Effort is a behavioral signal, not a strict
token budget" ([effort]).

Two model-specific notes bear on a Run that must retrieve evidence. "At `low` effort, Claude Fable
5.1 is less likely than Claude Fable 5 to call a search or retrieval tool, and more likely to answer
from memory" ([prompting-fable-5-1]). And in bash-and-editor loops "where the next independent calls
are implied by the task rather than explicitly requested", Fable 5.1 "may issue them one per turn
instead. This doesn't affect answer quality, but each extra turn costs tokens, a round trip, and
wall-clock time" ([prompting-fable-5-1]). Both push a citation-rule Run toward `high` or above and
toward a prompt that names the queries to run.

The Claude Code page frames effort as thinking depth only: "Lower effort is faster and cheaper for
straightforward tasks, while higher effort provides deeper reasoning for complex problems"
([model-config]). It neither confirms nor contradicts the tool-call statement.

## Cost and time: Opus 5 against Fable 5.1

**Per token.** Every line of Opus 5's price sheet is half of Fable 5.1's except cache reads, which
are $0.50 against $0.25 ([pricing]). For Fable 5.1 to come out cheaper on a Run, cache-read spend
would have to exceed everything else by a wide margin; with a 1-hour cache write of a twenty-thousand
token prompt on every Run, it does not.

**On the recorded Run.** The chapter-one fixture reports 66 input, 20,365 1h-cache-write, 131,802
cache-read and 235 output tokens, `total_cost_usd: 0.45266`, three turns, `duration_ms: 9995`,
`duration_api_ms: 6400`, `ttft_ms: 2479` and `thinking_tokens: 0` ([fixture]). At the Fable 5.1
prices above: 66 x $10 + 20,365 x $20 + 131,802 x $0.25 + 235 x $50, all per million, is $0.00066
+ $0.40730 + $0.03295 + $0.01175 = $0.45266. The harness's bundled price table and the pricing page
agree to the cent, and the 1-hour cache write of the appended prompt and skill was 90% of the
Run's cost. The same tokens at Opus 5 prices: $0.00033 + $0.20365 + $0.06590 + $0.00588 =
$0.27576, or 61% of the Fable figure. That is the price of the *same* tokens; it says nothing about
how many tokens a high-effort Run of the next chapter's skill will produce.

**What effort does to tokens and minutes, measured elsewhere.** Anthropic's cost page reports
runs on its own benchmarks, none of them an incident triage: on research and knowledge-work tasks
with Fable 5, "`low` gave up 1 to 3 points for a third to a half off the cost per task, `medium`
matched the default's accuracy at about 70% to 87% of its cost", and "`low` took 4.5 minutes per
problem on DeepWideSearch, compared with 7.9 minutes at the default"; on a coding subset "Claude
Opus 5 alone matched Claude Fable 5.1 alone at the default (91.7% compared with 92.1%, inside
run-to-run noise) at about 15% less per solved task ($1.01 against $1.19), and Opus 5 at `low`
solved 84.0% for $0.25"; on a research benchmark "Claude Opus 5 at its default scored 71% ... for
$6.71 per task, above Fable 5.1 at its default (65% for $7.12)" ([cost-optimization]). The page's
general advice is "start with Claude Fable 5.1 at `low` effort and raise effort where it misses"
([cost-optimization]); the models overview's is start with Opus 5 ([models-overview]).

**Per-request time.** The models overview rates Fable 5.1 "Slower" and Opus 5 "Moderate", adding
"Actual latency depends on prompt length, output length, and thinking effort" ([models-overview]).
On Fable 5.1 at `xhigh` and `max`, the model "can think for longer before it starts writing its
reply" ([prompting-fable-5-1]); the skill's migration guide puts it more bluntly: "Individual
requests on hard tasks can run many minutes at higher effort (a 15-minute single request is normal
when the task involves gathering context, building, and self-verifying)" ([skill-migration]). Two
harness limits bound a single request: `API_TIMEOUT_MS` at ten minutes ([env-vars]) and the per-
request output cap, 64,000 tokens for Fable 5.1 in the recorded Run ([fixture]), which thinking
counts toward: "`max_tokens` is a hard cap on total output for the request, thinking and response
text combined ... At `high` effort and above, Claude may think extensively and is more likely to
exhaust the budget" ([thinking-cost]). The platform's own default for Opus 5 at `xhigh` or `max` is
"Starting at 64k tokens and tuning from there" ([effort]).

## What this means for the map

1. **Pin the model in `run_command.py`, by full id.** Add `--model claude-opus-5` (or
   `claude-fable-5-1` for the comparison arm). Today the laptop and the container resolve the model
   differently, and the `opus` alias has moved twice this year ([model-config], [fixture]).
2. **Carry effort on the command line or in the container's environment.** `--effort xhigh` is the
   documented launch-time control for `-p`; `CLAUDE_CODE_EFFORT_LEVEL` outranks it and fits the
   Receiver's env file. Say which one the demo uses, because the Transcript will not
   ([sdk-typescript]). Note that `high` is the default: the hypothesis "Opus 5 at high effort" is
   the no-flag configuration, and the first real experiment is `xhigh` ([effort], [model-config]).
3. **The fit-to-slot guards are `--max-turns` and `--max-budget-usd`, plus SIGINT from the
   Receiver.** There is no wall-clock cap. Both caps end the Run with an `error_*` result line the
   log formatter can already render, a non-zero exit, and `permission_denials` intact
   ([sdk-typescript], [headless]). The Receiver should treat those as a finished Run with a partial
   Report, not a crash, and should send SIGINT before SIGTERM if it enforces a deadline of its own.
4. **Size the turn cap for denials, or turn retries off.** Under `dontAsk` a denied call is a turn
   ([fixture]); `--permission-prompts none` (v2.1.259+, the image has 2.1.272) tells Claude not to
   retry ([headless]). The next chapter's Eyes will widen the allow list, which is the other way to
   keep denials out of the turn count.
5. **Measure before choosing; the prices predict the ranking of tokens, not of Runs.** Ticket 11's
   prototype should record, per arm, `num_turns`, `duration_ms`, `duration_api_ms`,
   `thinking_tokens` and `total_cost_usd` from the result line, and the count of tool calls from the
   Transcript, on the same Cascade. Anthropic's own numbers show Opus 5 at default beating Fable 5.1
   at default on cost per task in two of three benchmark families ([cost-optimization]); whether that
   holds for a five-minute triage is exactly what the prototype is for.
6. **The prompt's size is the cost lever chapter one never pulled.** Ninety percent of the recorded
   Run's cost was writing the appended prompt and skill into the 1-hour cache ([fixture],
   arithmetic above). As the one Skill becomes several, that write grows; Runs within an hour that
   share a byte-identical prefix read it at 10% (Opus 5) or 2.5% (Fable 5.1) of input price
   ([pricing]).
7. **`--bare` and the Forwarder-held API key change the price basis, not the price.** A Run on an
   API key is billed at the list prices above; a Run on OAuth reports the same estimate against a
   subscription ([sdk-cost-tracking], [fixture]). Cost per demo (an open item on the map) needs the
   basis decided first.

## Could not verify

- **No live `-p` Run was started** with `--effort`, `--max-turns` or `--max-budget-usd`. The flags
  are documented and two of the three appear in `claude --help` 2.1.272; `--max-turns` is documented
  but absent from that help text. Whether the binary accepts it is a one-command test in ticket 11.
- **That every denied tool call counts as a turn** is read off one fixture (`num_turns: 3`, one
  denial), not stated in any page fetched.
- **Per-turn latency of Opus 5 against Fable 5.1 on this workload.** The docs give comparative
  labels ("Moderate", "Slower") and benchmark minutes on unrelated tasks; no page gives seconds per
  round trip. The five-minute think is a measurement, not a lookup.
- **What Claude Code does when one request exceeds `API_TIMEOUT_MS`** (retry with an `api_retry`
  event, or fail the turn) was not read; only the default was.
- **Whether `--max-budget-usd` behaves identically on OAuth and API-key runs.** It compares against
  the client-side estimate, which the fixture shows is computed on OAuth too, but no page says so.
- **Whether Claude Code sends `output_config.effort` on every request or omits it at the default.**
  The SDK says the init field is "the effort level Claude Code sends on the session's next request,
  or `null` when it sends none" ([sdk-typescript]); either way the API default is `high` ([effort]).
- **Cross-Run cache sharing.** The fixture's first request already read 30,650 cached tokens while
  writing 19,821; that looks like the Claude Code system prompt cached by an earlier session on the
  same account, but no page fetched describes cache scope across separate `claude -p` processes.
- **The skill's cached price table is dated 2026-06-24.** The pricing page fetched today matches it
  for both models; the Sonnet 5 note on that page says a scheduled September price change "will not
  occur", so the page is current as of this month ([pricing]).

## Sources

- [skill] `claude-api` skill, bundled with Claude Code 2.1.271: SKILL.md model table (cached
  2026-06-24), `shared/models.md`, `shared/live-sources.md`
- [skill-migration] `claude-api` skill, `shared/model-migration.md` (Migrating to Claude Fable 5.1,
  "Longer turns by default")
- [pricing] https://platform.claude.com/docs/en/about-claude/pricing
- [models-overview] https://platform.claude.com/docs/en/about-claude/models/overview
- [opus-5] https://platform.claude.com/docs/en/models/opus-5/overview
- [fable-5-1] https://platform.claude.com/docs/en/models/fable-5-1/overview
- [effort] https://platform.claude.com/docs/en/build-with-claude/effort
- [thinking-cost] https://platform.claude.com/docs/en/build-with-claude/thinking-steering-and-cost
- [prompting-fable-5-1] https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1
- [cost-optimization] https://platform.claude.com/docs/en/about-claude/models/optimizing-for-cost-and-intelligence
- [cli-reference] https://code.claude.com/docs/en/cli-reference
- [model-config] https://code.claude.com/docs/en/model-config
- [settings] https://code.claude.com/docs/en/settings
- [settings-reference] https://code.claude.com/docs/en/settings-reference
- [env-vars] https://code.claude.com/docs/en/env-vars
- [permission-modes] https://code.claude.com/docs/en/permission-modes
- [headless] https://code.claude.com/docs/en/headless
- [costs] https://code.claude.com/docs/en/costs
- [sdk-typescript] https://code.claude.com/docs/en/agent-sdk/typescript
- [sdk-python] https://code.claude.com/docs/en/agent-sdk/python
- [sdk-cost-tracking] https://code.claude.com/docs/en/agent-sdk/cost-tracking
- [help] `claude --version` and `claude --help` on this laptop, 2026-09-15 (2.1.272)
- [run_command] `grafana_jsm_sandbox/run_command.py` in this repo
- [fixture] `fixtures/run-transcript.jsonl` in this repo, recorded 2026-09-14 with Claude Code
  2.1.270; the `system/init` line and the `result` line
