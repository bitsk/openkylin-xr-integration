#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Read-only device inspection. Logs are stored in the maintenance RAM filesystem.
set -eu
case "$0" in */*) . "${0%/*}/common.sh";; *) . ./common.sh;; esac
xr_lock
xr_identity
xr_unmounted
case "${1:-original}" in
    original)
        xr_original_gpt
        [ "$(blockdev --getsize64 /dev/sda15)" -eq "$XR_USERDATA_ORIGINAL_BYTES" ] || xr_die 'Original userdata size mismatch'
        xr_region /dev/sda15 0 2 "$XR_STORAGE_PLAN/original/userdata-superblocks.bin" "$XR_ORIGINAL_SUPERBLOCKS_SHA256"
        xr_region /dev/sda15 "$XR_ORIGINAL_FOOTER_BLOCK" 4 "$XR_STORAGE_PLAN/original/userdata-footer.bin" "$XR_FOOTER_SHA256"
        ;;
    candidate)
        xr_candidate_gpt
        xr_shrunk_superblocks
        [ "$(blockdev --getsize64 /dev/sda15)" -eq "$XR_USERDATA_TARGET_BYTES" ] || xr_die 'Target userdata size mismatch'
        [ "$(blockdev --getsize64 /dev/sda16)" -eq "$XR_OSSTORE_BYTES" ] || xr_die 'osstore size mismatch'
        [ "$(cat /sys/class/block/sda16/start)" -eq "$((XR_OSSTORE_START * 8))" ] || xr_die 'osstore start mismatch'
        ;;
    *) xr_die 'Usage: inspect.sh [original|candidate]';;
esac
echo 'VR700 identity, unmounted UFS, GPT and geometry verified; no device writes'
