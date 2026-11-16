#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the VR700 early userspace from explicit tools and private identity."""
import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import uuid
import lzma


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4194304), b''):
            h.update(block)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--busybox', type=Path, required=True)
    p.add_argument('--busybox-sha256', required=True)
    p.add_argument('--gen-init-cpio', type=Path, required=True)
    p.add_argument('--private-config', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--extra-tree', type=Path, action='append', default=[],
                   help='Explicit additional maintenance tool/library root; files are hashed in the receipt')
    p.add_argument('--build-epoch', type=int, required=True)
    a = p.parse_args()
    if a.output.exists():
        p.error('Use a new output directory')
    if sha(a.busybox) != a.busybox_sha256:
        p.error('BusyBox SHA-256 mismatch')
    cfg = json.loads(a.private_config.read_text())
    required = {'expected_serial', 'storage_mode',
                'usb_device_mac', 'usb_host_mac', 'usb_address', 'usb_netmask'}
    if not required.issubset(cfg) or cfg['storage_mode'] not in ('osstore', 'userdata-image', 'maintenance'):
        p.error('Private serial, storage mode/UUID and USB settings required')
    if not re.fullmatch('[A-Za-z0-9_-]{1,64}', cfg['expected_serial']):
        p.error('Invalid device serial')
    if cfg['storage_mode'] != 'maintenance':
        uuid.UUID(cfg['storage_uuid'])
    else:
        cfg['storage_uuid'] = ''
    required.add('storage_uuid')
    if cfg['storage_mode'] == 'userdata-image':
        uuid.UUID(cfg['rootfs_uuid'])
    else:
        cfg['rootfs_uuid'] = ''
    for key in ('usb_device_mac', 'usb_host_mac'):
        mac = cfg[key]
        if not re.fullmatch('(?:[0-9a-f]{2}:){5}[0-9a-f]{2}', mac) or int(mac[:2], 16) & 3 != 2:
            p.error('USB MACs must be locally administered unicast addresses')
    if cfg['usb_device_mac'] == cfg['usb_host_mac']:
        p.error('USB endpoint MACs must differ')
    ipaddress.IPv4Interface(cfg['usb_address'] + '/' + cfg['usb_netmask'])
    out = a.output.resolve()
    out.mkdir(parents=True, mode=0o700)
    for src, name in ((a.busybox, 'busybox'), (Path(__file__).with_name('init'), 'init')):
        shutil.copyfile(src, out / name)
        (out / name).chmod(0o755)
    conf = ''.join(k + '=' + shlex.quote(str(cfg[k])) + '\n' for k in sorted(required | {'rootfs_uuid'}))
    (out / 'xr-device.conf').write_text(conf)
    (out / 'xr-device.conf').chmod(0o600)
    (out / 'build-epoch').write_text(str(a.build_epoch) + '\n')
    entries = ['dir ' + d + ' 0755 0 0' for d in ('/bin', '/dev', '/etc', '/proc', '/sys', '/run', '/store', '/newroot')]
    entries += ['nod /dev/console 0600 0 0 c 5 1', 'nod /dev/kmsg 0600 0 0 c 1 11',
                'file /bin/busybox ' + str(out / 'busybox') + ' 0755 0 0',
                'file /init ' + str(out / 'init') + ' 0755 0 0',
                'file /etc/xr-device.conf ' + str(out / 'xr-device.conf') + ' 0600 0 0',
                'file /build-epoch ' + str(out / 'build-epoch') + ' 0644 0 0']
    applets = 'blkid cat date grep ifconfig ln losetup mdev mkdir mount readlink reboot setsid sh sleep stat switch_root sync tr umount uname cp dd df dmesg du free head ls mv od ps rm sed sha256sum tail touch wc cmp blockdev awk cut rmdir basename chmod'
    entries += ['slink /bin/' + name + ' busybox 0777 0 0' for name in applets.split()]
    extra_hashes = {}
    destinations = {entry.split()[1] for entry in entries}
    for tree in a.extra_tree:
        tree = tree.resolve()
        if not tree.is_dir():
            p.error('Extra tree must be an existing directory')
        for source in sorted(tree.rglob('*')):
            dest = '/' + source.relative_to(tree).as_posix()
            if any(c.isspace() for c in str(source)):
                p.error('cpio list paths must not contain whitespace')
            if dest in destinations:
                if source.is_dir():
                    continue
                p.error('Extra tree overlaps an existing initramfs entry: ' + dest)
            destinations.add(dest)
            if source.is_symlink():
                target = str(source.readlink())
                if any(c.isspace() for c in target):
                    p.error('cpio symlink targets must not contain whitespace')
                entries.append('slink ' + dest + ' ' + target + ' 0777 0 0')
                extra_hashes[dest] = {'symlink': target}
            elif source.is_dir():
                entries.append('dir ' + dest + ' 0755 0 0')
            elif source.is_file():
                mode = source.stat().st_mode & 0o777
                entries.append(f'file {dest} {source} {mode:04o} 0 0')
                extra_hashes[dest] = {'sha256': sha(source)}
            else:
                p.error('Only files, directories and symlinks allowed in extra tree')
    (out / 'cpio.list').write_text('\n'.join(entries) + '\n')
    archive = subprocess.check_output([str(a.gen_init_cpio.resolve()), '-t', '0', str(out / 'cpio.list')])
    (out / 'initramfs.cpio.xz').write_bytes(lzma.compress(archive, format=lzma.FORMAT_XZ,
                                                       check=lzma.CHECK_CRC32, preset=9))
    result = {'schema': 1, 'device': 'vr700', 'storage_mode': cfg['storage_mode'],
              'private_configuration_included': True, 'device_tested': False,
              'files_sha256': {name: sha(out / name) for name in
                               ('busybox', 'init', 'initramfs.cpio.xz')},
              'gen_init_cpio_sha256': sha(a.gen_init_cpio), 'extra_tree_files': extra_hashes}
    (out / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
