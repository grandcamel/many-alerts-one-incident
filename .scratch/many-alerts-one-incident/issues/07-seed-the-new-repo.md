# Seed the new repo

Type: task
Status: resolved
Resolved: 2026-09-15
Blocked by: none

## Question

Create the public repository `grandcamel/many-alerts-one-incident` on GitHub, seeded from this repository's full history, with the branch `many-alerts-one-incident` becoming its `main`, every `research/*` branch pushed alongside, and grafana-jsm-sandbox `main` left untouched. Then move this map's home: update the "Lives on" line at the top of `map.md`, and give the new README a first paragraph that names the lineage and points at chapter one.

Human in the loop: creating a public surface needs the user's approval in chat, and `gh repo create` on this machine needs `env -u GH_TOKEN` (see the project memory on publishing). The answer records the new remote URL and the date.

## Answer

**The repository is `https://github.com/grandcamel/many-alerts-one-incident`, public, created 2026-09-15.** Its default branch is `main`, pushed from `many-alerts-one-incident` and carrying the whole ancestry; the six `research/*` branches are pushed alongside. `grandcamel/grafana-jsm-sandbox` is untouched: its `main` is still `705732d` and nothing was pushed to it. The push went through a second remote named `chapter-two`, one explicit refspec per branch, so `origin` was never a candidate target.

- **Settings, matching chapter one**: wiki off at creation (`--disable-wiki`), Actions off afterwards (`PUT /repos/.../actions/permissions`, `-F enabled=false`, because `-f` sends the string `"false"` and the endpoint rejects it with a 422). Both were read back.
- **The map's home moved** and the README opens with the lineage: chapter one stays where it is, this repository is the one that moves from here, and the paragraph names the map, `CONTEXT.md`, `docs/adr` and the `research/*` branches. The README's title is still `grafana-jsm-sandbox`, which is what the code below it is; the lineage paragraph reconciles the two names rather than renaming the chapter-one demo.
- **`gh` needed `env -u GH_TOKEN`**, as the project memory says: a `GH_TOKEN` is exported in the shell and shadows the keyring account `grandcamel`.

**A pre-publish audit ran first**, six lenses over everything new to the public, every finding put to a skeptic prompted to refute it. The result the audit was for: no secret, no credential and no personal identifier is in anything that publishes. `.env` does hold a live Jira API token and a live Claude Code OAuth token, but it is gitignored, has never been in any commit, and a push carries history rather than files, so it could not leak on this path. The commit identity on every ref is `grandcamel <jasonkrue@gmail.com>`, already public in chapter one.

- **Six factual errors were corrected before the push**, and both bugs the handoff named are gone: the "8 cores" claim (the machine is 4 physical cores and 8 threads) and Mimir stated as fact where the image runs Prometheus. Also Opus 5's cache-read share of input price (10%, not 5%, checked against the `claude-api` skill: $0.50 against $5.00 per MTok), the Docker Desktop version facts (kind by 4.43.0, default at 4.65.0, the Kubernetes view 4.51 and later, not "the 4.4x line"), one rather than two open OOM reports on a 4 vCPU / 8 GiB node, and `mcp-grafana`'s 17.6 MB being the release tarball rather than the binary. The four research documents were corrected on their own branches, each as a named correction commit rather than an amend, so the record shows the fix.
- **What was found and not fixed** is now ticket "Quotations in the research documents": about eleven passages reproducing third-party documentation at length rather than citing it, heaviest in the model-and-effort document. All attributed, none a violation on its face; the user chose to publish as-is and track it.
- **`.gitignore` gained `.claude/worktrees/`**, so the trap that a subagent worktree can be swept in by `git add -A` is closed rather than remembered.

What this settles for the map: the map now lives on `main` in the new repository, and every later ticket's branch belongs there. `git remote -v` in this working copy shows both remotes; `origin` is chapter one and stays read-only for this effort.
