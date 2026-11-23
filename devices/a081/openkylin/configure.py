#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Configure an inactive native ARM64 root. Never select a boot or flash."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--root',required=True,type=Path)
p.add_argument('--source-root',required=True,type=Path,help='Installed board baseline supplying modules, firmware and private network/SSH configuration')
p.add_argument('--kernel-release',required=True)
a=p.parse_args();r=a.root.resolve();s=a.source_root.resolve()
if os.geteuid()!=0 or os.uname().machine!='aarch64':p.error('Run as root on native arm64')
if r==Path('/') or r==s or (r/'etc/a081-rootfs-id').exists():p.error('Choose a new inactive root')
release=(r/'usr/lib/os-release').read_text()
if 'ID=openkylin' not in release or 'VERSION_ID="3.0"' not in release:p.error('Expected openKylin 3.0')
if not (s/'etc/a081-rootfs-id').is_file():p.error('Source is not a board baseline')
model=Path('/proc/device-tree/model').read_text().rstrip('\0')
if 'A081' not in model:p.error('Expected MIX A081')
if not (s/'usr/lib/modules'/a.kernel_release).is_dir():p.error('Matching baseline modules required')
if not (r/'usr/share/keyrings/openkylin-archive-anything-keyring.gpg').is_file():p.error('Install openkylin-archive-anything in the base root first')

def write(name,text,mode=0o644):
 q=r/name;q.parent.mkdir(parents=True,exist_ok=True)
 if q.is_symlink():q.unlink()
 q.write_text(text);q.chmod(mode)

def link(name,target):
 q=r/name;q.parent.mkdir(parents=True,exist_ok=True)
 if q.is_symlink() or q.exists():q.unlink()
 q.symlink_to(target)

def run(*args):subprocess.run(['chroot',str(r),*args],check=True,env={**os.environ,'SYSTEMD_OFFLINE':'1','DEBIAN_FRONTEND':'noninteractive'})

# Maintain native distribution libraries; only board resources cross roots.
board=Path(__file__).resolve().parent.parent
model_config=json.loads((board/'model.json').read_text())
shutil.copytree(board.parent/model_config['shared_overlay'],r,dirs_exist_ok=True,symlinks=True)
shutil.copytree(board/'overlay',r,dirs_exist_ok=True,symlinks=True)
shutil.copytree(s/'usr/lib/modules'/a.kernel_release,r/'usr/lib/modules'/a.kernel_release,symlinks=True)
for folder in ['qcom','ath11k']:
 shutil.copytree(s/'usr/lib/firmware'/folder,r/'usr/lib/firmware'/folder,dirs_exist_ok=True,symlinks=True)
shutil.copytree(s/'usr/lib/firmware/xr/a081',r/'usr/lib/firmware/xr/a081',dirs_exist_ok=True,symlinks=True)
for q in (s/'usr/lib/firmware').glob('regulatory.db*'):shutil.copy2(q,r/'usr/lib/firmware'/q.name)
write('etc/hostname','a081-openkylin\n')
write('etc/hosts','127.0.0.1 localhost\n127.0.1.1 a081-openkylin\n::1 localhost ip6-localhost\n')
write('etc/fstab','# Root and /osstore are mounted by the board initramfs.\n')
for q in (r/'etc/apt/sources.list.d').glob('*'):
 if q.suffix in ('.list','.sources'):
  q.rename(q.with_name(q.name+'.disabled'))
apt=Path(__file__).resolve().parent/'apt'
write('etc/apt/sources.list',(apt/'sources.list').read_text())
for q in sorted(apt.iterdir()):
 if q.name!='sources.list':write('etc/apt/sources.list.d/'+q.name,q.read_text())
write('etc/resolv.conf','nameserver 1.1.1.1\nnameserver 9.9.9.9\n')
write('etc/NetworkManager/conf.d/10-a081-dns.conf','[main]\ndns=systemd-resolved\nrc-manager=symlink\n')
write('etc/timezone','Asia/Hong_Kong\n');link('etc/localtime','/usr/share/zoneinfo/Asia/Hong_Kong')
write('etc/machine-id','')
link('var/lib/dbus/machine-id','/etc/machine-id')
write('etc/default/locale','LANG=zh_CN.UTF-8\n')
write('etc/systemd/journald.conf.d/a081.conf','[Journal]\nStorage=persistent\nSystemMaxUse=128M\n')
write('usr/sbin/policy-rc.d','#!/bin/sh\nexit 101\n',0o755)
# Keep remote access available while booting the new root, with the existing
# private host key and authorized keys. Never include them in a public bundle.
ssh=r/'etc/ssh/a081-backup';ssh.parent.mkdir(parents=True,exist_ok=True)
shutil.copytree(s/'etc/ssh/a081-backup',ssh,symlinks=True)
write('etc/systemd/system/a081-backup-ssh.service',(s/'etc/systemd/system/a081-backup-ssh.service').read_text().replace('/usr/bin/sshd','/usr/sbin/sshd'))
network=r/'etc/NetworkManager/system-connections';network.mkdir(parents=True,exist_ok=True)
for q in (s/'etc/NetworkManager/system-connections').glob('*.nmconnection'):
 shutil.copy2(q,network/q.name);(network/q.name).chmod(0o600)
shutil.copy2(board/'network/a081-usb-console.service',r/'etc/systemd/system/a081-usb-console.service')
write('etc/systemd/network/10-a081-wlan.link',(board/'network/10-a081-wlan.link').read_text())
write('usr/local/sbin/boot-android','#!/bin/sh\nexec systemctl reboot\n',0o755)
# The generic PC image contains boot/restore services inappropriate for bind
# mounted osstore roots. The existing bootloader and recovery manage booting.
for unit in ['casper.service','casper-md5check.service','casper-uuid.service','casper-getty.service',
 'grub-initrd-fallback.service','grub-common.service','ostree-remount.service',
 'ostree-finalize-staged.service','ostree-prepare-root.service','ostree-coredata-restore.service',
 'open-vm-tools.service','vgauth.service','apt-daily.timer','apt-daily-upgrade.timer',
 'dnsmasq.service','smartmontools.service','ssh.service','ssh.socket','lightdm.service']:
 link('etc/systemd/system/'+unit,'/dev/null')
link('etc/systemd/system/default.target','/usr/lib/systemd/system/multi-user.target')
for unit in ['NetworkManager.service','bluetooth.service','a081-usb-console.service','a081-backup-ssh.service','a081-thermal-profile.service']:
 link('etc/systemd/system/multi-user.target.wants/'+unit,'/etc/systemd/system/'+unit if unit.startswith('a081-') and unit!='a081-thermal-profile.service' else '/usr/lib/systemd/system/'+unit)
run('/usr/sbin/useradd','--create-home','--uid','1000','--shell','/bin/bash','mix')
run('/usr/sbin/usermod','--append','--groups','video,render,audio,input','mix')
run('/usr/sbin/depmod','-a',a.kernel_release)
write('etc/a081-rootfs-id','a081-openkylin-3.0-arm64\n')
result={'system':'openkylin','version':'3.0','architecture':'arm64','kernel_release':a.kernel_release,'firmware_source':'installed board baseline','private_network_and_ssh_imported':True,'desktop_enabled':False,'device_boot_validated':False}
write('usr/share/xr/openkylin-install.json',json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
