#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Shared guards for an explicitly staged, device-specific maintenance plan.
set -eu
export PATH=/bin:/system/bin
export LD_LIBRARY_PATH=/system/lib64
XR_STORAGE_PLAN=${XR_STORAGE_PLAN:-/plan}
XR_STORAGE_WORK=/run/vr700-storage

xr_die() { echo "VR700 storage: $*" >&2; exit 1; }
[ -r "$XR_STORAGE_PLAN/storage.env" ] || xr_die 'Private storage plan missing'
. "$XR_STORAGE_PLAN/storage.env"
[ "$((XR_ORIGINAL_FOOTER_BLOCK + 4))" -eq "$((XR_USERDATA_ORIGINAL_BYTES / 4096))" ] || xr_die 'Original footer is not at partition EOF'
[ "$((XR_TARGET_FOOTER_BLOCK + 4))" -eq "$((XR_USERDATA_TARGET_BYTES / 4096))" ] || xr_die 'Target footer is not at partition EOF'
[ "$((XR_FS_TARGET_BLOCKS % 512))" -eq 0 ] || xr_die 'Filesystem target is not segment aligned'
[ "$((XR_USERDATA_TARGET_BYTES / 4096 - XR_FS_TARGET_BLOCKS))" -ge 512 ] || xr_die 'Filesystem lacks reserved tail space'
XR_PLAN_HASH=$(sha256sum "$XR_STORAGE_PLAN/storage.env" | cut -d ' ' -f 1)
XR_BOOT_ID=$(cat /proc/sys/kernel/random/boot_id)
mkdir -p "$XR_STORAGE_WORK"

xr_lock() {
    mkdir "$XR_STORAGE_WORK/operation.lock" 2>/dev/null || xr_die 'Another storage operation is active; inspect before clearing its lock'
    trap 'rmdir "$XR_STORAGE_WORK/operation.lock"' 0
    trap 'exit 1' 1 2 15
}

xr_hash_file() {
    [ -f "$1" ] || xr_die "Missing staged file: $1"
    [ "$(sha256sum "$1" | cut -d ' ' -f 1)" = "$2" ] || xr_die "Staged digest differs: $1"
}

xr_region() {
    # Read to a regular RAM file so a failed dd cannot be hidden by a pipeline.
    xr_hash_file "$4" "$5"
    dd if="$1" of="$XR_STORAGE_WORK/region.bin" bs=4096 skip="$2" count="$3" 2>"$XR_STORAGE_WORK/region.err" || xr_die 'Block read failed'
    [ "$(wc -c < "$XR_STORAGE_WORK/region.bin")" -eq "$((4096 * $3))" ] || xr_die 'Short block read'
    cmp -s "$XR_STORAGE_WORK/region.bin" "$4" || xr_die "Device region differs: $1 block $2"
}

xr_identity() {
    tr '\000' '\n' < /sys/firmware/devicetree/base/compatible |
        grep -Fxq 'iqiyi,vr700' || xr_die 'Expected independent VR700 device tree'
    xr_serial=
    for xr_arg in $(cat /proc/cmdline); do
        case "$xr_arg" in androidboot.serialno=*) xr_serial=${xr_arg#*=};; esac
    done
    [ "$xr_serial" = "$XR_EXPECTED_SERIAL" ] || xr_die 'Bootloader serial mismatch'
    [ "$(blockdev --getss /dev/sda)" -eq 4096 ] || xr_die 'Expected 4096-byte logical sectors'
    [ "$(blockdev --getsize64 /dev/sda)" -eq "$XR_DISK_BYTES" ] || xr_die 'UFS size mismatch'
    [ "$(cat /sys/class/block/sda15/start)" -eq "$((XR_USERDATA_START * 8))" ] || xr_die 'userdata start moved'
}

