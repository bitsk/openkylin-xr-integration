#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Explicit filesystem operation; never changes GPT or formats a filesystem.
set -eu
[ "${1:-}" = --execute-shrink ] || { echo 'Usage: shrink.sh --execute-shrink' >&2; exit 1; }
case "$0" in */*) . "${0%/*}/common.sh";; *) . ./common.sh;; esac
xr_lock
[ ! -e "$XR_STORAGE_WORK/shrink-started" ] || xr_die 'Shrink was already attempted; inspect retained logs before recovery'
xr_identity
xr_unmounted
xr_original_gpt
[ "$(blockdev --getsize64 /dev/sda15)" -eq "$XR_USERDATA_ORIGINAL_BYTES" ] || xr_die 'Original userdata size mismatch'
xr_region /dev/sda15 0 2 "$XR_STORAGE_PLAN/original/userdata-superblocks.bin" "$XR_ORIGINAL_SUPERBLOCKS_SHA256"
xr_region /dev/sda15 "$XR_ORIGINAL_FOOTER_BLOCK" 4 "$XR_STORAGE_PLAN/original/userdata-footer.bin" "$XR_FOOTER_SHA256"
# The inspected footer is all zero. Check this before allowing it to be relocated.
dd if=/dev/zero of="$XR_STORAGE_WORK/zero-footer.bin" bs=4096 count=4 2>/dev/null
cmp -s "$XR_STORAGE_WORK/zero-footer.bin" "$XR_STORAGE_PLAN/original/userdata-footer.bin" || xr_die 'Unexpected nonzero footer; requires separate analysis'
xr_hash_file /bin/resize.f2fs "$XR_RESIZE_SHA256"
xr_fsck before
# Check the current offline allocation count against the reviewed target's
# usable-block bound before invoking resize (which can write before checking).
xr_valid_hex=$(grep '^\[FSCK\] valid_block_count ' "$XR_STORAGE_WORK/before.counts" | sed -n 's/.*\[0x\([0-9a-fA-F]*\)\].*/\1/p')
case "$xr_valid_hex" in ''|*[!0-9a-fA-F]*) xr_die 'Cannot read offline valid-block count';; esac
[ "$((0x$xr_valid_hex))" -le "$XR_TARGET_USER_BLOCKS" ] || xr_die 'Offline allocation exceeds reviewed target capacity'
# Recheck immediately before invoking the mutating tool; even its failed
# capacity check can follow NAT/SIT journal writes. Never use lowercase -f.
xr_identity
xr_unmounted
xr_original_gpt
xr_marker shrink-started
/bin/resize.f2fs -F -s -d 1 -t "$XR_FS_TARGET_BLOCKS" /dev/sda15 </dev/null >"$XR_STORAGE_WORK/resize.log" 2>&1 || xr_die 'Resize failed; preserve logs and do not change GPT'
sync
xr_shrunk_superblocks
xr_fsck after
cmp -s "$XR_STORAGE_WORK/before.tree" "$XR_STORAGE_WORK/after.tree" || xr_die 'Filesystem tree changed'
cmp -s "$XR_STORAGE_WORK/before.counts" "$XR_STORAGE_WORK/after.counts" || xr_die 'Allocation counts changed'
# Only after segment bounds and fsck pass may the original footer be copied
# into the reserved end of the future (still unchanged) userdata partition.
[ "$XR_FS_TARGET_BLOCKS" -le "$XR_TARGET_FOOTER_BLOCK" ] || xr_die 'Footer overlaps filesystem'
xr_unmounted
xr_original_gpt
dd if="$XR_STORAGE_PLAN/original/userdata-footer.bin" of=/dev/sda15 bs=4096 seek="$XR_TARGET_FOOTER_BLOCK" count=4 conv=notrunc,fsync || xr_die 'Footer write failed'
xr_region /dev/sda15 "$XR_TARGET_FOOTER_BLOCK" 4 "$XR_STORAGE_PLAN/original/userdata-footer.bin" "$XR_FOOTER_SHA256"
xr_marker shrink-verified
echo 'VR700 F2FS shrink and original tree/counts verified; GPT remains original'
