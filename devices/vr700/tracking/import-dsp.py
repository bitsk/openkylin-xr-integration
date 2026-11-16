#!/usr/bin/env python3
"""Import the captured VR700 DSP runtimes and RFSA libraries offline."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil


def main():
    os.umask(0o022)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True,
                        help='New qcom/dsp directory; creates sdsp and slpi -> sdsp')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output must be new')
    manifest = json.loads(args.manifest.read_text())
    sources = [(p, domain) for domain in ('sdsp', 'cdsp')
               for p in sorted((args.stock / ('vendor/dsp/' + domain)).iterdir())]
    rfsa = args.stock / 'system/lib/rfsa/adsp'
    sources += [(rfsa / name, domain) for domain, names in {
        'sdsp': ('libsns_low_lat_stream_skel.so', 'libsns_device_mode_skel.so'),
        'cdsp': ('libqvr_dsp_driver_skel.so', 'libqvr_cam_dsp_driver_skel.so',
                 'libqvr_3dof_tracker_skel.so', 'libtracker_6dof_skel_8250.so',
                 'libdsp_streamer_qvrcam_receiver.so',
                 'libsnpe_dsp_v66_domains_v2_skel.so', 'libcalculator_skel.so'),
    }.items() for name in names]
    sources += [(args.stock / 'vendor/lib/rfsa/adsp' / name, 'cdsp')
                for name in ('libcvpdsp_skel.so', 'libfastcvadsp.so', 'libdspCV_skel.so')]
    if not any(p.name == 'fastrpc_shell_2' and domain == 'sdsp' for p, domain in sources):
        parser.error('Original SLPI shell is missing')
    checked = []
    for source, domain in sources:
        relative = source.relative_to(args.stock).as_posix()
        if source.is_symlink() or not source.is_file():
            parser.error('Only original regular files are accepted: ' + relative)
        data = source.read_bytes()
        expected = manifest[relative]
        digest = hashlib.sha256(data).hexdigest()
        if len(data) != expected['bytes'] or digest != expected['sha256']:
            parser.error('Capture manifest mismatch: ' + relative)
        checked.append(dict(source=relative, target=domain + '/' + source.name,
                            bytes=len(data), sha256=digest))
    for domain in ('sdsp', 'cdsp'):
        target = args.output / domain
        target.mkdir(parents=True)
        target.chmod(0o755)
    args.output.chmod(0o755)
    for source, domain in sources:
        target = args.output / domain
        shutil.copyfile(source, target / source.name)
        (target / source.name).chmod(0o644)
    (args.output / 'slpi').symlink_to('sdsp', target_is_directory=True)
    print(json.dumps(dict(files=checked, alias={'slpi': 'sdsp'},
                          source_device='vr700', hardware_validated=False), indent=2))


if __name__ == '__main__':
    main()
