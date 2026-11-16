#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Configure an inactive official openKylin ARM64 root for VR700 bring-up."""
import argparse
import configparser
import json
import os
from pathlib import Path
import shutil
import shlex
import xml.etree.ElementTree as ET
import subprocess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--enable-desktop', action='store_true',
                   help='Enable local xr autologin in the installed Kylin Wayland session for bring-up')
    p.add_argument('--offline-chroot', action='store_true',
                   help='Permit root=/ only in an explicitly marked chroot without proc or systemd runtime')
    p.add_argument('--board-root', type=Path, help='Explicit committed devices/vr700 source directory')
    p.add_argument('--modules', type=Path, required=True,
                   help='Directory containing lib/modules/KERNEL_RELEASE or usr/lib/modules/KERNEL_RELEASE')
    p.add_argument('--kernel-release', required=True)
    p.add_argument('--firmware', type=Path, required=True,
                   help='Explicit device-specific firmware tree to install below usr/lib/firmware/xr/vr700')
    a = p.parse_args()
    root = a.root.resolve()
    if os.geteuid() != 0:
        p.error('Run offline root configuration as root to preserve owners')
    if root == Path('/'):
        token = Path('/run/vr700-offline-config')
        if (not a.offline_chroot or Path('/proc/self').exists()
                or Path('/run/systemd/system').exists() or not token.is_file()
                or token.stat().st_uid != 0 or token.stat().st_mode & 0o077
                or token.read_text().strip() != 'vr700-maintenance-offline-root'):
            p.error('root=/ requires an explicitly marked offline chroot without proc/systemd')
    elif a.offline_chroot:
        p.error('--offline-chroot applies only to root=/')
    if not root.is_dir() or (root / 'etc/xr-rootfs-id').exists():
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
    board = a.board_root.resolve() if a.board_root else Path(__file__).resolve().parents[1]
    if json.loads((board / 'model.json').read_text()).get('id') != 'vr700':
        p.error('Expected VR700 board integration source')

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
    link('etc/systemd/system/multi-user.target.wants/vr700-usb-console.service',
         '../vr700-usb-console.service')
    module_target = root / 'usr/lib/modules' / a.kernel_release
    if modules.resolve() != module_target.resolve():
        shutil.copytree(modules, module_target, symlinks=True)
    firmware_target = root / 'usr/lib/firmware/xr/vr700'
    if a.firmware.resolve() != firmware_target.resolve():
        shutil.copytree(a.firmware, firmware_target, dirs_exist_ok=True, symlinks=True)
    depmod = shutil.which('depmod') or '/usr/sbin/depmod'
    subprocess.run([depmod, '-b', str(root), a.kernel_release], check=True)
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
    desktop_session = None
    if a.enable_desktop:
        session_file = root / 'usr/share/wayland-sessions/kylin-wlcom.desktop'
        session = configparser.ConfigParser(interpolation=None)
        session.read(session_file)
        command = shlex.split(session.get('Desktop Entry', 'Exec'))
        if (not command or '/' in command[0]
                or not os.access(root / 'usr/bin' / command[0], os.X_OK)
                or not (root / 'usr/lib/systemd/system/lightdm.service').is_file()):
            p.error('Official Kylin Wayland session and LightDM required')
        desktop_session = session_file.stem
        accounts = [line.split(':') for line in (root / 'etc/passwd').read_text().splitlines()]
        if any(row[0] == 'xr' or row[2] == '1000' for row in accounts):
            p.error('Fresh base must not already contain xr or UID 1000')

        def run_target(*command):
            prefix = [] if root == Path('/') else ['chroot', str(root)]
            subprocess.run(prefix + list(command), check=True,
                           env={**os.environ, 'PATH': '/usr/sbin:/usr/bin:/sbin:/bin',
                                'SYSTEMD_OFFLINE': '1'})

        run_target('/usr/sbin/useradd', '--uid', '1000', '--user-group',
                   '--create-home', '--shell', '/bin/bash',
                   '--groups', 'video,render,audio,input', 'xr')
        password = next(line.split(':')[1] for line in (root / 'etc/shadow').read_text().splitlines()
                        if line.startswith('xr:'))
        if not password.startswith(('!', '*')):
            raise ValueError('Desktop account password must remain locked')
        settings = {
            'org.ukui.screensaver': {'idle-activation-enabled': 'false',
                'idle-lock-enabled': 'false', 'sleep-activation-enabled': 'false', 'idle-delay': '0'},
            'org.ukui.session': {'idle-delay': '0'},
            'org.ukui.power-manager': {key: '0' for key in
                ('sleep-computer-ac', 'sleep-computer-battery', 'sleep-computer-ups',
                 'sleep-display-ac', 'sleep-display-battery', 'sleep-display-ups',
                 'hibernate-computer-ac', 'hibernate-computer-battery')},
        }
        settings['org.ukui.power-manager'].update({'idle-dim-ac': 'false', 'idle-dim-battery': 'false'})
        schemas = root / 'usr/share/glib-2.0/schemas'
        text = ''
        for schema, values in settings.items():
            tree = ET.parse(schemas / (schema + '.gschema.xml'))
            available = {key.attrib['name'] for element in tree.findall('schema')
                         if element.attrib.get('id') == schema for key in element.findall('key')}
            if not values.keys() <= available:
                raise ValueError('Installed UKUI schema lacks expected bring-up keys: ' + schema)
            text += '[' + schema + ']\n' + ''.join(key + '=' + value + '\n' for key, value in values.items()) + '\n'
        write('usr/share/glib-2.0/schemas/99-vr700-bringup.gschema.override', text)
        run_target('/usr/bin/glib-compile-schemas', '/usr/share/glib-2.0/schemas')
        write('etc/lightdm/lightdm.conf.d/50-vr700.conf',
              '[Seat:*]\nautologin-user=xr\nautologin-user-timeout=0\n'
              'user-session=' + desktop_session + '\nautologin-session=' + desktop_session + '\n')
        (root / 'etc/systemd/system/lightdm.service').unlink()
        link('etc/systemd/system/display-manager.service', '/usr/lib/systemd/system/lightdm.service')
        link('etc/systemd/system/default.target', '/usr/lib/systemd/system/graphical.target')
    write('usr/local/sbin/boot-android', '#!/bin/sh\nexec systemctl reboot\n', 0o755)
    write('etc/xr-rootfs-id', 'vr700-openkylin-3.0-arm64\n')
    receipt = {'schema': 1, 'system': 'openkylin', 'version': '3.0', 'architecture': 'arm64',
               'device': 'vr700', 'kernel_release': a.kernel_release,
               'firmware_source': 'explicit device-specific input',
               'private_network_or_calibration_imported': False,
               'desktop_enabled': a.enable_desktop, 'desktop_session': desktop_session,
               'desktop_user': 'xr' if a.enable_desktop else None,
               'desktop_password_locked': bool(a.enable_desktop), 'hyperspace_enabled': False,
               'device_boot_validated': False}
    write('usr/share/xr/vr700-install.json', json.dumps(receipt, indent=2) + '\n')
    if a.offline_chroot:
        Path('/run/vr700-offline-config').unlink()
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
