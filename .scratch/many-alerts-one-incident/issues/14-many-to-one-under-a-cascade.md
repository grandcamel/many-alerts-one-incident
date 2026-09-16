# Many-to-one under a Cascade

Type: grilling
Status: open
Blocked by: 10, 11

## Question

With one Run per Notification kept: how is Grafana's grouping set so a Cascade tends to arrive together? Does one-at-a-time survive N Notifications when a Run takes minutes, or does the Receiver coalesce, queue with a cap, or drop repeats? What rule does a Run judge a Match by, what does it read to judge, and what happens when it judges wrong: an Alert filed under the wrong Incident, or a second Incident for a Fault that already has one? What may a later Run change in an existing Report? Extends ADR 0006 with the mechanics it left open.
