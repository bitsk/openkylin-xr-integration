#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Enable the native UKUI Wayland session on an installed A081 root."""
import os
from pathlib import Path
import subprocess

if os.geteuid()!=0 or os.uname().machine!='aarch64':
 raise SystemExit('Run as root on native A081 arm64')
if Path('/etc/a081-rootfs-id').read_text().strip()!='a081-openkylin-3.0-arm64':
 raise SystemExit('Expected the installed openKylin 3.0 root')
if b'A081' not in Path('/proc/device-tree/model').read_bytes():
 raise SystemExit('Unexpected board')
if not Path('/usr/share/wayland-sessions/kylin-wlcom.desktop').is_file():
 raise SystemExit('Install the official Kylin Wayland compositor and UKUI first')
config=Path('/etc/lightdm/lightdm.conf.d/50-a081.conf');config.parent.mkdir(parents=True,exist_ok=True)
config.write_text('[Seat:*]\nautologin-user=mix\nautologin-user-timeout=0\nuser-session=kylin-wlcom\nautologin-session=kylin-wlcom\n')
mask=Path('/etc/systemd/system/lightdm.service')
if mask.is_symlink() and str(mask.readlink())=='/dev/null':mask.unlink()
policy=Path('/usr/sbin/policy-rc.d')
if policy.is_file() and policy.read_text()=='#!/bin/sh\nexit 101\n':policy.unlink()
subprocess.run(['systemctl','daemon-reload'],check=True)
subprocess.run(['systemctl','set-default','graphical.target'],check=True)
print('UKUI Wayland enabled for the next boot; restart LightDM in an exclusive display window to validate.')
