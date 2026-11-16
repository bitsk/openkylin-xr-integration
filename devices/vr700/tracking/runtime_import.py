"""Pinned VR700 OEM runtime import shared by both offline preparers."""
import hashlib
import json
import os
from pathlib import Path


def captured_bytes(stock, capture, relative):
    source = Path(stock) / relative
    expected = capture.get(relative)
    if source.is_symlink() or not source.is_file() or not expected:
        raise ValueError('Missing captured regular sensor input: ' + relative)
    data = source.read_bytes()
    if len(data) != expected['bytes'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
        raise ValueError('Captured sensor input digest mismatch: ' + relative)
    return data


def validate_runtime(stock, manifest_path):
    lock = json.loads(Path(__file__).with_name('runtime-files.json').read_text())
    capture = json.loads(Path(manifest_path).read_text())
    checked = []
    for entry in lock['files']:
        source = Path(stock) / entry['source']
        if source.is_symlink() or not source.is_file():
            raise ValueError('Missing original regular runtime input: ' + entry['source'])
        original = capture.get(entry['source'])
        if not original or any(original.get(key) != entry[key] for key in ('bytes', 'sha256')):
            raise ValueError('Capture manifest differs from required VR700 input: ' + entry['source'])
        data = source.read_bytes()
        if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('VR700 runtime input digest mismatch: ' + entry['source'])
        checked.append((entry, data))
    # The DSP caches configuration mtimes in the original persistent registry.
    # Host extraction times would falsely request registry regeneration/writes.
    registry = 'mnt/vendor/persist/sensors/registry/registry'
    config = 'vendor/etc/sensors/config'
    cache_path = registry + '/sns_reg_config'
    cache = json.loads(captured_bytes(stock, capture, cache_path))['sns_reg_config']
    configs = sorted((Path(stock) / config).iterdir())
    expected_paths = {'/' + config + '/' + path.name for path in configs}
    if set(cache) - {'owner'} != expected_paths:
        raise ValueError('Original registry cache must cover exactly the captured vendor configurations')
    private_entries = []

    def add(relative, target, mtime=None):
        data = captured_bytes(stock, capture, relative)
        entry = dict(source=relative, target=target, bytes=len(data),
                     sha256=hashlib.sha256(data).hexdigest())
        if mtime is not None:
            entry.update(mtime=mtime, mtime_source=cache_path)
        checked.append((entry, data))
        private_entries.append(entry)

    for path in configs:
        record = cache['/' + config + '/' + path.name]
        value = record.get('data')
        if record.get('type') != 'int' or not isinstance(value, str) or not value.isdecimal():
            raise ValueError('Original registry cache has an invalid config mtime: ' + path.name)
        add(config + '/' + path.name, 'sensors/config/' + path.name, int(value))
    for path in sorted((Path(stock) / registry).iterdir()):
        add(registry + '/' + path.name, 'sensors/registry/' + path.name)
    add('vendor/etc/sensors/sns_reg_config', 'sensors/sns_reg.conf')
    lock['private_sensor_files'] = private_entries
    return lock, checked


def write_runtime(output, lock, checked):
    output = Path(output)
    if output.exists():
        raise ValueError('Runtime output must be new: ' + str(output))
    output.mkdir(parents=True)
    for entry, data in checked:
        target = output / entry['target']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        target.chmod(0o644)
        if 'mtime' in entry:
            os.utime(target, ns=(entry['mtime'] * 1000000000,) * 2)
    for alias, target in lock['aliases'].items():
        (output / alias).symlink_to(target, target_is_directory=True)
    for path in [output, *output.rglob('*')]:
        if not path.is_symlink() and path.is_dir():
            path.chmod(0o755)
    return dict(device=lock['device'], files=lock['files'] + lock['private_sensor_files'], aliases=lock['aliases'],
                dsp_resident_dependencies=lock['dsp_resident_dependencies'],
                hardware_validated=False, sensor_registry_contents_imported=True)
