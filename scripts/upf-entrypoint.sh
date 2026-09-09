#!/bin/sh
set -eu

# Replace the pinned image's /proc/sys writes with verification of Docker's
# namespaced sysctls. NET_ADMIN still performs every data-plane setup operation.
: "${IPV4_TUN_ADDR:?required}" "${IPV4_TUN_SUBNET:?required}" "${IPV6_TUN_ADDR:?required}"
case "${ENABLE_NAT:?required}" in true|false) ;; *) echo 'Invalid ENABLE_NAT' >&2; exit 1 ;; esac
check_only=false
if [ "${1:-}" = --check ]; then check_only=true; fi
if [ "$#" -eq 0 ]; then echo 'UPF command or --check required' >&2; exit 1; fi
created_tun=false
created_nat=false
cleanup() {
    failed=0
    if [ "$created_nat" = true ]; then
        iptables -t nat -D POSTROUTING -s "$IPV4_TUN_SUBNET" ! -o ogstun -j MASQUERADE || failed=1
    fi
    if [ "$created_tun" = true ]; then
        ip link del ogstun || failed=1
    fi
    if [ "$failed" = 1 ]; then echo UPF_BOOTSTRAP_CLEANUP_FAILED >&2; return 1; fi
    created_nat=false
    created_tun=false
}
trap 'cleanup || exit 1' EXIT
trap 'exit 1' INT TERM

require_sysctl() {
    actual=$(sysctl -n "$1")
    if [ "$actual" != "$2" ]; then
        echo "Required Compose sysctl $1=$2; observed $actual" >&2
        exit 1
    fi
}
require_sysctl net.ipv4.ip_forward 1
require_sysctl net.ipv6.conf.all.disable_ipv6 0
require_sysctl net.ipv6.conf.default.disable_ipv6 0

if ip link show ogstun >/dev/null 2>&1; then
    if [ "$check_only" = true ]; then
        echo 'Refusing to probe an existing ogstun; use an isolated container' >&2
        exit 1
    fi
else
    created_tun=true
    ip tuntap add name ogstun mode tun
fi
require_sysctl net.ipv6.conf.ogstun.disable_ipv6 0
ip -4 addr replace "$IPV4_TUN_ADDR" dev ogstun
ip -6 addr replace "$IPV6_TUN_ADDR" dev ogstun
ip link set ogstun up
addr4=$(ip -o -4 addr show dev ogstun)
addr6=$(ip -o -6 addr show dev ogstun)
link=$(ip -o link show dev ogstun)
printf '%s\n' "$addr4" | grep -F "inet $IPV4_TUN_ADDR "
printf '%s\n' "$addr6" | grep -F "inet6 $IPV6_TUN_ADDR "
printf '%s\n' "$link" | grep -E '<([^>]*,)?UP(,|>)'

if [ "$ENABLE_NAT" = true ]; then
    if ! iptables -t nat -C POSTROUTING -s "$IPV4_TUN_SUBNET" ! -o ogstun -j MASQUERADE 2>/dev/null; then
        created_nat=true
        iptables -t nat -A POSTROUTING -s "$IPV4_TUN_SUBNET" ! -o ogstun -j MASQUERADE
    fi
    iptables -t nat -C POSTROUTING -s "$IPV4_TUN_SUBNET" ! -o ogstun -j MASQUERADE
fi

if [ "$check_only" = true ]; then
    cleanup
    if ip link show ogstun >/dev/null 2>&1; then
        echo 'ogstun remained after probe cleanup' >&2
        exit 1
    fi
    trap - EXIT
    echo UPF_BOOTSTRAP_PASS
    exit 0
fi

# Retain the image's startup delay, then make the NF the container's main process.
sleep 10
trap - EXIT
exec "$@"