xr_unmounted() {
    # mountinfo major:minor catches aliases, UUID mounts and bind mounts.
    # Reject active device-mapper holders as well as direct filesystem mounts.
    for xr_block in /sys/class/block/sda /sys/class/block/sda[0-9]*; do
        [ -r "$xr_block/dev" ] || continue
        xr_devno=$(cat "$xr_block/dev")
        if awk -v dev="$xr_devno" '$3 == dev { found=1 } END { exit !found }' /proc/self/mountinfo; then
            xr_die "UFS filesystem is mounted: ${xr_block##*/}"
        fi
        for xr_holder in "$xr_block"/holders/*; do
            [ ! -e "$xr_holder" ] || xr_die "Active block holder: $xr_holder"
        done
    done
    while read -r xr_source xr_rest; do
        case "$xr_source" in Filename|/dev/zram*) continue;; esac
        xr_resolved=$(readlink -f "$xr_source" 2>/dev/null || true)
        case "$xr_resolved" in /dev/sda*|/dev/block/sda*) xr_die 'UFS swap is active';; esac
    done < /proc/swaps
    # Also inspect traditional mount sources, including /dev/block/by-name.
    while read -r xr_source xr_rest; do
        case "$xr_source" in /dev/*)
            xr_resolved=$(readlink -f "$xr_source" 2>/dev/null || true)
            case "$xr_resolved" in /dev/sda*|/dev/block/sda*) xr_die 'UFS mount source is active';; esac
        esac
    done < /proc/mounts
}

xr_original_gpt() {
    xr_region /dev/sda 0 6 "$XR_STORAGE_PLAN/original/gpt-first.bin" "$XR_ORIGINAL_FIRST_SHA256"
    xr_region /dev/sda "$XR_BACKUP_ENTRIES_LBA" 5 "$XR_STORAGE_PLAN/original/gpt-last.bin" "$XR_ORIGINAL_LAST_SHA256"
}

xr_candidate_gpt() {
    xr_region /dev/sda 0 6 "$XR_STORAGE_PLAN/candidate/gpt-first.bin" "$XR_CANDIDATE_FIRST_SHA256"
    xr_region /dev/sda "$XR_BACKUP_ENTRIES_LBA" 5 "$XR_STORAGE_PLAN/candidate/gpt-last.bin" "$XR_CANDIDATE_LAST_SHA256"
}

xr_u32() { od -An -tu4 -j"$2" -N4 "$1" | tr -d ' \n'; }
xr_u64() { od -An -tu8 -j"$2" -N8 "$1" | tr -d ' \n'; }

xr_shrunk_superblocks() {
    dd if=/dev/sda15 of="$XR_STORAGE_WORK/superblocks.bin" bs=4096 count=2 2>/dev/null || xr_die 'Cannot read superblocks'
    [ "$(wc -c < "$XR_STORAGE_WORK/superblocks.bin")" -eq 8192 ] || xr_die 'Short superblock read'
    for xr_base in 1024 5120; do
        [ "$(xr_u32 "$XR_STORAGE_WORK/superblocks.bin" "$xr_base")" -eq 4076150800 ] || xr_die 'F2FS magic mismatch'
        [ "$(xr_u64 "$XR_STORAGE_WORK/superblocks.bin" "$((xr_base+36))")" -eq "$XR_FS_TARGET_BLOCKS" ] || xr_die 'F2FS block_count mismatch'
        xr_logseg=$(xr_u32 "$XR_STORAGE_WORK/superblocks.bin" "$((xr_base+20))")
        xr_main=$(xr_u32 "$XR_STORAGE_WORK/superblocks.bin" "$((xr_base+92))")
        xr_segments=$(xr_u32 "$XR_STORAGE_WORK/superblocks.bin" "$((xr_base+68))")
        [ "$xr_logseg" -eq 9 ] && [ "$xr_main" -eq "$XR_FS_MAIN_BLOCK" ] || xr_die 'F2FS metadata geometry changed'
        [ "$((xr_main + xr_segments * 512))" -le "$XR_FS_TARGET_BLOCKS" ] || xr_die 'F2FS main segments exceed block_count'
        xr_uuid=$(od -An -tx1 -j"$((xr_base+108))" -N16 "$XR_STORAGE_WORK/superblocks.bin" | tr -d ' \n')
        [ "$xr_uuid" = "$XR_FS_UUID_HEX" ] || xr_die 'F2FS UUID changed'
    done
}

xr_fsck() {
    xr_log=$1
    xr_hash_file /system/bin/fsck.f2fs "$XR_FSCK_SHA256"
    /system/bin/fsck.f2fs --dry-run -q 1 -t /dev/sda15 </dev/null >"$XR_STORAGE_WORK/$xr_log.log" 2>"$XR_STORAGE_WORK/$xr_log.err" || xr_die "Original fsck failed: $xr_log"
    if grep -Eq '\[Fail\]|\[ASSERT\]|\[ERROR\]|Error:' "$XR_STORAGE_WORK/$xr_log.log" "$XR_STORAGE_WORK/$xr_log.err"; then
        xr_die "Original fsck reported errors: $xr_log; no automatic normalization"
    fi
    [ "$(grep -c '\[Ok\.\.\]' "$XR_STORAGE_WORK/$xr_log.log")" -ge 10 ] || xr_die 'Incomplete fsck checks'
    grep '<ino =' "$XR_STORAGE_WORK/$xr_log.log" > "$XR_STORAGE_WORK/$xr_log.tree" || xr_die 'Missing filesystem tree'
    grep '^\[FSCK\] valid_' "$XR_STORAGE_WORK/$xr_log.log" > "$XR_STORAGE_WORK/$xr_log.counts" || xr_die 'Missing allocation counts'
    [ "$(wc -l < "$XR_STORAGE_WORK/$xr_log.counts")" -ge 4 ] || xr_die 'Incomplete allocation counts'
}

xr_marker() { printf '%s\n%s\n' "$XR_PLAN_HASH" "$XR_BOOT_ID" > "$XR_STORAGE_WORK/$1"; }
xr_require_marker() {
    [ -f "$XR_STORAGE_WORK/$1" ] || xr_die "Missing this-boot prerequisite: $1"
    [ "$(sed -n '1p' "$XR_STORAGE_WORK/$1")" = "$XR_PLAN_HASH" ] || xr_die 'Prerequisite belongs to another plan'
    [ "$(sed -n '2p' "$XR_STORAGE_WORK/$1")" = "$XR_BOOT_ID" ] || xr_die 'Prerequisite belongs to another boot'
}
