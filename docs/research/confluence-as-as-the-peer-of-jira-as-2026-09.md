# confluence-as as the peer of jira-as (September 2026)

Written 2026-09-15. Question: what can `confluence-as` 1.1.1 do, and does it fit the
chapter-one boundary unchanged? The boundary is ADR 0002 (credentials live in a loopback
Forwarder; a Run holds a sentinel), ADR 0003 (`dontAsk` with an allow list that denies a
multi-line command whole) and ADR 0005 (a minimal image; `jira-as` in its own venv at
`/opt/jira-as`, no `curl`, no `jq`).

**Method.** Local only. Everything below was read off the copy installed on this machine
(`~/.as-plugins-venv`, `confluence-as --version` prints `confluence-as, version 1.1.1`),
its `--help` output, its source under `site-packages/`, the `jira-as` 2.0.0 source beside it,
the plugin docs in `~/.claude/plugins/cache/as-plugins/`, and this repo's Forwarder and
spawner. Four operations were exercised in the CLI's own offline mock mode
(`CONFLUENCE_MOCK_MODE=true`), and both CLIs were pointed at `http://127.0.0.1:9`, a loopback
port with no listener, to see how each treats a plain-http site URL. No request left the
machine and the live Atlassian site was not called; what that leaves unverified is listed at
the end. Citations are the command run or the file read, with line numbers where they matter.

## Short answer

1. **It does the five things the chapter needs, each on one line.** Page read, CQL search,
   page create, page update and page comment are all single `confluence-as` commands with
   `-o json` output, listed in the table below. There is no `api search` / `api describe`
   layer: `confluence-as api --help` answers `No such command 'api'`, and the ticket's
   `confluence-as help` answers `No such command 'help'`. Discovery is `--help` on each of
   its sixteen groups.
2. **Same shape of credential, different variable names, and the Forwarder's single-site rule
   covers `/wiki`.** It reads `CONFLUENCE_SITE_URL`, `CONFLUENCE_EMAIL`, `CONFLUENCE_API_TOKEN`
   where jira-as reads the `JIRA_` three; both send HTTP basic auth with the token as the
   password, which is exactly what the Forwarder inspects. Every Confluence request is
   `<site>/wiki/api/v2/...` or `<site>/wiki/rest/api/...`, and the Forwarder appends a request's
   path to the one configured site, so a Confluence call through it lands on the same host
   the Jira calls do.
3. **It does not fit unchanged, for one reason: confluence-as refuses a plain-http site URL,
   and the Forwarder is plain http on loopback.** `CONFLUENCE_SITE_URL=http://127.0.0.1:9
   confluence-as page get 12345` exits 1 with `[validation] URL must use HTTPS` before opening
   a socket; jira-as with the same URL goes ahead and connects. The check is one argument in
   confluence-as's config manager. Either confluence-as learns to accept http the way jira-as
   does, or the Forwarder learns TLS. That is a map decision; the options are laid out below.
4. **One pip package, `confluence-as`, pinned `==1.1.1`, and it can share jira-as's venv.** Its
   three dependencies (`assistant-skills-lib`, `click`, `requests`) are already in jira-as's
   closure; `pip check` on the venv holding both reports nothing broken; it adds 1.2 MB on
   disk. The plugin author's own runtime image and this laptop both use one shared venv.
5. **Nothing it needs is missing from the image, and the five operations write no files,
   with one exception.** It imports `click`, `requests`, `urllib3` and the standard library;
   no subprocess, no external tool, a hand-rolled Markdown parser. `search cql` appends every
   successful query to `~/.cache/confluence-assistant-skills/cql_history.json`, which the
   tmpfs home in ADR 0005 already absorbs. Markdown-to-storage conversion only happens for
   `--file` with a `.md` suffix; a `-b` body is sent verbatim as storage XHTML, which is the
   one-line form a Run must use.

## The operations

