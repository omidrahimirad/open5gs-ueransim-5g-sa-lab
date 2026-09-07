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

## Open5GS 2.8.0 PCF/NSSF Mode

PCF is required for this lab. In the tagged Open5GS 2.8.0 source, the AMF registration path creates an `Npcf_AMPolicyControl` association after UDM subscription-data handling, and the SMF session path creates an `Npcf_SMPolicyControl` association. The Compose topology therefore runs `open5gs-pcfd` with MongoDB and NRF connectivity.

NSSF is intentionally not required for this one-SMF topology. Open5GS 2.8.0 AMF first searches NRF-discovered SMF instances using S-NSSAI, DNN, and TAI; it calls NSSF only when that direct SMF selection does not find a match. The lab's `smf.info` advertises SST `1`, SD `000001`, and DNN `internet`, and static validation binds that advertisement to AMF/session configuration.

Version-specific primary sources:

- [Open5GS 2.8.0 AMF UDM/PCF path](https://github.com/open5gs/open5gs/blob/v2.8.0/src/amf/nudm-handler.c)
- [Open5GS 2.8.0 AMF SMF/NSSF selection path](https://github.com/open5gs/open5gs/blob/v2.8.0/src/amf/gmm-handler.c)
- [Open5GS 2.8.0 SMF UDM/PCF path](https://github.com/open5gs/open5gs/blob/v2.8.0/src/smf/nudm-handler.c)
- [Open5GS 2.8.0 SMF configuration template](https://github.com/open5gs/open5gs/blob/v2.8.0/configs/open5gs/smf.yaml.in)
