#!/system/bin/sh
# Installed root-owned under /data/adb/qiyu-boot; invoked with su -mm.
set -eu
PATH=/system/bin:/system/xbin:/sbin
export PATH
fail() { echo "ERROR: $*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || fail '需要 root 授权'
[ "$(getprop ro.product.model)" = A081 ] || fail '设备型号不匹配'
[ "$(getprop ro.boot.slot_suffix)" = _b ] || fail '当前不是已验证的 Android B'
action=${1:-}
target=${2:-}
case "$action" in preflight|reboot) ;; *) fail '未知操作' ;; esac
case "$target" in
    openkylin) marker=a081-openkylin-3.0-arm64 ;;
    steamos) marker=a081-steamos-arm64 ;;
    debian) marker=a081-debian-trixie-arm64 ;;
    *) fail '未知系统' ;;
esac
. /data/adb/qiyu-boot/config.sh
[ -n "$RECOVERY_SHA256" ] && [ -n "$KERNEL_RELEASE" ] || fail '缺少本机安装配置'
actual=$(sha256sum /dev/block/by-name/recovery_b)
[ "${actual%% *}" = "$RECOVERY_SHA256" ] || fail 'Recovery 已改变，请更新安装配置'

# Android mksh closes extra descriptors across exec. /dev is cleared on boot.
lock=/dev/qiyu-boot-request
mkdir "$lock" 2>/dev/null || fail '另一个启动请求正在执行'
store=/mnt/qiyu-boot-store
mounted=0
cleanup() {
    if [ "$mounted" = 1 ]; then umount "$store" || true; fi
    rmdir "$lock" || true
}
trap cleanup EXIT
mkdir -p "$store"
chmod 700 "$store"
mount | grep -Fq " on $store " && fail '启动目录已被挂载'
if [ "$action" = preflight ]; then
    mount -t ext4 -o ro,noload /dev/block/by-name/osstore "$store"
else
    mount -t ext4 -o noatime /dev/block/by-name/osstore "$store"
fi
mounted=1
[ ! -L "$store/boot" ] && [ -d "$store/boot" ] || fail '启动目录无效'
root="$store/systems/$target/rootfs"
[ "$(cat "$root/etc/a081-rootfs-id")" = "$marker" ] || fail '系统安装标记不匹配'
[ -e "$root/usr/lib/systemd/systemd" ] || fail '系统启动程序缺失'
[ "$(cat "$store/systems/debian/rootfs/etc/a081-rootfs-id")" = a081-debian-trixie-arm64 ] || fail 'Debian 回退安装缺失'
[ -f "$root/usr/lib/modules/$KERNEL_RELEASE/modules.dep" ] ||
    [ -f "$root/lib/modules/$KERNEL_RELEASE/modules.dep" ] || fail '该系统缺少当前内核模块'
if [ "$action" = preflight ]; then
    echo "READY $target"
    if [ "$target" = steamos ] && [ "${STEAMOS_VR_READY:-0}" != 1 ]; then
        echo 'NOTICE SteamOS 可启动桌面，VR 自启动尚未通过验证。'
    fi
    umount "$store"
    mounted=0
    exit 0
fi
[ ! -L "$store/boot/next-system" ] || fail '单次启动项不能是符号链接'
tmp="$store/boot/.next-system.$$"
printf '%s\n' "$target" > "$tmp"
chmod 644 "$tmp"
mv -f "$tmp" "$store/boot/next-system"
date +%s > "$store/boot/clock-epoch"
sync
[ "$(cat "$store/boot/next-system")" = "$target" ] || fail '启动项读回失败'
umount "$store"
mounted=0
echo "REBOOTING $target"
/system/bin/reboot recovery