Endpoints are the ones each command's source calls; the client prefixes every one with
`/wiki` (`confluence_client.py:165-185`). "Mock" is what happened under
`CONFLUENCE_MOCK_MODE=true` on this machine.

| Need | One-line invocation | Requests it makes | Mock |
| --- | --- | --- | --- |
| Read a page | `confluence-as page get 12345 --body --format markdown -o json` | `GET /wiki/api/v2/pages/12345?body-format=storage`; markdown is converted locally from storage (`page_cmds.py:121-127`) | exit 0, body rendered |
| Search by CQL | `confluence-as search cql "space = OPS AND type = page AND title ~ 'checkout'" -l 10 -o json` | `GET /wiki/rest/api/search?cql=...`, paginated (`search_cmds.py:255-256`); then writes the history file (`:263`) | not implemented in the mock |
| Create a page | `confluence-as page create -s OPS -t "OPS-12 checkout latency" -b "<h2>Root cause</h2><p>One line of storage XHTML.</p>" -o json` | `GET /wiki/api/v2/spaces?keys=OPS` to resolve the key (`helpers.py:13-33`), then `POST /wiki/api/v2/pages` (`page_cmds.py:222`) | exit 0, body echoed as `representation: storage` |
| Update a page | `confluence-as page update 12345 -b "<p>Second version.</p>" -m "Run 2 appended" -o json` | `GET /wiki/api/v2/pages/12345`, then `PUT` with `version.number + 1` and the message (`page_cmds.py:309-327`) | exit 0, version 1 became 2 |
| Comment | `confluence-as comment add 12345 "<p>Seen again in Run 3.</p>" -o json` | `POST /wiki/api/v2/footer-comments` with `pageId` in the body (`comment_cmds.py:215-216`) | not implemented in the mock |

Facts that shape how a Run would write these:

- **A `-b` body is storage XHTML, verbatim.** `page create` sets `is_markdown = False` for
  `--body` and converts only when `--file` names a `.md`/`.markdown` file
  (`page_cmds.py:193-205`, `helpers.py:69-77`); `comment add` sends its positional body as-is
  (`comment_cmds.py:197-202`). The `--help` text "Markdown or XHTML" is about the two routes,
  not about `-b`. So structure on one line comes from tags, `<h2>..</h2><p>..</p>`, not from
  newlines. The mock run confirmed the tags pass through untouched.
- **A Run cannot take the `--file` route today.** The allow list is `Bash(jira-as *)` and
  `Read` (`grafana_jsm_sandbox/run_command.py:33`); nothing lets a Run write the file. Either
  the Receiver stages one, or the Run writes XHTML on one line.
- **`-o json` is per command, and a global `-o json` before the subcommand also works**
  (`confluence-as --help`; plugin `skills/confluence-search/SKILL.md:150`). Same flag as
  jira-as, which `reset.py` already passes as `-o json`.
- **Pagination stays behind the Forwarder.** `paginate` pulls only the `cursor=` value out of
  `_links.next` and re-issues the request against its own base URL
  (`confluence_client.py:646-671`); it never follows an absolute link.
- **Two calls where one looks like one.** Create resolves the space key first; update reads
  the page first for its version number. Comment `list` also reads the page for its title
  (`comment_cmds.py:92`). Each is a Forwarder round trip, not a concern, but the Transcript
  will show them.
- **No site guard.** jira-as has `JIRA_ALLOW_SITE_OPERATIONS` and `JIRA_ALLOWED_PROJECTS`
  (`jira_as/config_manager.py:211,233`); confluence-as has nothing comparable (`grep -rn
  ALLOW confluence_as/` finds one unrelated comment). What a Run can write is whatever
  space the account behind the Forwarder can write.
- **Mock mode exists.** `CONFLUENCE_MOCK_MODE=true` returns a seeded in-memory client before
  credentials are read (`config_manager.py:94-113`, `mock/base.py:20-22`); page get, create
  and update work offline, search and comments raise `NotImplementedError`. A rehearsal
  fixture could lean on the first three.

