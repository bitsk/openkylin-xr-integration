#!/bin/sh
# Run on installed VR700 after exact locked component packages are installed.
# Copies project bytes only from their installed package paths; starts nothing.
set -eu
[ "$(id -u)" = 0 ]
[ "$(cat /etc/xr-rootfs-id)" = vr700-openkylin-3.0-arm64 ]
tr '\000' '\n' < /sys/firmware/devicetree/base/compatible | grep -Fxq iqiyi,vr700
capsule=/opt/xr/vr700/session
lib=/usr/lib/aarch64-linux-gnu/xr/controller
for file in controller-sdk-pose liba081-sdk-log.so libcdsprpc.so libcdsprpc_system.so liba081-snpe-runtime.so; do
    test -f "$lib/$file"
done
test -x /usr/bin/xr-hexagonrpcd
test -x /usr/bin/xr-controller-uart
test -f /usr/lib/aarch64-linux-gnu/xr/monado/bin/linuxarm64/driver_monado.so
test -x /usr/lib/aarch64-linux-gnu/xr/monado/pose-watch
install -d -m 755 "$capsule/controller-dsp" "$capsule/tracking"
install -m 755 "$lib/controller-sdk-pose" "$capsule/controller-sdk-pose"
install -m 644 "$lib/liba081-sdk-log.so" "$capsule/liba081-sdk-log.so"
for file in libcdsprpc.so libcdsprpc_system.so liba081-snpe-runtime.so; do
    install -m 644 "$lib/$file" "$capsule/controller-dsp/$file"
done
install -m 755 /usr/bin/xr-hexagonrpcd "$capsule/tracking/hexagonrpcd-a081"
install -m 755 /usr/lib/aarch64-linux-gnu/xr/monado/pose-watch "$capsule/pose-watch"
sha256sum "$capsule/pose-watch" "$capsule/controller-sdk-pose" "$capsule/liba081-sdk-log.so" "$capsule/controller-dsp/"*.so "$capsule/tracking/hexagonrpcd-a081" > "$capsule/installed-component-sha256.txt"
echo 'Capsule completed from installed components; no services started.'
