# 19c source review

Status: independent Standards and Spec reviews PASS, 2026-09-25.
Fixed point for reviewed source: unit 19c policy, tests and docs before commit.

Standards review found no actionable defect in scalar validation, immutable
result, boundary tests or no-authority wording. It noted an editorial plan
phrase describing one input object; the plan now says bounded scalar inputs.
Spec review found no actionable defect against ADR 0012/ticket 37: same-boot
monotonic observations, exact 270/20/10 boundaries, shortened early-stop
windows and a hard 300-second cap are represented without claiming process
containment or dispatch authority.

The review does not validate OS signaling, stream draining, native process
behavior, Forwarder lease revocation, journal evidence or intended venue
containment. Those remain separate work.
