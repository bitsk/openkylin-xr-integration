#!/usr/bin/env python3
"""Import the captured VR700 SLPI shell and direct IMU library offline."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True,
                        help='New qcom/dsp directory; creates sdsp and slpi -> sdsp')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output must be new')
    manifest = json.loads(args.manifest.read_text())
    sources = sorted((args.stock / 'vendor/dsp/sdsp').iterdir())
    sources.append(args.stock / 'system/lib/rfsa/adsp/libsns_low_lat_stream_skel.so')
    if not any(p.name == 'fastrpc_shell_2' for p in sources):
        parser.error('Original SLPI shell is missing')
    checked = []
    for source in sources:
        relative = source.relative_to(args.stock).as_posix()
        if source.is_symlink() or not source.is_file():
            parser.error('Only original regular files are accepted: ' + relative)
        data = source.read_bytes()
        expected = manifest[relative]
        digest = hashlib.sha256(data).hexdigest()
        if len(data) != expected['bytes'] or digest != expected['sha256']:
            parser.error('Capture manifest mismatch: ' + relative)
        checked.append(dict(source=relative, target='sdsp/' + source.name,
                            bytes=len(data), sha256=digest))
    target = args.output / 'sdsp'
    target.mkdir(parents=True)
    target.chmod(0o755)
    args.output.chmod(0o755)
    for source in sources:
        shutil.copyfile(source, target / source.name)
        (target / source.name).chmod(0o644)
    (args.output / 'slpi').symlink_to('sdsp', target_is_directory=True)
    print(json.dumps(dict(files=checked, alias={'slpi': 'sdsp'},
                          source_device='vr700', hardware_validated=False), indent=2))


if __name__ == '__main__':
    main()
