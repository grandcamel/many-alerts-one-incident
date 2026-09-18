# Ticket 33: installed CLI capability facts (offline)

* **Installed surface.** `command -v` resolves `confluence-as` to the local
  plugin venv (`cli/command-v.txt:1`); `--version` reports
  1.1.1 (`cli/version.txt:1`). The root help lists `page`, `permission`, `search`,
  and `space` commands (`cli/help.txt:24-40`). This build has **no** `api`
  command: each attempted local `api --help`, `api search --help`, and `api
  describe --help` reports that command absent (`cli/api-help.txt:1-4`,
  `cli/api-search-help.txt:1-4`, `cli/api-describe-help.txt:1-4`). Thus those stale
  self-discovery forms cannot support a Ticket 33 claim.

* **Native draft command shape.** `page create` exposes `--status
  [current|draft]`, accepts a required space key, and optional parent page ID
  (`cli/page-create-help.txt:5-12`). `page update PAGE_ID` also exposes that status
  choice (`cli/page-update-help.txt:1-11`); `page get PAGE_ID` reads by ID
  (`cli/page-get-help.txt:1-9`). Static installed source forwards `status` in the
  create payload and posts to `/api/v2/pages` ([page_cmds.py:202-224](/Users/jasonkrueger/.as-plugins-venv/lib/python3.13/site-packages/confluence_as/cli/commands/page_cmds.py:202)); it forwards update status to a page PUT
  ([page_cmds.py:308-329](/Users/jasonkrueger/.as-plugins-venv/lib/python3.13/site-packages/confluence_as/cli/commands/page_cmds.py:308)). This supports a native-draft *CLI capability*; no tenant request verified draft creation, retrieval, or permissions.

* **Version behavior.** Update has no caller-supplied expected-version flag
  (`cli/page-update-help.txt:5-11`). Its installed implementation GETs the page,
  reads `version.number`, then PUTs that number plus one
  ([page_cmds.py:308-329](/Users/jasonkrueger/.as-plugins-venv/lib/python3.13/site-packages/confluence_as/cli/commands/page_cmds.py:308)). It is a read-before-write increment, not evidence of a user-controlled optimistic-version contract; race/conflict response behavior is unverified.

* **Scope and grants.** CLI input scopes page operations by `PAGE_ID` and
  creation/space permissions by space key. Page restriction subcommands are
  get/add/remove (`cli/permission-page-help.txt:1-11`); add accepts user/group and
  required `read|update` (`cli/permission-page-add-help.txt:1-12`). Space
  permissions likewise support get/add/remove (`cli/permission-space-help.txt:1-11`). Static source resolves a space key to a space ID before creating and may perform a best-effort create-grant diagnostic only after a create 404 ([page_cmds.py:202-241](/Users/jasonkrueger/.as-plugins-venv/lib/python3.13/site-packages/confluence_as/cli/commands/page_cmds.py:202)). It does not prove effective human/bot read access, tenant namespace existence, or enforcement of a registered-scope policy.

No tenant, credential, or network operation was run.