## Authentication and the base URL

| | jira-as 2.0.0 | confluence-as 1.1.1 |
| --- | --- | --- |
| Site variable | `JIRA_SITE_URL` | `CONFLUENCE_SITE_URL` |
| Email variable | `JIRA_EMAIL` | `CONFLUENCE_EMAIL` |
| Token variable | `JIRA_API_TOKEN` | `CONFLUENCE_API_TOKEN` |
| Where read | `jira_as/config_manager.py:97-99` via `get_credential_from_env` | `confluence_as/config_manager.py:62-64` via the same method |
| Unprefixed fallback | `SITE_URL`, `EMAIL`, `API_TOKEN` (`assistant_skills_lib/config_manager.py:131-140`) | same |
| Scheme check | `validate_url(url)`, `require_https` defaults to `False` (`jira_as/config_manager.py:143`; `assistant_skills_lib/validators.py:204-266`) | `validate_url(url, require_https=True)` (`confluence_as/config_manager.py:85`) |
| Observed with `http://127.0.0.1:9` | connects; `HTTP transport failed: ConnectionError`, exit 1 | `[validation] URL must use HTTPS`, exit 1, no connection attempted |
| Auth on the wire | basic, `auth=(email, api_token)` (`jira_client.py:275`) | basic, `session.auth = (email, api_token)` (`confluence_client.py:154`) |
| Base URL | `base_url.rstrip("/")`, then `f"{base_url}{endpoint}"` with `/rest/api/3/...` (`jira_client.py:53,124`) | strip `/` and a trailing `/wiki`, then `f"{base_url}/wiki/{endpoint}"` for every endpoint (`confluence_client.py:70-73,165-185`) |
| Settings files | `.claude/settings.json` and `settings.local.json`, found by walking up from cwd, key `jira` | same walk, key `confluence` (`assistant_skills_lib/config_manager.py:51-99`) |
| Keychain at runtime | optional, guarded | the CLI path is `get_confluence_client()` -> `ConfigManager.get_credentials()` (`cli_utils.py:54`), env only; the keychain class is not on that path |

The documented names match the code: plugin `confluence-assistant-skills` 2.0.1
`README.md:139-141,207-209` and `commands/confluence-assistant-setup.md` name the
`CONFLUENCE_` three; `jira-assistant-skills` 5.0.0 `README.md:140-142,196-198` names the
`JIRA_` three.

**What the Forwarder does with a Confluence request.** `Forwarder._upstream_url` joins the
configured site's scheme, host and path with the request's path and query and nothing else;
`_presented_sentinel` reads the basic-auth password; `_StopAtRedirect` refuses to follow a
3xx off the site (`grafana_jsm_sandbox/forwarder.py`). A Run's
`GET http://127.0.0.1:<port>/wiki/api/v2/pages/1` with the sentinel as password would be sent
to `https://<site>.atlassian.net/wiki/api/v2/pages/1` with the real basic-auth header. The
single-site rule holds because `/wiki` is a path on the same host; nothing in the Forwarder
needs to know Confluence exists. The Run's environment is built from scratch in
`RunSpawner._environment` (`run_spawner.py`), so adding the three `CONFLUENCE_` names, with
the Forwarder URL, the same email and the same sentinel, is three lines there. The `ALLOWED_TOOLS`
tuple gains `Bash(confluence-as *)`.

**Why it still does not fit unchanged.** The Forwarder is `http://127.0.0.1:<port>` by design
(ADR 0002 says in words that jira-as "accepts an http site URL, so no patching is needed").
confluence-as will not start a request to that URL. The generic `SITE_URL` fallback does not
help; the same validator runs on it. The ways out, for the map to choose between:

