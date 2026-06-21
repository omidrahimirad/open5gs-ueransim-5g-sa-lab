# Troubleshooting Notes

| Symptom | Likely root cause | How to verify | Fix | Example command |
|---|---|---|---|---|
| gNB never connects to AMF | AMF service name/IP or SCTP issue | Check gNB and AMF logs | Confirm `amfConfigs.address`, Linux SCTP support, port 38412 | `docker compose logs -f gnb amf` |
| AMF rejects UE registration | Subscriber missing | AMF log says unknown SUPI/IMSI | Add subscriber to Open5GS DB | `./scripts/add_subscriber.sh` |
| Authentication fails | K/OPc/AMF mismatch | AMF/UE authentication failure logs | Match `subscriber_config.yaml` and `ue.yaml` | `grep -i auth logs/*sample.txt` |
| UE sees wrong PLMN | MCC/MNC mismatch | Compare UE, gNB, AMF configs | Use `001/01` consistently or change all files | `grep -R "mcc\\|mnc" configs` |
| No PDU session accept | DNN mismatch | SMF logs show DNN reject | Match DNN `internet` in subscriber, SMF, UE | `grep -R "internet" configs` |
| Slice rejected | S-NSSAI mismatch | AMF/SMF logs mention NSSAI/S-NSSAI | Match SST/SD in AMF, SMF, UE, subscriber | `grep -R "sst\\|sd" configs` |
| UE registered but no tunnel | TUN device unavailable or PDU failed | Check `ip link` inside UE | Run on Linux with `/dev/net/tun` and privileged UE | `docker compose exec ue ip link` |
| UE has IP but ping fails | UPF NAT/forwarding route missing | Check UE route, UPF logs, host forwarding | Enable forwarding/NAT for UE subnet if image does not handle it | `docker compose exec ue ip route` |
| MongoDB unhealthy | DB not ready or volume corrupted | Compose health/status | Restart DB or recreate volume after backup | `docker compose ps mongodb` |
| Parser finds missing events | Logs are incomplete or patterns differ | Inspect parsed CSV and raw logs | Collect full logs and extend parser regex if needed | `python3 scripts/parse_attach_logs.py logs/*sample.txt` |
| Docker Desktop behaves inconsistently | macOS/Windows virtualization limits SCTP/TUN | Compare with Ubuntu VM | Use Ubuntu VM or bare-metal Linux host | `uname -a` |
| Port already in use | Local service occupies 7777 or 38412 | Check listening sockets | Stop conflicting process or change compose ports | `sudo ss -ltnp` |

