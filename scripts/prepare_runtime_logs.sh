#!/bin/sh
set -eu

# This path is a Docker named volume, never the checkout or its sample logs.
log_dir=/var/log/open5gs
[ -d "$log_dir" ] && [ ! -L "$log_dir" ]
chown 999:999 "$log_dir"
chmod 0775 "$log_dir"
for nf in nrf ausf udm udr pcf amf smf upf; do
    log_file="$log_dir/$nf.log"
    if [ -L "$log_file" ]; then
        echo "Refusing symlink: $log_file" >&2
        exit 1
    fi
    if [ ! -e "$log_file" ]; then
        (umask 022; : > "$log_file")
    fi
    [ -f "$log_file" ]
    chown 999:999 "$log_file"
    chmod 0644 "$log_file"
done
echo LOG_DIRECTORY_READY
