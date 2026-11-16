#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
set -eu
[ "${1:-}" = --format-osstore ] || { echo 'Usage: format-osstore.sh --format-osstore' >&2; exit 1; }
case "$0" in */*) . "${0%/*}/common.sh";; *) . ./common.sh;; esac
xr_lock
xr_require_marker gpt-verified
[ ! -e "$XR_STORAGE_WORK/format-started" ] || xr_die 'Format already attempted; inspect before recovery'
xr_identity
xr_unmounted
xr_candidate_gpt
xr_shrunk_superblocks
[ "$(blockdev --getsize64 /dev/sda15)" -eq "$XR_USERDATA_TARGET_BYTES" ] || xr_die 'Target userdata size mismatch'
[ "$(blockdev --getsize64 /dev/sda16)" -eq "$XR_OSSTORE_BYTES" ] || xr_die 'Target osstore size mismatch'
[ "$(cat /sys/class/block/sda16/start)" -eq "$((XR_OSSTORE_START * 8))" ] || xr_die 'Target osstore start mismatch'
# Refuse an already initialized filesystem, including this plan's prior result.
if blkid /dev/sda16 >"$XR_STORAGE_WORK/osstore-existing.txt" 2>/dev/null; then
    [ ! -s "$XR_STORAGE_WORK/osstore-existing.txt" ] || xr_die 'osstore already has a recognizable filesystem'
fi
xr_marker format-started
mke2fs -t ext4 -b 4096 -i 16384 -I 256 -m 0 -L osstore -U "$XR_OSSTORE_UUID" \
    -O has_journal,extent,huge_file,flex_bg,metadata_csum,64bit,dir_nlink,extra_isize \
    -E lazy_itable_init=1,lazy_journal_init=1,nodiscard /dev/sda16 </dev/null >"$XR_STORAGE_WORK/mke2fs.log" 2>&1 || xr_die 'osstore format failed'
sync
e2fsck -fn /dev/sda16 </dev/null >"$XR_STORAGE_WORK/e2fsck.log" 2>&1 || xr_die 'New osstore fsck failed'
blkid /dev/sda16 | grep -Fq "UUID=\"$XR_OSSTORE_UUID\"" || xr_die 'New filesystem UUID mismatch'
xr_candidate_gpt
xr_marker format-verified
echo 'VR700 osstore ext4 created and checked; Android return and rootfs installation remain separate gates'
