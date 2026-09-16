# When a Run is refused or never runs

Type: grilling
Status: open
Blocked by: none

## Question

The timing prototype found three ways a Run fails that the demo currently cannot tell
apart from success, and none of them is the Run reasoning badly.

- **Hands refuses.** A `jira-as` command over roughly 9,400 characters is denied by the
  allow list on length alone, with the ordinary don't-ask message and no reason
  ("Does a high-effort Run fit the slot"). All three arms that hit it handled it badly:
  one shortened and retried twice, one **created a junk Incident to test the boundary**
  before filing the real one, and one spent its whole remaining slot probing and filed
  nothing. What does the Skill tell a Run to do the first time Hands refuses? A Run must
  never write a probe into a live OPS project, and it must prefer a short filed Report
  over a long denied one.
- **The Run never ran.** A rate-limited Run's result line says `"subtype": "success"`
  with zero cost and one turn; only `terminal_reason: "api_error"` and a
  `rate_limit_event` carrying `"status": "rejected"` are honest. What does the Receiver
  read to decide a Run worked, and what does the audience see when it did not?
- **The Run was killed.** A Run killed on the Receiver's timeout writes no result line,
  so its cost and usage are lost, and chapter one's `RUN_TIMEOUT` is 300 s against an
  Opus 5 Run measured at 370 s. Is the guard SIGINT, which yields a result line, rather
  than the current SIGKILL? What is the timeout now that a Cascade has been timed?

Produces an ADR or extends ADR 0003, and hands the Skill a "what to do when refused"
section. This is the decision the prototype's worst outcome argues for: a Run that
investigates perfectly and produces nothing is worse on a stage than a thin Report.
