# Which model, at what effort, on a headless Run

Type: research
Status: resolved
Resolved: 2026-09-15, by a research subagent
Blocked by: none

## Question

How are the model and the effort set for a Claude Code print-mode Run, and what does a high-effort Opus 5 Run cost in time and money against a Fable 5.1 one? Facts:

- The CLI flags, settings or environment variables that select the model and the effort for `claude -p`, and whether effort is settable at all on a headless Run.
- The model ids for Opus 5 and Fable 5.1, their prices per input and output token, and their context windows.
- Any turn or time limits on a print-mode Run, how `--max-turns` interacts with `dontAsk`, and what happens at the limit.
- Whether raising effort is documented to change the number of tool calls a Run makes.

Load the `claude-api` skill first and take model ids and prices from it and from the documentation it points at, never from memory. Also read `grafana_jsm_sandbox/run_command.py` in this repo for the flags chapter one already uses.

## Answer

Findings: `docs/research/model-and-effort-on-a-headless-run-2026-09.md` on branch `research/model-and-effort` (commit eae6b56). Every claim there is cited to code.claude.com, the pricing page, or this repo's fixture; nothing below is from memory.

- **Model** is `--model <alias|id>`, overriding the `model` settings key and `ANTHROPIC_MODEL`. The `opus` alias means Opus 5 from Claude Code 2.1.219 and `fable` means Fable 5.1 from 2.1.257, and both aliases have moved this year, so pin by full id. `run_command.py` passes no model today, so a Run inherits whatever the host or container resolves: the fixture ran `claude-fable-5-1` while the account default is Opus 5.
- **Effort** is settable on a headless Run: `--effort low|medium|high|xhigh|max` at launch, or `CLAUDE_CODE_EFFORT_LEVEL` in the environment, which outranks the flag. `high` is the default, so "Opus 5 at high effort" is the no-flag configuration and the first real experiment is `xhigh`. The Transcript's `init` line does not report effort, so the demo must say which it used.
- **Prices**: `claude-opus-5` is $5 in / $25 out per million tokens; `claude-fable-5-1` is $10 / $50. Both have a 1M context and 128K max output. Re-pricing chapter one's recorded Run at Opus 5 rates gives $0.28 against the recorded $0.45, and ninety percent of that Run's cost was the one-hour cache write of the prompt and Skill.
- **Limits**: `--max-turns` and `--max-budget-usd` end a Run with an `error_max_turns` or `error_max_budget_usd` result line that still carries cost, usage and denials, and a non-zero exit. There is no wall-clock cap; SIGINT yields a result line, SIGTERM does not. Under `dontAsk` a denied call consumes a turn; `--permission-prompts none` (2.1.259+, the image has 2.1.272) stops retries. The platform docs say lower effort means fewer and terser tool calls; the Claude Code docs are silent on it.

What this settles for the map: the timing prototype ("Does a high-effort Run fit the slot") compares Opus 5 at `xhigh` and at default against Fable 5.1 on the same canned Cascade, recording turns, duration, thinking tokens, cost and tool-call count from the result line and Transcript. The Receiver's fit-to-slot guards are the two caps plus SIGINT, treated as a finished Run with a partial Report. Cost per demo needs the billing basis decided first: API key at list price, or OAuth against a subscription.

Could not verify without a live Run: the flags untested here; `--max-turns` absent from `claude --help` at 2.1.272 though documented; per-turn seconds for either model; behaviour when `API_TIMEOUT_MS` is exceeded; whether the budget cap applies on OAuth; cache scope across Runs.