1. **confluence-as accepts http.** One argument at `confluence_as/config_manager.py:85`
   (`require_https=True` to the default, or gated on a variable such as
   `CONFLUENCE_ALLOW_HTTP`), a release, and a new pin. It is the same package author as
   jira-as, and it makes the two peers behave alike. `credential_manager.py:147` builds its
   test URL the same way behind another `require_https=True`, but the CLI does not go
   through that class.
2. **The Forwarder speaks TLS on loopback.** A self-signed certificate for `127.0.0.1`,
   `ssl.wrap` around the `ThreadingHTTPServer`, and the certificate in the image's one trust
   bundle, which every client in the image already reads (`Dockerfile` `ENV SSL_CERT_FILE
   ... REQUESTS_CA_BUNDLE ...`; the Run inherits exactly those, `run_spawner.py`
   `TRUST_STORE_VARIABLES`). No change to confluence-as; more moving parts in the demo's
   own code, and a certificate to mint at build or at start.
3. **The cheap version of 2 is a word the audience will ask about.** confluence-as reads
   `confluence.api.verify_ssl` from a `.claude/settings.json` found by walking up from the
   Run's working directory (`config_manager.py:44-50`, `assistant_skills_lib/config_manager.py:51-99`),
   so `/app/.claude/settings.json` with `{"confluence": {"api": {"verify_ssl": false}}}`
   would let the Forwarder use an untrusted certificate. It works and it is the wrong lesson
   for a demo about boundaries.

## The package and the image

| Fact | Value | Source |
| --- | --- | --- |
| PyPI name, version | `confluence-as` 1.1.1, MIT, `github.com/grandcamel/confluence-as` | `pip show confluence-as` |
| Entry point | `confluence-as = confluence_as.cli.main:cli` | `confluence_as-1.1.1.dist-info/entry_points.txt` |
| Python | `>=3.10` (jira-as: `>=3.10`) | `METADATA` of each |
| Runtime dependencies | `assistant-skills-lib>=1.0.0`, `click>=8.0.0`, `requests>=2.28.0` | `confluence_as-1.1.1.dist-info/METADATA` |
| jira-as's runtime dependencies | `as-engine<0.2,>=0.1.0a0`, `assistant-skills-lib>=1.0.0`, `click>=8.0`, `colorama`, `nest-asyncio`, `python-dotenv`, `requests>=2.28.0`, `tabulate`, `tqdm` | `jira_as-2.0.0.dist-info/METADATA` |
| Both in one venv | `No broken requirements found.` | `~/.as-plugins-venv/bin/pip check` |
| Installed size | 1.2 MB with bytecode (`cli/` 800 KB, `mock/` 116 KB); 40 `.py` files, 519 KB of source | `du -sh site-packages/confluence_as`; `find ... -name '*.py' \| xargs cat \| wc -c` |
| jira-as for comparison | 11 MB, of which `specs/` is 4.6 MB | `du -sh site-packages/jira_as{,/specs}` |
| The pin as documented | `pip install "confluence-as>=1.1.1"`, a floor | plugin `README.md:128,154`; `commands/confluence-assistant-setup.md` |
| Precedent for a shared venv | the assistant-skills runtime image makes one `~/.assistant-skills-venv` for every `*-as` package; this laptop has both CLIs in `~/.as-plugins-venv` | `as-plugins/assistant-skills/1.3.3/docker/runtime/Dockerfile`; `ls ~/.as-plugins-venv/bin`; `~/.zshrc:4` |

So: `ARG CONFLUENCE_AS_VERSION=1.1.1` beside `ARG JIRA_AS_VERSION=2.0.0`, one `pip install` of
both into the existing venv, and a second symlink into `/usr/local/bin`. Sharing costs 1.2 MB
and brings no new dependency; a second venv would duplicate about 5 MB of `click`, `requests`,
`urllib3`, `certifi`, `charset_normalizer`, `idna` and `assistant_skills_lib` plus a 12 MB
`pip` of its own (`du -sh` of each). The one thing sharing changes is a name: ADR 0005 calls
the venv `/opt/jira-as` because it held one tool. Two tools in it want a name that says so,
or the ADR wants a sentence saying the name is historical.

