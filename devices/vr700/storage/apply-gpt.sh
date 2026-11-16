#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
set -eu
[ "${1:-}" = --apply-gpt ] || { echo 'Usage: apply-gpt.sh --apply-gpt' >&2; exit 1; }
case "$0" in */*) . "${0%/*}/common.sh";; *) . ./common.sh;; esac
xr_lock
xr_require_marker shrink-verified
xr_identity
xr_unmounted
xr_shrunk_superblocks
xr_region /dev/sda15 "$XR_TARGET_FOOTER_BLOCK" 4 "$XR_STORAGE_PLAN/original/userdata-footer.bin" "$XR_FOOTER_SHA256"
xr_hash_file "$XR_STORAGE_PLAN/candidate/gpt-header.bin" "$XR_CANDIDATE_HEADER_SHA256"
xr_hash_file "$XR_STORAGE_PLAN/candidate/gpt-entries.bin" "$XR_CANDIDATE_ENTRIES_SHA256"
xr_hash_file "$XR_STORAGE_PLAN/candidate/gpt-backup-header.bin" "$XR_CANDIDATE_BACKUP_HEADER_SHA256"
xr_hash_file "$XR_STORAGE_PLAN/candidate/gpt-backup-entries.bin" "$XR_CANDIDATE_ENTRIES_SHA256"
# Last check before any GPT write: all original bytes, including padding.
xr_original_gpt
# Backup entries/header first; primary entries/header second. LBA0 is untouched.
dd if="$XR_STORAGE_PLAN/candidate/gpt-backup-entries.bin" of=/dev/sda bs=4096 seek="$XR_BACKUP_ENTRIES_LBA" count=1 conv=notrunc,fsync || xr_die 'Backup entries write failed'
dd if="$XR_STORAGE_PLAN/candidate/gpt-backup-header.bin" of=/dev/sda bs=4096 seek="$XR_BACKUP_HEADER_LBA" count=1 conv=notrunc,fsync || xr_die 'Backup header write failed'
dd if="$XR_STORAGE_PLAN/candidate/gpt-entries.bin" of=/dev/sda bs=4096 seek=2 count=1 conv=notrunc,fsync || xr_die 'Primary entries write failed'
dd if="$XR_STORAGE_PLAN/candidate/gpt-header.bin" of=/dev/sda bs=4096 seek=1 count=1 conv=notrunc,fsync || xr_die 'Primary header write failed'
xr_candidate_gpt
blockdev --rereadpt /dev/sda || xr_die 'GPT readback passed but partition reread failed; do not format using stale geometry'
sleep 2
[ "$(blockdev --getsize64 /dev/sda15)" -eq "$XR_USERDATA_TARGET_BYTES" ] || xr_die 'New userdata size mismatch'
[ "$(blockdev --getsize64 /dev/sda16)" -eq "$XR_OSSTORE_BYTES" ] || xr_die 'New osstore size mismatch'
[ "$(cat /sys/class/block/sda16/start)" -eq "$((XR_OSSTORE_START * 8))" ] || xr_die 'New osstore start mismatch'
xr_shrunk_superblocks
xr_marker gpt-verified
echo 'VR700 GPT readback and kernel partition geometry verified; osstore is unformatted'
