# Upgrade Docker Desktop

Type: task
Status: open
Blocked by: none

## Question

Docker Desktop on this laptop is 4.0.0 from 2021, on Engine 20.10.8 and HyperKit (see "Where a real Kubernetes could run"). The kind provisioner appears by 4.43.0 and became the default at 4.65.0; the Kubernetes view in the Dashboard is 4.51 and later; the current release is 4.91.0. Upgrade it, then read two facts off the Resources pane that the docs do not give: the highest memory the slider allows on this 16 GB machine, and whether the built-in Kubernetes offers the kind provisioner. Human in the loop: installing an application and changing its resource settings is the user's to do. The answer records the version installed, the memory ceiling, the allocation set, and the Kubernetes options shown.
