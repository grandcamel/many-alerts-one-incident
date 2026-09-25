# 19p implementation plan: isolated permit lifecycle

Baseline: `fdd0f95`. Multi-file source change, no live route wiring.

1. Add `grafana_jsm_sandbox/forwarder_permit_model.py` with strict immutable
   binding validation and a bounded identity-owned, locked in-memory
   `PermitBook` for L1/L2 transitions, explicit close, 32-open capacity and
   2,048 lifetime tombstones. Use fixed denial codes, no clock
   sampling, random value, I/O, trusted-reply claim or Receiver call. Keep
   the module absent from runtime imports.
2. Add `tests/test_forwarder_permit_model.py` for exact transitions and
   mismatches, forged/copy/replay, duplicate staging before and after close,
   both capacity ceilings,
   expiry/restart, fixed errors and the
   absence of runtime imports or route-catalog changes. Run focused tests
   and Ruff; verify existing gate/exchange tests remain green.
3. Document the no-authority boundary in `docs/forwarder-control.md` and
   update local tickets 36/37 truthfully. Obtain independent Standards and
   Spec source review, fix findings, read back protected dirty files, run
   the full local suite, then stage exact files and commit locally.

No provider/native/tenant/venue experiment, credential use, live permit,
effect writer, deployment, push or publication is part of this unit.
