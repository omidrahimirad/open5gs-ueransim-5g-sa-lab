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
    "pcf",
    "amf",
    "smf",
    "upf",
    "gnb",
    "ue",
    "dn-server",
}
OPEN5GS_NFS = ("nrf", "ausf", "udm", "udr", "pcf", "amf", "smf", "upf")
LOG_VOLUME = "open5gs-logs"
LOG_TARGET = "/var/log/open5gs"
UPF_ENTRYPOINT = ["/bin/sh", "/lab/upf-entrypoint.sh"]
LOG_INIT_ENTRYPOINT = ["/bin/sh", "/lab/prepare-runtime-logs.sh"]
LAB_DB_URI = "mongodb://mongodb/open5gs"
GPRS_TIMER_3_MAX_VALUE = 31


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
    pcf = load_yaml(repo_root / "configs/open5gs/pcf.yaml")
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
    checks.extend(
        validate_open5gs_2_8_policy_and_slice_selection(compose, amf, smf, pcf)
        + validate_open5gs_startup_contract(
            compose, amf, pcf, load_yaml(repo_root / "configs/open5gs/udr.yaml")
        )
        + validate_ueransim_ue_startup_contract(ue)
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
    checks.extend(
        validate_container_runtime_contract(compose) + validate_upf_address_alignment(compose, upf)
    )
    return checks


def compose_environment(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return cast("dict[str, Any]", value)
    if isinstance(value, list):
        return {
            item.partition("=")[0]: item.partition("=")[2]
            for item in value
            if isinstance(item, str) and "=" in item
        }
    return {}


def exposes_tun_device(devices: Any) -> bool:
    if not isinstance(devices, list):
        return False
    for device in devices:
        if isinstance(device, str):
            parts = device.split(":")
            if len(parts) not in {2, 3}:
                continue
            source, target, *permission_fields = parts
            permissions = permission_fields[0] if permission_fields else "rwm"
        elif isinstance(device, dict):
            source = str(device.get("source", ""))
            target = str(device.get("target", ""))
            permissions = str(device.get("permissions", "rwm"))
        else:
            continue
        if source == target == "/dev/net/tun" and {"r", "w"} <= set(permissions):
            return True
    return False


def validate_container_runtime_contract(compose: dict[str, Any]) -> list[Check]:
    """Protect declared bootstrap settings; this does not prove runtime capability."""
    mongo_env = compose_environment(nested(compose, "services", "mongodb", "environment"))
    upf = nested(compose, "services", "upf")
    if not isinstance(upf, dict):
        upf = {}
    capabilities = upf.get("cap_add", [])
    return (
        [
            check(
                "mongodb_kernel_rseq_compatibility",
                mongo_env.get("GLIBC_TUNABLES") == "glibc.pthread.rseq=1",
                "MongoDB must explicitly set GLIBC_TUNABLES=glibc.pthread.rseq=1 for the "
                "Linux kernel compatibility workaround validated on the external VM",
            ),
            check(
                "upf_explicit_root_user",
                upf.get("user") == "0:0",
                "UPF must use user 0:0; the image default uid 999 lacked effective "
                "TUN capabilities",
            ),
            check(
                "upf_net_admin_capability",
                isinstance(capabilities, list) and "NET_ADMIN" in capabilities,
                "UPF must add NET_ADMIN to create ogstun; verify effective capability with "
                "runtime-preflight on Linux",
            ),
            check(
                "upf_tun_device",
                exposes_tun_device(upf.get("devices")),
                "UPF must expose /dev/net/tun at /dev/net/tun with read/write access",
            ),
            check(
                "upf_without_privileged",
                "privileged" not in upf or upf["privileged"] is False,
                "UPF must omit privileged or set it false; root + NET_ADMIN + TUN passed the "
                "isolated external VM TUN test",
            ),
        ]
        + validate_logging_contract(compose)
        + validate_upf_bootstrap_contract(upf)
    )


def mount_at(service: Any, target: str) -> dict[str, Any]:
    volumes = nested(service, "volumes")
    if not isinstance(volumes, list):
        return {}
    for item in volumes:
        mount = item
        if isinstance(mount, str):
            parts = mount.split(":")
            if len(parts) not in {2, 3}:
                continue
            source, destination = parts[:2]
            mount = {
                "source": source,
                "target": destination,
                "type": "bind" if source.startswith((".", "/", "~")) else "volume",
                "read_only": bool(parts[2:]) and "ro" in parts[2].split(","),
            }
        if isinstance(mount, dict) and mount.get("target") == target:
            return cast("dict[str, Any]", mount)
    return {}


def readonly_script(service: Any, target: str, filename: str) -> bool:
    mount = mount_at(service, target)
    return (
        mount.get("type") == "bind"
        and mount.get("read_only") is True
        and str(mount.get("source", "")).endswith("/scripts/" + filename)
    )


def validate_logging_contract(compose: dict[str, Any]) -> list[Check]:
    volume = nested(compose, "volumes", LOG_VOLUME)
    volume = {} if volume is None else volume
    volume_ok = isinstance(volume, dict) and set(volume) <= {"name"}
    if isinstance(volume, dict) and "name" in volume:
        volume_ok = volume_ok and volume["name"] == f"{compose.get('name')}_{LOG_VOLUME}"
    init = nested(compose, "services", "log-init") or {}
    checks = [
        check(
            "runtime_log_initializer",
            LOG_VOLUME in (compose.get("volumes") or {})
            and volume_ok
            and init.get("user") == "0:0"
            and init.get("network_mode") == "none"
            and init.get("read_only") is True
            and not init.get("privileged", False)
            and init.get("cap_drop") == ["ALL"]
            and set(init.get("cap_add", [])) == {"CHOWN", "FOWNER", "DAC_OVERRIDE"}
            and init.get("entrypoint") == LOG_INIT_ENTRYPOINT
            and readonly_script(init, LOG_INIT_ENTRYPOINT[1], "prepare_runtime_logs.sh"),
            "Prepare only the Docker-managed runtime log volume with the scoped root initializer.",
        )
    ]
    for name in ("log-init", *OPEN5GS_NFS):
        service = nested(compose, "services", name) or {}
        mount = mount_at(service, LOG_TARGET)
        ok = mount.get("type") == "volume" and mount.get("source") == LOG_VOLUME
        ok = ok and not mount.get("read_only", False)
        if name != "log-init":
            ok = (
                ok
                and nested(service, "depends_on", "log-init", "condition")
                == "service_completed_successfully"
            )
        if name not in {"log-init", "upf"}:
            ok = ok and service.get("user") == "999:999"
        checks.append(
            check(
                f"{name}_runtime_logs",
                ok,
                "Use initialized named logs; non-UPF NFs remain UID/GID 999.",
            )
        )
    return checks


def validate_upf_bootstrap_contract(upf: dict[str, Any]) -> list[Check]:
    sysctls = upf.get("sysctls", {})
    environment = compose_environment(upf.get("environment"))
    return [
        check(
            "upf_bootstrap_entrypoint",
            upf.get("entrypoint") == UPF_ENTRYPOINT
            and readonly_script(upf, UPF_ENTRYPOINT[1], "upf-entrypoint.sh"),
            "Use the mounted UPF bootstrap that verifies Docker sysctls instead of writing them.",
        ),
        check(
            "upf_bootstrap_sysctls",
            isinstance(sysctls, dict)
            and all(
                str(sysctls.get(key)) == value
                for key, value in {
                    "net.ipv4.ip_forward": "1",
                    "net.ipv6.conf.all.disable_ipv6": "0",
                    "net.ipv6.conf.default.disable_ipv6": "0",
                }.items()
            ),
            "Compose must configure IPv4 forwarding and enable IPv6 before UPF bootstrap.",
        ),
        check(
            "upf_bootstrap_environment",
            all(
                environment.get(key)
                for key in ("IPV4_TUN_ADDR", "IPV4_TUN_SUBNET", "IPV6_TUN_ADDR")
            )
            and environment.get("ENABLE_NAT") in {"true", "false"},
            "Explicitly configure tunnel addresses, UE subnet, and NAT behavior.",
        ),
    ]


def validate_upf_address_alignment(
    compose: dict[str, Any], upf_config: dict[str, Any]
) -> list[Check]:
    environment = compose_environment(nested(compose, "services", "upf", "environment"))
    session = list_first(nested(upf_config, "upf", "session"))
    try:
        subnet = ipaddress.IPv4Network(str(session.get("subnet")))
        address = ipaddress.IPv4Interface(str(environment.get("IPV4_TUN_ADDR")))
        ipaddress.IPv6Interface(str(environment.get("IPV6_TUN_ADDR")))
        valid = address.network == subnet and str(address.ip) == str(session.get("gateway"))
        valid = valid and str(environment.get("IPV4_TUN_SUBNET")) == str(subnet)
    except ValueError:
        valid = False
    return [
        check(
            "upf_tunnel_address_alignment",
            valid,
            "UPF bootstrap IPv4 address/NAT subnet must match the configured UE gateway/pool; "
            "IPv6 must be valid.",
        )
    ]


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


def validate_open5gs_2_8_policy_and_slice_selection(
    compose: dict[str, Any],
    amf: dict[str, Any],
    smf: dict[str, Any],
    pcf: dict[str, Any],
) -> list[Check]:
    services = cast("dict[str, Any]", compose.get("services", {}))
    pcf_ip = service_ip(compose, "pcf")
    pcf_sbi_ip = str(list_first(nested(pcf, "pcf", "sbi", "server")).get("address"))
    pcf_db_uri = str(pcf.get("db_uri"))

    amf_slice = list_first(list_first(nested(amf, "amf", "plmn_support")).get("s_nssai"))
    smf_info = list_first(nested(smf, "smf", "info"))
    smf_slice = list_first(smf_info.get("s_nssai"))
    smf_dnns = smf_slice.get("dnn", [])
    session_dnn = list_first(nested(smf, "smf", "session")).get("dnn")
    nssf_omitted = "nssf" not in services
    smf_advertises_selected_slice = (
        smf_slice.get("sst") == amf_slice.get("sst")
        and str(smf_slice.get("sd")) == str(amf_slice.get("sd"))
        and isinstance(smf_dnns, list)
        and session_dnn in smf_dnns
    )

    return [
        check(
            "open5gs_2_8_pcf_required_mode",
            "pcf" in services and pcf_sbi_ip == pcf_ip and pcf_db_uri == LAB_DB_URI,
            "Open5GS 2.8.0 PCF must be present, use the Compose SBI IP, and use lab MongoDB",
        ),
        check(
            "open5gs_2_8_nssf_bypass_mode",
            nssf_omitted and smf_advertises_selected_slice,
            "NSSF is intentionally omitted only while SMF advertises the matching "
            "S-NSSAI/DNN to NRF",
        ),
    ]


def validate_open5gs_startup_contract(
    compose: dict[str, Any],
    amf: dict[str, Any],
    pcf: dict[str, Any],
    udr: dict[str, Any],
) -> list[Check]:
    """Validate pinned 2.8.0 startup inputs; runtime readiness is a separate check."""
    timer = nested(amf, "amf", "time", "t3512", "value")
    # v2.8.0 lib/nas/common/conv.c encodes GPRS Timer 3 in these units,
    # with a five-bit value. AMF additionally rejects an absent/zero timer.
    timer_units = (2, 30, 60, 600, 3600, 36000, 1152000)
    timer_ok = (
        isinstance(timer, int)
        and not isinstance(timer, bool)
        and any(
            timer % unit == 0 and 1 <= timer // unit <= GPRS_TIMER_3_MAX_VALUE
            for unit in timer_units
        )
    )
    checks = [
        check(
            "open5gs_2_8_amf_t3512",
            timer_ok,
            "AMF requires a positive integer amf.time.t3512.value in seconds that "
            "Open5GS 2.8.0 can encode as GPRS Timer 3 (upstream default: 540).",
        )
    ]
    for name, config in (("pcf", pcf), ("udr", udr)):
        environment = compose_environment(nested(compose, "services", name, "environment"))
        checks.extend(
            [
                check(
                    f"open5gs_2_8_{name}_db_uri",
                    config.get("db_uri") == LAB_DB_URI
                    and "db_uri" not in (nested(config, name) or {}),
                    f"{name.upper()} requires root-level db_uri={LAB_DB_URI}; "
                    f"{name}.db_uri is not a supported key.",
                ),
                check(
                    f"open5gs_2_8_{name}_db_environment",
                    environment.get("DB_URI") == LAB_DB_URI,
                    f"Compose {name}.environment.DB_URI must explicitly target lab MongoDB; "
                    "Open5GS gives DB_URI precedence over YAML and the pinned image "
                    "inherits mongodb://mongo/open5gs.",
                ),
            ]
        )
    return checks


def validate_ueransim_ue_startup_contract(ue: dict[str, Any]) -> list[Check]:
    """Check the v3.3.0 parser fields exposed by the Linux startup failure."""
    public_key = ue.get("homeNetworkPublicKey")
    public_key_ok = "homeNetworkPublicKey" not in ue or (
        isinstance(public_key, str) and re.fullmatch(r"[0-9a-fA-F]{64}", public_key) is not None
    )
    return [
        check(
            "ueransim_3_3_home_network_public_key",
            public_key_ok,
            "UERANSIM 3.3.0 requires exactly 64 hexadecimal homeNetworkPublicKey "
            "characters when present, including with protectionScheme=0.",
        ),
        check(
            "ueransim_3_3_integrity_max_rate",
            all(
                nested(ue, "integrityMaxRate", direction) in ("full", "64kbps")
                for direction in ("uplink", "downlink")
            ),
            "UERANSIM 3.3.0 requires integrityMaxRate.uplink and .downlink; "
            "each must be full or 64kbps.",
        ),
    ]


def checks_pass(checks: list[Check]) -> bool:
    return all(item.status != CheckStatus.FAIL for item in checks)
