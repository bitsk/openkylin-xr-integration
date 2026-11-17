# VR700 / DREAM PRO bring-up

This model has an independent mainline board description and firmware namespace.
MIX per-device calibration, boot images, wireless identities and root selectors
are not inputs to this model. Kernel code remains in `bitsk/qiyu-kernel` and its
selected commit is packaged by `xr-kernel`.

Installed openKylin boot, USB ACM/ECM, dual DSI initialization, the Kylin Wayland
desktop and Adreno 650 Vulkan rendering have passed device checks. HyperSpace
completed a bounded simulated-input run with 3,491 stereo frames and clean
component shutdown. Android B/root return and the existing application inventory
were checked after userdata shrink and after the installed system run.

This validates initial graphics bring-up. Physical headset/controller/hand
tracking, radio, audio and wearer/optical acceptance remain pending. The generic
native XR metapackage selects A081 resources and must not be installed on VR700.

## Installed openKylin root

Use the exact official ARM64 base selected by
`xr-image-tools/systems/openkylin/source.lock.json`. The prepared tar preserves
numeric ownership, ACLs and xattrs. A fresh writable root can omit
`./sysroot/ostree/repo` (the live image's duplicate restore repository); the active
`/usr` and package database remain intact. The complete extracted root including
that repository needs more than 24 GiB.

Configure the inactive root with `openkylin/configure.py`, supplying matching
committed-kernel modules and an explicitly prepared VR700 firmware directory.
This enables only the physical USB maintenance console and preserves the USB ECM
address established by the initramfs. It does not copy another device's host keys,
network credentials, calibration or application state. Generic desktop login and
XR sessions are separate activation/acceptance steps.

For explicit desktop bring-up, `--enable-desktop` creates locked account `xr`
(UID 1000) with video/render/audio/input groups and enables LightDM local autologin.
It verifies the installed `kylin-wlcom.desktop` entry and executable, and applies
only known UKUI idle/lock/sleep settings after verifying their installed schemas.
SSH remains masked and the password remains locked. This does not enable XR.

A maintenance chroot can use `--root / --offline-chroot` only when `/proc/self`
and `/run/systemd/system` are absent and the root-owned mode-0600 file
`/run/vr700-offline-config` contains `vr700-maintenance-offline-root`. The token is
consumed after successful configuration. Preserve this device directory layout
or supply `--board-root` when invoking a relocated configuration script.

## Early userspace

`initramfs/build.py` requires an explicit static ARM64 BusyBox and its SHA-256,
a `gen_init_cpio` tool, a new output directory, a build epoch and a private JSON
configuration. Required keys are `expected_serial`, `storage_mode`, `storage_uuid`,
`usb_device_mac`, `usb_host_mac`, `usb_address` and `usb_netmask`.
`storage_uuid` is omitted for maintenance. Additional tools/libraries can be
included with explicit `--extra-tree` roots; each file digest is recorded.
An optional `usb_peer_address` serves one DHCP lease on the USB interface,
without advertising a default route or DNS. This keeps host network managers
from disconnecting a link that otherwise has no DHCP server. The BusyBox input
must include `udhcpd` when this option is selected.

- `storage_mode=maintenance` opens only USB ACM/ECM and a persistent maintenance
  shell. It mounts no storage and has no automatic reboot timer.
- `storage_mode=osstore` mounts the verified ext4 UUID and binds
  `systems/openkylin/rootfs` as the root.
- `storage_mode=userdata-image` is an optional installation mode requiring
  explicit authorization to write Android's userdata filesystem. It also needs
  `rootfs_uuid` and a regular 24 GiB `local/openkylin/rootfs.ext4` file, whose UUID
  and installation marker are checked read-only before writable activation.

The private configuration and resulting ramdisk are not public artifacts.
The initramfs verifies `iqiyi,vr700`, the bootloader serial, the filesystem UUID,
the root marker and matching modules. Neither mode partitions or formats storage.
The outer backing filesystem remains mounted below `/run/xr-store`. Failures leave
a local USB shell and request a normal reboot after two minutes. Recovery image
installation, full partition readback and the Android return path must be verified
separately before activating a candidate.

## Bluetooth identity

The board overlay runs `vr700-bluetooth-address.service` before BlueZ. QCA6390
firmware alone leaves the controller unconfigured when it contains a generic
address. The helper mounts this device's persist partition read-only with journal
replay disabled, validates `bluetooth/.bt_nv.bin`, and supplies its factory address
through the Linux Bluetooth management interface. It verifies the controller's
actual address before finishing. The address is never included in the package or
printed to the journal; persist is never modified. Controller enumeration, radio
power/discovery, pairing and audio are separate validation stages. The model
overlay initializes `/etc/bluetooth/ukui-bluetooth.conf` with the Bluetooth
switch enabled. The installed UKUI service uses this INI setting for its power
policy. For an existing installation, enable it through
`com.ukui.bluetooth.setDefaultAdapterAttr` with `Powered=true`, which updates
the service state and its persisted configuration together. Subsequent user
changes remain under UKUI control.

The tracking capsule selects bounded OV7251 startup exposure convergence. Its
transient measurement frames remain on the device and are removed after each
epoch. The final producer uses fixed read-back controls and the corresponding
exposure timestamps. Tracking quality remains the original algorithm's result.