`ls /usr/local/bin` would then answer `claude`, `confluence-as`, `jira-as`, `node`, `nodejs`,
`npm`, `npx`.

## Files and tools

- **Imports.** Across the package: `click`, `requests`, `urllib3.util.retry`, and the standard
  library; no `subprocess`, no `shutil.which`, no `os.system` (`grep -rhn -E "^import
  |^from " confluence_as/`). The Markdown parser is regular expressions in
  `markdown_parser.py`; `markdown-it-py` in this venv belongs to `rich`, not to confluence-as.
  Nothing calls `curl` or `jq`.
- **Reads.** `--file` on create, update and comment reads one file (`helpers.py:52-66`).
  Settings files are read if found on the walk up from cwd; in the container that walk goes
  `/app/runs/<id>` -> `/app/runs` -> `/app` -> `/`, so a `/app/.claude/settings.json` would
  count.
- **Writes by the five operations.** `search cql` calls `_add_to_history` after every
  successful query, which does `mkdir -p ~/.cache/confluence-assistant-skills` and rewrites
  `cql_history.json`, capped at a hundred entries (`search_cmds.py:152-194,263`). Page get,
  create and update, and comment add, write nothing: the mock run with `HOME` pointed at an
  empty directory produced no files. ADR 0005 puts the Run user's home on tmpfs, so the
  history write succeeds; under a read-only root with no tmpfs home it would fail the search
  after the results were fetched.
- **Writes by operations the chapter does not need.** `attachment download` and `attachment
  upload` (`attachment_cmds.py:248,292`), `search export` and `search stream-export`
  (`search_cmds.py:572-762`), and `ops cache-*` under `~/.confluence-skills/cache`
  (`ops_cmds.py:35`).
- **The multi-line rule.** Every invocation above is one line, and every body is one line.
  Whether `$'...\n...'` counts as one line to the allow list was not tested here.

## What this means for the map

- **confluence-as is the peer of jira-as in every respect but one**: variable names differ by
  prefix, the auth shape is identical, the Forwarder needs no change for `/wiki`, the venv
  and the image absorb it in a few lines. The one respect is the https check, and it is a
  blocking one: with confluence-as as released, a Run cannot reach the Forwarder. The ticket
  "one Forwarder or one per site" (map, "Not yet specified") gains a prerequisite: one
  Forwarder is fine, but it must be one confluence-as will talk to. Options 1 and 2 above
  are the choice; a decision belongs in an ADR next to 0002, because it amends what 0002
  says about "plain http".
- **The Skill for Memory writes storage XHTML on one line.** No Markdown route exists for a
  Run without a Write tool. The Report's Confluence shape is therefore tags, and the Skill
  should show the tags, the way the incident-sync Skill shows jira-as invocations.
- **The credential's Confluence scope is the boundary.** With no space guard in
  confluence-as, the "which Confluence space" ticket is also a question of what the OPS
  account can write; a dedicated space with the account's write restricted to it is the
  control, and it lives in Confluence, not in the image.
- **Allow list and environment**: `Bash(confluence-as *)` in `ALLOWED_TOOLS`; `CONFLUENCE_SITE_URL`,
  `CONFLUENCE_EMAIL`, `CONFLUENCE_API_TOKEN` in `RunSpawner._environment`, pointing at the
  same Forwarder with the same sentinel. The Forwarder's variables stay `JIRA_*` for the
  real site; a rename to something site-scoped is cosmetic and can wait.
- **Rehearsal**: mock mode covers page get, create and update offline; search and comment
  need the live site or a fixture of a different kind.

## Could not verify

