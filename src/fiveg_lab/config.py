from __future__ import annotations

import ipaddress
import re
from pathlib import Path
from typing import Any, cast

import yaml

from fiveg_lab.models import Check, CheckStatus

HEX_32_RE = re.compile(r"^[0-9a-fA-F]{32}$")
SUPI_RE = re.compile(r"^imsi-\d{15}$")
REQUIRED_NFS = {
    "mongodb",
    "nrf",
    "ausf",
    "udm",
    "udr",
    "amf",
    "smf",
    "upf",
    "gnb",
    "ue",
    "dn-server",
}


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        msg = f"{path} must contain a YAML mapping"
        raise ValueError(msg)
    return cast("dict[str, Any]", data)


def nested(data: Any, *keys: str | int) -> Any:
    value = data
    for key in keys:
        if isinstance(key, int):
            if not isinstance(value, list) or key >= len(value):
                return None
            value = value[key]
            continue
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def service_ip(compose: dict[str, Any], service: str, network: str = "core") -> str | None:
    value = nested(compose, "services", service, "networks", network, "ipv4_address")
    return str(value) if value is not None else None


def list_first(value: Any) -> dict[str, Any]:
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return cast("dict[str, Any]", value[0])
    return {}


def check(name: str, ok: bool, detail: str) -> Check:
    return Check(name=name, status=CheckStatus.PASS if ok else CheckStatus.FAIL, detail=detail)


def warning(name: str, detail: str) -> Check:
    return Check(name=name, status=CheckStatus.WARN, detail=detail)


def validate_repo(repo_root: Path) -> list[Check]:
    compose = load_yaml(repo_root / "docker-compose.yml")
    amf = load_yaml(repo_root / "configs/open5gs/amf.yaml")
    smf = load_yaml(repo_root / "configs/open5gs/smf.yaml")
    upf = load_yaml(repo_root / "configs/open5gs/upf.yaml")
    nrf = load_yaml(repo_root / "configs/open5gs/nrf.yaml")
    gnb = load_yaml(repo_root / "configs/ueransim/gnb.yaml")
    ue = load_yaml(repo_root / "configs/ueransim/ue.yaml")
    subscriber = load_yaml(repo_root / "configs/subscriber_config.yaml")

    checks: list[Check] = []
    services = cast("dict[str, Any]", compose.get("services", {}))
    service_names = set(services)
    checks.append(
        check(
            "required_network_functions",
            service_names >= REQUIRED_NFS,
            f"services={sorted(service_names)}",
        )
    )

    compose_ips = collect_static_ips(services)
    checks.append(
        check(
            "unique_static_container_ips",
            len(compose_ips) == len(set(compose_ips)),
            str(compose_ips),
        )
    )
    checks.extend(validate_ips(compose_ips))

    amf_plmn = list_first(nested(amf, "amf", "guami")).get("plmn_id", {})
    nrf_plmn = list_first(nested(nrf, "nrf", "serving")).get("plmn_id", {})
    subscriber_root = cast("dict[str, Any]", subscriber["subscriber"])
    checks.append(
        check(
            "mcc_consistent",
            str(amf_plmn.get("mcc"))
            == str(gnb.get("mcc"))
            == str(ue.get("mcc"))
            == str(subscriber_root.get("mcc"))
            == str(nrf_plmn.get("mcc")),
            "MCC must match NRF, AMF, gNB, UE, and subscriber",
        )
    )
    checks.append(
        check(
            "mnc_consistent",
            str(amf_plmn.get("mnc"))
            == str(gnb.get("mnc"))
            == str(ue.get("mnc"))
            == str(subscriber_root.get("mnc"))
            == str(nrf_plmn.get("mnc")),
            "MNC must match NRF, AMF, gNB, UE, and subscriber",
        )
    )
    checks.append(
        check(
            "tac_consistent",
            nested(amf, "amf", "tai", 0, "tac") == gnb.get("tac"),
            "AMF TAI TAC must match gNB TAC",
        )
    )

    amf_ngap = str(list_first(nested(amf, "amf", "ngap", "server")).get("address"))
    gnb_amf = str(list_first(gnb.get("amfConfigs")).get("address"))
    checks.append(
        check("amf_ngap_ip_matches_compose", amf_ngap == service_ip(compose, "amf"), amf_ngap)
    )
    checks.append(check("gnb_points_to_amf_ngap", gnb_amf == amf_ngap, gnb_amf))
    checks.append(
        check(
            "gnb_ngap_ip_matches_compose",
            str(gnb.get("ngapIp")) == service_ip(compose, "gnb"),
            str(gnb.get("ngapIp")),
        )
    )
    checks.append(
        check(
            "gnb_gtp_ip_matches_compose",
            str(gnb.get("gtpIp")) == service_ip(compose, "gnb"),
            str(gnb.get("gtpIp")),
        )
    )

    smf_session = list_first(nested(smf, "smf", "session"))
    upf_session = list_first(nested(upf, "upf", "session"))
    subscriber_session = cast("dict[str, Any]", subscriber["session"])
    ue_session = list_first(ue.get("sessions"))
    checks.append(
        check(
            "dnn_consistent",
            str(smf_session.get("dnn"))
            == str(upf_session.get("dnn"))
            == str(subscriber_session.get("dnn"))
            == str(ue_session.get("apn")),
            "DNN/APN must match SMF, UPF, subscriber, and UE",
        )
    )
    checks.append(
        check(
            "ue_ipv4_pool_consistent",
            str(smf_session.get("subnet"))
            == str(upf_session.get("subnet"))
            == str(subscriber_session.get("ue_ipv4_pool")),
            "SMF/UPF/subscriber UE pool must match",
        )
    )
    checks.append(
        check(
            "smf_upf_pfcp_ip_consistent",
            str(list_first(nested(smf, "smf", "pfcp", "client", "upf")).get("address"))
            == service_ip(compose, "upf"),
            "SMF N4 client must target UPF PFCP IP",
        )
    )

    amf_slice = list_first(list_first(nested(amf, "amf", "plmn_support")).get("s_nssai"))
    gnb_slice = list_first(gnb.get("slices"))
    ue_slice = list_first(ue.get("configured-nssai"))
    subscriber_slice = cast("dict[str, Any]", subscriber["slice"])
    checks.append(
        check(
            "sst_consistent",
            amf_slice.get("sst")
            == gnb_slice.get("sst")
            == ue_slice.get("sst")
            == subscriber_slice.get("sst"),
            "SST must match AMF, gNB, UE, and subscriber",
        )
    )
    checks.append(
        check(
            "sd_consistent",
            str(amf_slice.get("sd"))
            == str(gnb_slice.get("sd"))
            == str(ue_slice.get("sd"))
            == str(subscriber_slice.get("sd")),
            "SD must match AMF, gNB, UE, and subscriber",
        )
    )

    checks.append(
        check("supi_format", bool(SUPI_RE.match(str(ue.get("supi")))), str(ue.get("supi")))
    )
    checks.append(
        check(
            "supi_matches_subscriber",
            str(ue.get("supi")) == str(subscriber_root.get("supi")),
            "UE SUPI must match subscriber",
        )
    )
    checks.append(
        check(
            "subscriber_key_format",
            bool(HEX_32_RE.match(str(subscriber_root.get("key")))),
            "subscriber K must be 16-byte hex",
        )
    )
    checks.append(
        check(
            "ue_key_matches_subscriber",
            str(ue.get("key")) == str(subscriber_root.get("key")),
            "UE K must match subscriber",
        )
    )
    checks.append(
        check(
            "ue_opc_matches_subscriber",
            str(ue.get("op")) == str(subscriber_root.get("opc")),
            "UE OPc must match subscriber",
        )
    )
    checks.append(
        check(
            "ue_amf_matches_subscriber",
            str(ue.get("amf")) == str(subscriber_root.get("amf")),
            "UE AMF auth field must match subscriber",
        )
    )

    checks.extend(validate_image_defaults(compose))
    return checks


