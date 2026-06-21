# GitHub Publication Guide

## Repository Description

Reproducible 5G SA lab using Open5GS and UERANSIM with Docker Compose, subscriber config, log collection, Python attach/PDU parser, notebook analysis, reports, and an honest Linux runtime evidence workflow.

## Suggested Topics

```text
5g
5g-sa
open5gs
ueransim
telecom
ran
5g-core
docker-compose
networking
linux
python
log-analysis
wireless
telecom-lab
```

## Suggested Pinned-Repo Description

5G Standalone lab portfolio project: Open5GS core, UERANSIM gNB/UE, Docker Compose, subscriber provisioning, traffic checks, log parsing, notebook analysis, and real-run evidence workflow.

## Suggested LinkedIn Post

I built a 5G Standalone lab portfolio project using Open5GS and UERANSIM.

The goal is to show practical understanding across 5G Core, RAN-facing procedures, Linux networking, Docker-based lab setup, and Python log analysis. The repository includes AMF/SMF/UPF/NRF and gNB/UE configuration, subscriber provisioning notes, traffic validation scripts, log collection, attach/PDU session parsing, a Jupyter analysis notebook, architecture diagrams, troubleshooting notes, and a real-run evidence workflow.

I kept the project intentionally honest: current validation covers configuration checks and sample-log parser analysis; full Linux runtime validation will be added only after collecting real evidence from an Ubuntu host.

Relevant for 5G/RAN Engineer, 5G Core/Lab Engineer, Network Integration Engineer, RF & Wireless Test Engineer, and telecom support roles.

Repository: https://github.com/omidrahimirad/open5gs-ueransim-5g-sa-lab

## Suggested CV Bullet

Built a documented 5G Standalone lab portfolio using Open5GS, UERANSIM, Docker Compose, Linux networking, and Python log parsing to demonstrate UE registration, authentication/security flow, PDU session analysis, traffic validation workflow, and evidence-based troubleshooting.

## Suggested Commit Sequence

```text
1. Harden Open5GS and UERANSIM lab networking
2. Improve attach and PDU session log parser
3. Add real-run evidence workflow
4. Strengthen troubleshooting and validation documentation
5. Polish README for public GitHub portfolio
```

## Suggested Branch And Push Commands

If committing directly to `main`:

```bash
git status -sb
git add README.md docker-compose.yml configs scripts docs reports notebooks evidence
git commit -m "Polish 5G SA lab portfolio documentation"
git push origin main
```

If using a review branch:

```bash
git checkout -b polish/github-portfolio
git add README.md docker-compose.yml configs scripts docs reports notebooks evidence
git commit -m "Polish 5G SA lab portfolio documentation"
git push -u origin polish/github-portfolio
```

## Do Not Claim Before Real Linux Validation

Do not claim:

- The lab has fully executed end to end.
- UE registration succeeded on real runtime logs.
- PDU session establishment succeeded on the current host.
- Ping/latency values are measured results.
- Docker Desktop on macOS is validated for SCTP/TUN/user-plane behavior.
- The lab represents commercial RF/RAN latency or scheduler behavior.

Safe wording before real evidence:

- "Configuration and parser validated with sample logs."
- "Linux runtime validation pending."
- "Designed for Ubuntu/Linux execution with SCTP and TUN support."
- "Sample logs are included for parser demonstration only."

