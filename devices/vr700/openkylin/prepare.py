#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Extract the exact official base into a new host directory, without devices."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--archive-output', action='store_true',
                   help='Write a filtered uncompressed tar preserving archive metadata without host root')
    a = p.parse_args()
    if not a.archive_output and os.geteuid() != 0:
        p.error('Root is needed to retain archive numeric owners and capabilities')
    if a.output.exists() or a.output.is_symlink():
        p.error('Use a new root output directory')
    lock = json.loads(Path(__file__).with_name('base.lock.json').read_text())
    digest = hashlib.sha256()
    with a.archive.open('rb') as f:
        for block in iter(lambda: f.read(4194304), b''):
            digest.update(block)
    if digest.hexdigest() != lock['prepared_tar_sha256']:
        p.error('Prepared base archive SHA-256 mismatch')
    if a.archive_output:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        excluded = lock['excluded_path'].removeprefix('./')
        with tarfile.open(a.archive, 'r|') as src, tarfile.open(a.output, 'w|', format=tarfile.PAX_FORMAT) as dst:
            for member in src:
                name = member.name.removeprefix('./')
                if name == excluded or name.startswith(excluded + '/'):
                    continue
                if member.islnk():
                    target = member.linkname.removeprefix('./')
                    if target == excluded or target.startswith(excluded + '/'):
                        raise ValueError('Included hardlink refers to excluded restore repository')
                dst.addfile(member, src.extractfile(member) if member.isfile() else None)
    else:
        a.output.mkdir(parents=True)
        subprocess.run(['tar', '--numeric-owner', '--xattrs', '--xattrs-include=*', '--acls',
                        '--exclude=' + lock['excluded_path'], '-xpf', str(a.archive.resolve()),
                        '-C', str(a.output.resolve())], check=True)
    result = {'schema': 1, 'system': 'openkylin', 'architecture': 'arm64',
              'base_archive_sha256': digest.hexdigest(),
              'omitted_live_restore_repository': lock['excluded_path'],
              'archive_output': a.archive_output, 'board_configuration_complete': False, 'device_accessed': False}
    (a.output.parent / (a.output.name + '-base.json')).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
