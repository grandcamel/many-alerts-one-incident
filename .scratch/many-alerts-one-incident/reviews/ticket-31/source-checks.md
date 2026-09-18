# Source checks for ticket 31

Read-only inspection; no model Run, Jira call, Receiver execution or demo.

The current replay entry point fixes SEQUENCE to three legacy files (grafana_jsm_sandbox/replay.py:25-29), sends HTTP POSTs (:50-58), and exposes only --receiver and --pause (:77-86). tests/test_replay.py:24-32 expects three HTTP202 responses and three Runs. tests/conftest.py:95-98 provides a controllable Run-spawner gate; :109-119 records and blocks the real Receiver's spawn call. These are available seams, not an implemented Cascade fixture harness.

Captured Alert projections below are independently read from the committed ticket14 extracts. They identify body inputs for synthetic controlled arrival sequences; source arrival timing is not used as a future scheduler forecast.

- `../ticket-14/jira/notifications-paymentUnreachable.jsonl:1`: `[{"fingerprint":"5e8d72dc87b1ff35","status":"firing","values":{"A":0.11440082443757411,"B":1}}]`
- `../ticket-14/jira/notifications-paymentUnreachable.jsonl:2`: `[{"fingerprint":"5e8d72dc87b1ff35","status":"firing","values":{"A":0.19568987579698632,"B":1}}]`
- `../ticket-14/jira/notifications-paymentUnreachable.jsonl:16`: `[{"fingerprint":"6cd7e206a0716d2d","status":"resolved","values":{"A":0.09999958333506945,"B":0}},{"fingerprint":"5e8d72dc87b1ff35","status":"firing","values":{"A":0.1999991666701389,"B":1}},{"fingerprint":"8e2d9556f6c757b5","status":"resolved","values":{"A":0.09999958333506945,"B":0}}]`
- `../ticket-14/jira/notifications-paymentUnreachable.jsonl:18`: `[{"fingerprint":"5e8d72dc87b1ff35","status":"firing","values":{"A":0.18333409722540508,"B":1}}]`
- `../ticket-14/jira/notifications-paymentUnreachable.jsonl:20`: `[{"fingerprint":"6cd7e206a0716d2d","status":"firing","values":{"A":0.13333111114814752,"B":1}},{"fingerprint":"5e8d72dc87b1ff35","status":"firing","values":{"A":0.26666222229629505,"B":1}},{"fingerprint":"8e2d9556f6c757b5","status":"firing","values":{"A":0.13749770837152714,"B":1}}]`
- `../ticket-14/jira/notifications-paymentUnreachable.jsonl:21`: `[{"fingerprint":"f09facf2b8f5b694","status":"resolved","values":{"A":0.01666638889351844,"B":0}},{"fingerprint":"4396dcd5ddc23476","status":"resolved","values":{"A":0.01666638889351844,"B":0}},{"fingerprint":"4bde20aac01f95a2","status":"resolved","values":{"A":0.02083298611689805,"B":0}},{"fingerprint":"b3587dd72657d226","status":"resolved","values":{"A":0.02499958334027766,"B":0}}]`
- `../ticket-14/jira/notifications-paymentUnreachable.jsonl:23`: `[{"fingerprint":"6cd7e206a0716d2d","status":"resolved","values":{"A":0.08333125005208204,"B":0}},{"fingerprint":"5e8d72dc87b1ff35","status":"firing","values":{"A":0.16666250010416409,"B":1}},{"fingerprint":"8e2d9556f6c757b5","status":"resolved","values":{"A":0.08749781255468614,"B":0}}]`
- `../ticket-14/jira/notifications-paymentUnreachable.jsonl:24`: `[{"fingerprint":"5e8d72dc87b1ff35","status":"firing","values":{"A":0.16666250010416409,"B":1}}]`
- `../ticket-14/jira/notifications-paymentUnreachable.jsonl:26`: `[{"fingerprint":"6cd7e206a0716d2d","status":"resolved","values":{"A":0,"B":0}},{"fingerprint":"5e8d72dc87b1ff35","status":"resolved","values":{"A":0,"B":0}},{"fingerprint":"8e2d9556f6c757b5","status":"resolved","values":{"A":0,"B":0}}]`
- `../ticket-14/jira/notifications-emailMemoryLeak.jsonl:57`: `[{"fingerprint":"391dc40ca1dfd1a3","status":"resolved","values":{"A":55042048,"B":55042048,"C":0}}]`
- `../ticket-14/jira/notifications-emailMemoryLeak.jsonl:62`: `[{"fingerprint":"90ec22b91f46a6ce","status":"resolved","values":{"A":-1,"B":-1}}]`
- `../ticket-14/jira/notifications-emailMemoryLeak.jsonl:63`: `[{"fingerprint":"3253da2ba16cb0cb","status":"resolved","values":{"A":0,"B":0}}]`
- `../ticket-14/jira/notifications-cartFailure.jsonl:1`: `[{"fingerprint":"bddc72414d172719","status":"firing","values":{"A":5,"B":1}}]`
- `../ticket-14/jira/notifications-cartFailure.jsonl:6`: `[{"fingerprint":"5de6002ca2547b11","status":"firing","values":{"A":1,"B":1}}]`
