# confluence-as as the peer of jira-as

Type: research
Status: resolved
Resolved: 2026-09-15, by a research subagent
Blocked by: none

## Question

What can `confluence-as` 1.1.1 do, and does it fit the chapter-one boundary unchanged? Facts:

- Its operations: read a page, search by CQL, create and update a page, comment; each with a one-line example invocation, since the allow list denies multi-line commands.
- Its authentication: whether it reads the same Atlassian site URL, email and API token variables as `jira-as` or different names, and how its base URL is formed, so that the Forwarder's single-site rule (ADR 0002) either covers `/wiki` or does not.
- The pip package name and how it pins, its installed size, and whether it can share `jira-as`'s virtual environment in the image (ADR 0005).
- Whether any operation writes files or needs a tool the image does not have.

Local first: run `confluence-as --help` and `confluence-as help` from `~/.as-plugins-venv/bin`, then `confluence-as api search` and `confluence-as api describe` on the operations above, then `pip show` in that venv. Read the `jira-assistant-skills` plugin documentation in this machine's Claude plugin cache for the credential variable names. Do not call the live Confluence site.

## Answer

Findings: `docs/research/confluence-as-as-the-peer-of-jira-as-2026-09.md` on branch `research/confluence-as-as-the-peer-of-jira-as` (commit 54c167f). Everything below was established offline, from the installed CLI's help, its source in `~/.as-plugins-venv`, its mock mode, and the plugin docs; the live site was not called.

- **Operations, each one line with `-o json`**: `page get <id> --body --format markdown`, `search cql "space = OPS AND type = page" -l 10`, `page create -s OPS -t "Title" -b "<h2>..</h2><p>..</p>"`, `page update <id> -b "<p>..</p>" -m "why"`, `comment add <id> "<p>..</p>"`. A `-b` body is sent verbatim as Confluence storage XHTML; Markdown converts only through `--file`, which a Run with no Write tool cannot produce. So a Run writes tags on one line, and the Skill shows the tags the way the incident-sync Skill shows `jira-as` invocations.
- **Credentials**: `CONFLUENCE_SITE_URL`, `CONFLUENCE_EMAIL`, `CONFLUENCE_API_TOKEN`, the same reader and the same basic auth as the `JIRA_*` trio, every request at `<site>/wiki/...`. The Forwarder appends the path to its one site, so the single-site rule of ADR 0002 covers `/wiki` unchanged.
- **The one blocker**: `confluence-as` validates the site URL with `require_https=True` (`config_manager.py:85`). Pointed at `http://127.0.0.1:<port>` it exits 1 with "URL must use HTTPS" before connecting, where `jira-as` connects. As released it cannot reach the Forwarder. The choice is an upstream change so `confluence-as` accepts plain http (a new release, then a pin), or the Forwarder speaking TLS on loopback. Either amends what ADR 0002 says about plain http and wants an ADR beside it.
- **Package**: PyPI `confluence-as`, pin `==1.1.1`, 1.2 MB, dependencies (`assistant-skills-lib`, `click`, `requests`) already in `jira-as`'s closure, `pip check` clean with both in one venv. Share `/opt/jira-as` and footnote the name in ADR 0005. Nothing needs `curl` or `jq`. `search cql` writes a history file under the home directory, which the tmpfs home absorbs; the other four write nothing.
- **No space guard**: the account's Confluence scope is the write boundary. A dedicated space with the account's write restricted to it is the control, and it lives in Confluence, not the image.
- **Rehearsal**: mock mode (`CONFLUENCE_MOCK_MODE=true`) covers page get, create and update offline; search and comment need the live site or a fixture of another kind.

What this settles for the map: "Memory" is unblocked and knows its write shape. The Forwarder question in the fog is sharp enough to ticket now; see "The Forwarder's growth". The allow list gains `Bash(confluence-as *)`, and the Run's environment gains the three `CONFLUENCE_*` variables pointing at the same Forwarder with the same sentinel.

Could not verify offline: whether the OPS account's token has Confluence access and to which spaces; live output of `search cql` and `comment add`; end-to-end passage through the Forwarder; whether upstream already has an http option; install on the image's Debian Python.
