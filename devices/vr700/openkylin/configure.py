#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Configure an inactive official openKylin ARM64 root for VR700 bring-up."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--modules', type=Path, required=True,
                   help='Directory containing lib/modules/KERNEL_RELEASE or usr/lib/modules/KERNEL_RELEASE')
    p.add_argument('--kernel-release', required=True)
    p.add_argument('--firmware', type=Path, required=True,
                   help='Explicit device-specific firmware tree to install below usr/lib/firmware/xr/vr700')
    a = p.parse_args()
    root = a.root.resolve()
    if os.geteuid() != 0:
        p.error('Run offline root configuration as root to preserve owners')
    if root == Path('/') or not root.is_dir() or (root / 'etc/xr-rootfs-id').exists():
        p.error('Use a fresh, inactive extracted root')
    if '/' in a.kernel_release or not a.kernel_release.endswith('-xr-vr700'):
        p.error('Expected the explicit VR700 kernel release')
    release = (root / 'usr/lib/os-release').read_text()
    if 'ID=openkylin' not in release or 'VERSION_ID="3.0"' not in release:
        p.error('Expected openKylin 3.0')
    status = (root / 'var/lib/dpkg/status').read_text()
    if not any(s.startswith('Package: libc6\n') and '\nArchitecture: arm64\n' in s
               for s in status.split('\n\n')):
        p.error('Expected ARM64 libc6 in base archive')
    modules = next((a.modules / prefix / a.kernel_release for prefix in ('lib/modules', 'usr/lib/modules')
                    if (a.modules / prefix / a.kernel_release).is_dir()), None)
    if modules is None or not a.firmware.is_dir():
        p.error('Matching modules and explicit VR700 firmware required')
    board = Path(__file__).resolve().parents[1]

    def write(name, text, mode=0o644):
        q = root / name
        q.parent.mkdir(parents=True, exist_ok=True)
        if q.is_symlink():
            q.unlink()
        q.write_text(text)
        q.chmod(mode)

    def link(name, target):
        q = root / name
        q.parent.mkdir(parents=True, exist_ok=True)
        if q.is_symlink() or q.is_file():
            q.unlink()
        q.symlink_to(target)

    shutil.copytree(board / 'overlay', root, dirs_exist_ok=True, symlinks=True)
    shutil.copytree(modules, root / 'usr/lib/modules' / a.kernel_release, symlinks=True)
    shutil.copytree(a.firmware, root / 'usr/lib/firmware/xr/vr700', dirs_exist_ok=True, symlinks=True)
    subprocess.run(['depmod', '-b', str(root), a.kernel_release], check=True)
    write('etc/hostname', 'vr700-openkylin\n')
    write('etc/hosts', '127.0.0.1 localhost\n127.0.1.1 vr700-openkylin\n::1 localhost ip6-localhost\n')
    write('etc/fstab', '# VR700 initramfs mounts the installed root and backing storage.\n')
    write('etc/machine-id', '')
    link('var/lib/dbus/machine-id', '/etc/machine-id')
    write('etc/default/locale', 'LANG=zh_CN.UTF-8\n')
    write('etc/systemd/journald.conf.d/vr700.conf', '[Journal]\nStorage=volatile\nRuntimeMaxUse=32M\n')
    write('usr/sbin/policy-rc.d', '#!/bin/sh\nexit 101\n', 0o755)
    # A recovery-booted installed root does not use PC live media or OSTree
    # restore/boot tooling. Generic graphics login is enabled after DRM works.
    for unit in ('casper.service', 'casper-md5check.service', 'casper-uuid.service',
                 'casper-getty.service', 'grub-initrd-fallback.service', 'grub-common.service',
                 'ostree-remount.service', 'ostree-finalize-staged.service',
                 'ostree-prepare-root.service', 'ostree-coredata-restore.service',
                 'open-vm-tools.service', 'vgauth.service', 'apt-daily.timer',
                 'apt-daily-upgrade.timer', 'dnsmasq.service', 'smartmontools.service',
                 'ssh.service', 'ssh.socket', 'lightdm.service'):
        link('etc/systemd/system/' + unit, '/dev/null')
    link('etc/systemd/system/default.target', '/usr/lib/systemd/system/multi-user.target')
    write('usr/local/sbin/boot-android', '#!/bin/sh\nexec systemctl reboot\n', 0o755)
    write('etc/xr-rootfs-id', 'vr700-openkylin-3.0-arm64\n')
    receipt = {'schema': 1, 'system': 'openkylin', 'version': '3.0', 'architecture': 'arm64',
               'device': 'vr700', 'kernel_release': a.kernel_release,
               'firmware_source': 'explicit device-specific input',
               'private_network_or_calibration_imported': False,
               'desktop_enabled': False, 'hyperspace_enabled': False,
               'device_boot_validated': False}
    write('usr/share/xr/vr700-install.json', json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
