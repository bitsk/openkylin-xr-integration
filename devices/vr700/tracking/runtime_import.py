"""Pinned VR700 OEM runtime import shared by both offline preparers."""
import hashlib
import json
from pathlib import Path


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
    for alias, target in lock['aliases'].items():
        (output / alias).symlink_to(target, target_is_directory=True)
    for path in [output, *output.rglob('*')]:
        if not path.is_symlink() and path.is_dir():
            path.chmod(0o755)
    return dict(device=lock['device'], files=lock['files'], aliases=lock['aliases'],
                dsp_resident_dependencies=lock['dsp_resident_dependencies'],
                hardware_validated=False, sensor_registry_contents_imported=False)
