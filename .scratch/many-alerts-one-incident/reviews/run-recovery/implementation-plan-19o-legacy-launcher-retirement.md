# 19o implementation plan: legacy executable closure

Baseline: `72ee0c7`. This is a multi-file, fail-closed refactor.

1. In `grafana_jsm_sandbox/__main__.py`, replace the runtime `serve` body
   with an immediate fixed refusal, and make `main` refuse before parsing
   credentials. Retain historical `Settings` parsing for isolated tests.
   In `grafana_jsm_sandbox/forwarder.py`, close only its standalone `main`
   before credential/sentinel/listener effects; keep its class for tests.
   Verify import/compile and focused startup tests before other edits.
2. In `docker/entrypoint.sh`, refuse the default invocation before any
   onboarding write; preserve explicit command pass-through without that
   write. In `tests/test_startup.py` and `tests/test_container.py`, replace
   launch/onboarding expectations with exact no-construction/no-mutation
   assertions while retaining isolated configuration-parser tests. Add
   bounded subprocess smoke tests for both Python executables. In
   `tests/conftest.py`, make the historical `DEMO_CONTAINER` marker a
   permanent archival skip; likewise quarantine `tests/test_end_to_end.py`.
   Relabel `tests/test_grafana.py`'s live setup directions. Run these focused
   tests and Ruff.
3. At the start of `README.md` and `docs/demo-runbook.md`, mark the legacy
   launch/Compose walkthrough as historical and point to the admission-only
   journaled path. Update `Dockerfile` and the top/runtime comments of
   `docker-compose.yml`; preserve their historical configuration for static
   tests. Update local ticket 37 with the exact unrun boundary.
4. Obtain independent Standards and Spec source reviews, fix findings,
   check protected dirty-file hashes, run the **full suite** after final
   source edits, then stage only this unit's named files and commit locally.

Do not start the demo, build or run containers, use credentials, call native
clients, dispatch a provider request, deploy, push or publish.
