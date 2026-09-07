# Runtime Version Selection

Validated on: 2026-09-07 from Docker Hub/GitHub metadata lookup.

| Component | Image/source | Selected default | Notes |
| --- | --- | --- | --- |
| Open5GS | `gradiant/open5gs` | `2.8.0` | Community container image aligned with Open5GS `v2.8.0`; not an official upstream Open5GS image. |
| UERANSIM | `gradiant/ueransim` | `3.3.0` | Community container image aligned with UERANSIM `v3.3.0`. |
| MongoDB | `mongo` | `8.3.8-noble` | Official MongoDB image tag used for subscriber database storage. |
| dbctl | `gradiant/open5gs-dbctl` | `0.10.3` | Community helper image for deterministic subscriber provisioning. |
| DN target | `busybox` | `1.37.0` | Minimal internal data-network target for interface-bound ping validation. |

The defaults are pinned tags, not digests. Environment overrides remain supported for controlled experiments, but any runtime evidence must record the actual image values used.

Critical note: Gradiant images are useful community packaging for lab work. This repository must not imply that they are official Open5GS or UERANSIM upstream container images.