def collect_static_ips(services: dict[str, Any]) -> list[str]:
    ips: list[str] = []
    for service in services.values():
        if not isinstance(service, dict):
            continue
        networks = service.get("networks", {})
        if not isinstance(networks, dict):
            continue
        for network_cfg in networks.values():
            if isinstance(network_cfg, dict) and "ipv4_address" in network_cfg:
                ips.append(str(network_cfg["ipv4_address"]))
    return ips


def validate_ips(values: list[str]) -> list[Check]:
    checks: list[Check] = []
    for value in values:
        try:
            ipaddress.ip_address(value)
        except ValueError:
            checks.append(Check("valid_ip_addresses", CheckStatus.FAIL, f"invalid={value}"))
    if not checks:
        checks.append(
            Check("valid_ip_addresses", CheckStatus.PASS, "all static IP addresses parse")
        )
    return checks


def validate_image_defaults(compose: dict[str, Any]) -> list[Check]:
    image_values = [
        str(value)
        for value in (
            compose.get("x-open5gs-image"),
            compose.get("x-ueransim-image"),
            nested(compose, "services", "mongodb", "image"),
            nested(compose, "services", "open5gs-dbctl", "image"),
            nested(compose, "services", "dn-server", "image"),
        )
    ]
    floating = [value for value in image_values if value.endswith(":latest") or value == "latest"]
    checks = [check("critical_images_not_latest", not floating, f"floating={floating}")]
    if "${" in " ".join(image_values):
        checks.append(
            warning(
                "image_overrides_supported",
                "Images can be overridden by environment variables; defaults remain pinned.",
            )
        )
    return checks


def checks_pass(checks: list[Check]) -> bool:
    return all(item.status != CheckStatus.FAIL for item in checks)
