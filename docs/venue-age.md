# Local venue age arithmetic

`venue_age.derive_claimed_age` applies ticket 42's conservative lower/upper
formula to bounded caller-supplied nanosecond claims. It computes fresh raw
bounds before comparing them with a persisted anchor. On one boot it advances
both prior bounds by elapsed monotonic time; after a boot change it carries
the prior bounds without subtracting clocks from different boots. A rollback,
lost same-boot anchor, changed resource digest, malformed timestamp or
overflow raises a fixed error.

The result is an arithmetic `AgeAnchor`, not an authenticated venue age or
permission to start a session, Fault or Run. This module cannot establish
that provider time came from the creation account/resource, that it was
generated during the measured request, or that the observation covers a
restart gap. A future trusted adapter and durable off-cluster state must
establish those facts before the `<85` Run gate or other ticket 42 admission
rules can use the bounds. No cloud resource is created or inspected here.