- That the API token behind the Forwarder is accepted by Confluence on the same site, that
  Confluence is provisioned on that site, and which spaces the account can read or write.
  Atlassian API tokens are per account, not per product, but that was not exercised.
- The live output of `search cql` and `comment add`, and the shape of a real
  `/wiki/rest/api/search` result; the mock implements neither.
- End-to-end passage of a Confluence request and response through the Forwarder; reasoned
  from `forwarder.py`, not run, because the Forwarder would have needed the live site.
- Whether the upstream `confluence-as` repository already has, or would accept, an option to
  allow http; GitHub was not fetched.
- Whether ADR 0003's line rule treats `$'..\n..'` as one line.
- That `confluence-as==1.1.1` installs cleanly on the image's Debian trixie `python3`; the
  `pip check` above ran on macOS with Python 3.13.7.

## Sources

Commands, all run 2026-09-15 on this machine:

- `~/.as-plugins-venv/bin/confluence-as --version`, `--help`, `help`, `api --help`, and
  `--help` on `page`, `search`, `comment`, `ops`, `jira`, `page get`, `page create`, `page
  update`, `search cql`, `search content`, `comment add`, `comment list`
- `~/.as-plugins-venv/bin/pip show -f confluence-as`, `pip show jira-as`, `pip list`, `pip check`
- `du -sh` on `site-packages/{confluence_as,jira_as,assistant_skills_lib,as_engine,click,requests,urllib3,certifi,charset_normalizer,idna,pip}`
- `CONFLUENCE_SITE_URL=http://127.0.0.1:9 CONFLUENCE_EMAIL=demo@example.com CONFLUENCE_API_TOKEN=sentinel confluence-as page get 12345`
- `JIRA_SITE_URL=http://127.0.0.1:9 JIRA_EMAIL=demo@example.com JIRA_API_TOKEN=sentinel jira-as search jql "project = OPS" -o json`
- `CONFLUENCE_MOCK_MODE=true confluence-as page get 100001 --body --format markdown`, and a
  script driving `confluence_as.cli.main:cli` with `HOME` set to an empty directory for
  `search cql`, `page create`, `page update`, `comment add`

Files read, under `~/.as-plugins-venv/lib/python3.13/site-packages/`:

- `confluence_as/config_manager.py`, `credential_manager.py`, `confluence_client.py`,
  `markdown_parser.py`, `mock/base.py`, `cli/main.py`, `cli/cli_utils.py`, `cli/helpers.py`,
  `cli/commands/{page,search,comment,attachment,ops}_cmds.py`
- `jira_as/config_manager.py`, `jira_client.py`, `validators.py`
- `assistant_skills_lib/config_manager.py`, `credential_manager.py`, `validators.py`, `cache.py`
- `confluence_as-1.1.1.dist-info/{METADATA,entry_points.txt}`, `jira_as-2.0.0.dist-info/METADATA`,
  `assistant_skills_lib-1.0.1.dist-info/METADATA`, `as_engine-0.1.1.dist-info/METADATA`

Plugin docs, under `~/.claude/plugins/cache/as-plugins/`:

- `confluence-assistant-skills/2.0.1/README.md`, `commands/confluence-assistant-setup.md`,
  `.claude/settings.json`, `skills/confluence-{assistant,page,search,comment}/SKILL.md`
- `jira-assistant-skills/5.0.0/README.md`, `skills/jira/SKILL.md`
- `assistant-skills/1.3.3/docker/runtime/Dockerfile`, `README.md`

This repo: `docs/adr/0002-jira-token-behind-localhost-forwarder.md`,
`docs/adr/0003-runs-use-dontask-with-jira-as-allowlist.md`,
`docs/adr/0005-container-is-the-boundary-minimal-image.md`, `Dockerfile`,
`docker/entrypoint.sh`, `grafana_jsm_sandbox/forwarder.py`, `run_spawner.py`, `run_command.py`,
`reset.py`.
