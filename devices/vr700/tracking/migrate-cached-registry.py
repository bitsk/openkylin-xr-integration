#!/usr/bin/env python3
"""Migrate an inactive installed VR700 runtime to its original read-only cache."""
import argparse
import hashlib
import json
import os
from pathlib import Path


def verify_directory(directory, entries, prefix):
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('Expected original directory: ' + str(directory))
    expected = {}
    for entry in entries:
        name = entry['target'].removeprefix(prefix)
        if Path(name).name != name or name in ('', '.', '..'):
            raise ValueError('Invalid receipt member')
        expected[name] = entry
    if {p.name for p in directory.iterdir()} != set(expected):
        raise ValueError('Original directory members differ: ' + str(directory))
    for name, entry in expected.items():
        path = directory / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('Expected original regular file: ' + str(path))
        data = path.read_bytes()
        if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('Original file digest differs: ' + str(path))


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--runtime', type=Path, required=True)
parser.add_argument('--receipt', type=Path, required=True)
args = parser.parse_args()
if os.geteuid() != 0 or Path('/etc/xr-rootfs-id').read_text().strip() != 'vr700-openkylin-3.0-arm64':
    parser.error('Run only as root inside the installed VR700 system')
if b'iqiyi,vr700' not in Path('/proc/device-tree/compatible').read_bytes().split(b'\0'):
    parser.error('VR700 device identity is required')
runtime = args.runtime.resolve(strict=True)
if runtime not in (Path('/usr/share/qcom/sm8250/iqiyi/vr700'),
                   Path('/var/opt/xr/vr700/session/tracking/stock-runtime/qcom')):
    parser.error('Select the installed resident or capsule runtime')
receipt = json.loads(args.receipt.read_text())
mode = receipt['sensor_runtime']
if receipt['device'] != 'vr700' or mode['mode'] != 'read-only-cached':
    parser.error('A verified VR700 cached-runtime import receipt is required')
entries = receipt['files']
registry = [e for e in entries if e['target'].startswith('sensors/registry/')]
configs = [e for e in entries if e['target'].startswith('sensors/config.vendor-original/')]
if len(registry) != mode['registry_file_count'] or len(configs) != mode['vendor_config_count']:
    parser.error('Receipt does not contain the complete original inputs')
verify_directory(runtime / 'sensors/registry', registry, 'sensors/registry/')
alias = runtime / 'dsp/slpi'
if (alias.exists() or alias.is_symlink()) and (not alias.is_symlink() or alias.readlink() != Path('sdsp')):
    parser.error('Unexpected existing SLPI runtime alias')
if not (runtime / 'dsp/sdsp').is_dir():
    parser.error('Install the captured SDSP runtime files before migrating')
config = runtime / 'sensors/config'
archive = runtime / 'sensors/config.vendor-original'
if archive.exists() or archive.is_symlink():
    verify_directory(archive, configs, 'sensors/config.vendor-original/')
    if config.is_symlink() or (config.exists() and (not config.is_dir() or any(config.iterdir()))):
        parser.error('An archive already exists; refusing to replace populated config')
else:
    verify_directory(config, configs, 'sensors/config.vendor-original/')
    config.rename(archive)
config.mkdir(mode=0o755, exist_ok=True)
config.chmod(0o755)
if not alias.is_symlink():
    alias.symlink_to('sdsp', target_is_directory=True)
for entry in configs:
    path = archive / Path(entry['target']).name
    os.utime(path, ns=(entry['mtime'] * 1000000000,) * 2)
metadata = runtime / 'sensors/runtime-mode.json'
metadata.write_text(json.dumps(mode, indent=2) + '\n')
metadata.chmod(0o644)
print(json.dumps(dict(runtime=str(runtime), mode=mode['mode'],
                      registry_unchanged=True, config_exposed_empty=True,
                      services_changed=False)))
