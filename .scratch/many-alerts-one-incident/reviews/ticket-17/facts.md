# Ticket 17 — Forwarder facts (offline, 2026-09-18)

## Current implementation

One `JiraCredential` reads `JIRA_SITE_URL`, `JIRA_EMAIL`, and `JIRA_API_TOKEN`; startup accepts HTTP/HTTPS upstream URLs (`grafana_jsm_sandbox/forwarder.py:67-106`). `Forwarder` binds only loopback, returns an HTTP URL, and holds one process-global active sentinel under a lock (:109-125,144-173). It is not route-specific or multi-Run.

`RunSpawner` creates/registers the sentinel before execution and clears it in a `finally` block (`grafana_jsm_sandbox/run_spawner.py:112-120`). Its rebuilt Run environment supplies the Forwarder URL, Jira email and sentinel, never the real token (:162-180). Tests prove rejection before registration, after clearing, and after replacement, while the upstream sees real Basic auth rather than the sentinel (`tests/test_forwarder.py:39-97`).

The handler serves GET, POST, PUT, DELETE and PATCH (`forwarder.py:210-232`). It drops Run-supplied Authorization/Host/hop headers, takes scheme/netloc/base path only from configured site, preserves requested path/query, then adds Basic auth (:49-53,154-207,262-290). The absolute-target test proves the request cannot select the upstream (`tests/test_forwarder.py:233-241`); method/path/body pass through (:100-125).

The opener does not follow upstream redirects (`forwarder.py:235-246`), but the Forwarder sends the status and `Location` response back to its client (:161-165,267-273; test `tests/test_forwarder.py:243-254`). Current tests do not establish whether `jira-as` or a future client follows that returned 3xx. Logs carry method/path/status but test-prove no real token, sentinel, or Authorization (`forwarder.py:157-165,191-193`; `tests/test_forwarder.py:152-165`).

## Process, control plane, and CA

Today it is a thread in the Receiver’s main process, not a sidecar/container (`grafana_jsm_sandbox/__main__.py:1-6,114-146`). Run authority is only `Bash(jira-as *)` and `Read` (`grafana_jsm_sandbox/run_command.py:30-34,62-80`). The current Forwarder has no Grafana/Confluence/Kubernetes route or bearer credential handling, and Run authority does not include `kubectl` or a sidecar control command.

Docker points Python/requests, curl, pip, and Node at the system CA bundle (`Dockerfile:63-67`); RunSpawner passes only named CA variables from Receiver to a Run (`run_spawner.py:49-64,90-93,162-180`). This covers outbound TLS. Current loopback Forwarder is plain HTTP and has no TLS listener/certificate/key (`forwarder.py:123-125`; ADR0002:1-8).

## Confluence and planned boundary

Installed `confluence-as` 1.1.1 reads `CONFLUENCE_SITE_URL`, `CONFLUENCE_EMAIL`, and `CONFLUENCE_API_TOKEN`, and requires HTTPS (`/Users/jasonkrueger/.as-plugins-venv/lib/python3.13/site-packages/confluence_as/config_manager.py:52-88`; `/Users/jasonkrueger/.as-plugins-venv/lib/python3.13/site-packages/assistant_skills_lib/validators.py:229-266`). It cannot target today’s HTTP Forwarder unchanged. Current Forwarder only models one Jira Basic credential (`forwarder.py:79-85,203-207`); it does not prove Jira and Confluence can share one credential or model several sites/schemes.

Ticket 17’s sidecar/multi-site language is planning, not source (`.scratch/many-alerts-one-incident/issues/17-the-forwarders-growth.md:7-24`). ADR0007 says Forwarder “becomes a sidecar” and secrets become Kubernetes Secrets (`docs/adr/0007-one-digitalocean-node-with-everything-in-the-cluster.md:16-18`), but says “a pod is still one container” (line 17), which contradicts an actual sidecar: an explicit Receiver/Run main container plus a Forwarder sidecar is the accurate planned topology. ADR0007 otherwise does not specify routes, TLS, CA, credentials, Grafana auth, or Kubernetes access; Grafana remains unexposed (:16,20).

No live calls, credential use, container, cluster, or client behavior ran. Unverified: Confluence via a TLS/patched Forwarder; client behavior after a returned redirect; credential sharing; Grafana/Kubernetes auth; and sidecar network/CA/secret partitioning.
