#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate an inactive VR700 real-input session from explicit private resources."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys


def source_module(root, commit, relative, name):
    head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if head != commit or len(commit) != 40:
        raise ValueError('Select the exact component commit: ' + str(root))
    subprocess.run(['git', '-C', str(root), 'diff-index', '--quiet', 'HEAD', '--'], check=True)
    spec = importlib.util.spec_from_file_location(name, root / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-input', type=Path, required=True)
    parser.add_argument('--calibration', type=Path, required=True)
    parser.add_argument('--calibration-sha256', required=True)
    parser.add_argument('--config6', type=Path, required=True)
    parser.add_argument('--config6-sha256', required=True)
    parser.add_argument('--session-source', type=Path, required=True)
    parser.add_argument('--session-commit', required=True)
    parser.add_argument('--hand-source', type=Path, required=True)
    parser.add_argument('--hand-commit', required=True)
    parser.add_argument('--hand-assets', type=Path,
                        help='Optional existing original-weight assets.lock.json directory to validate')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Choose a new output directory; this tool never updates an installed system')
    resources = json.loads(args.private_input.read_text())
    if resources.get('device') != 'vr700':
        parser.error('Private resources must explicitly identify VR700')
    device_api = source_module(args.session_source, args.session_commit,
                               'src/device_profile.py', 'vr700_device_profile')
    camera_api = source_module(args.hand_source, args.hand_commit,
                               'backends/quest/camera.py', 'vr700_camera_calibration')
    payload = args.calibration.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != args.calibration_sha256:
        parser.error('Private VR700 calibration digest mismatch')
    config6 = args.config6.read_bytes()
    config_digest = hashlib.sha256(config6).hexdigest()
    if config_digest != args.config6_sha256:
        parser.error('VR700 stock head configuration digest mismatch')
    calibration = camera_api.Calibration.load(args.calibration, rig_convention='rig-to-camera')
    if len(calibration.cameras) != 4:
        parser.error('Expected the four actual VR700 camera calibrations')
    prefix = resources['prefix']
    if not device_api.ordinary_path(prefix, '/opt/') or 'vr700' not in Path(prefix).parts:
        parser.error('Use a private /opt/.../vr700/... asset prefix')
    rig = resources['camera_rig']
    transport = resources['controller_transport']
    controller = resources['controller_plan']
    if (controller.get('format') != 'xr-controller-session-plan-v1' or
            controller.get('transport') != transport or
            not controller.get('input_socket', '').startswith('/run/xr-vr700-controller-input-') or
            controller.get('camera_env', {}).get('A081_CONTROLLER_INPUT_SOCKET') != controller.get('input_socket')):
        parser.error('Explicit matching VR700 UART controller plan required')
    radio = controller.get('radio_argv', [])
    if not radio or radio[0] != '/usr/bin/xr-controller-uart':
        parser.error('Select the installed VR700 UART helper')
    for flag, field in (('--device', 'device'), ('--baud', 'baud')):
        if (radio.count(flag) != 1 or radio.index(flag) + 1 >= len(radio) or
                radio[radio.index(flag) + 1] != str(transport.get(field))):
            parser.error('UART argv disagrees with transport selection')
    if rig.get('synchronization') == 'free-running' and (
            controller['camera_env'].get('A081_QVR_STARTUP_AE') or
            controller['camera_env'].get('A081_CONTROLLER_EXPOSURE_PROFILE') == 'kernel-three-phase'):
        parser.error('Free-running capture cannot use the MIX external-FSIN AE/three-phase protocol')
    hand = dict(resources['hand_tracking'])
    hand.update(schema=1, backend='quest-dsp',
                calibration=prefix + '/tracking/input-config/calibration.xml',
                rpc_daemon='/usr/bin/xr-hexagonrpcd',
                dsp_client='/usr/lib/aarch64-linux-gnu/xr/hand-tracking/libxr-quest-hand-client.so',
                camera_socket='/run/xr-hand-tracking/camera/input.sock',
                state_socket='/run/xr-hand-tracking/state.sock',
                log_directory='/var/log/xr-hand-tracking')
    for key in ('assets', 'runtime_root'):
        if not device_api.ordinary_path(hand.get(key)) or 'a081' in Path(hand[key]).parts:
            parser.error('Hand resources must be explicitly imported without MIX fallback')
    if 'vr700' not in Path(hand['runtime_root']).parts:
        parser.error('Hand DSP runtime must use a VR700 asset namespace')
    if type(hand.get('vtcm_bytes')) is not int or hand['vtcm_bytes'] <= 0:
        parser.error('Select the explicit DSP VTCM budget')
    if args.hand_assets:
        service_api = source_module(args.hand_source, args.hand_commit,
                                    'src/xr_hand/service.py', 'vr700_hand_assets')
        service_api.verified_assets(args.hand_assets)
    profile = dict(format='qiyu-vr-session-profile-v1', id='vr700-openkylin-xr',
        user='xr', uid=1000, gid=1000, home='/home/xr',
        rootfs_id='vr700-openkylin-3.0-arm64', prefix=prefix,
        runtime_directory='/run/xr-vr700-session', unit='xr-vr700.service',
        tracking_unit='xr-vr700-tracking.service', desktop_unit='lightdm.service',
        viewer_unit='', sensor_consumers=['iio-sensor-proxy.service'],
        utilities='/usr/lib/xr/session-manager/utilities',
        head_tracking_plugin='/usr/lib/aarch64-linux-gnu/xr/head-tracking/liba081-qvr-client-live-stream.so',
        controller_plan='/etc/xr/vr700-controller.json', controller_transport=transport,
        head_tracking=dict(config=prefix + '/tracking/config6.xml',
            calibration=prefix + '/tracking/input-config/calibration.xml', cvp_mode='stock',
            config_sha256=config_digest, calibration_sha256=digest),
        hand_tracking=dict(enabled=True, unit='xr-hand-tracking.service',
                           camera_socket=hand['camera_socket'], state_socket=hand['state_socket']),
        device=dict(id='vr700', compatible='iqiyi,vr700', rootfs_marker='/etc/xr-rootfs-id',
                    kernel_releases=resources['kernel_releases'],
                    firmware_root='/usr/lib/firmware/xr/vr700', camera_rig=rig),
        runtime_environment={})
    for key in ('desktop_owner', 'sdsp_listener', 'steamvr', 'steamvr_settings',
                'system_icd', 'kms_icd', 'runtime_library_paths', 'controller_models_directory'):
        profile[key] = resources[key]
    profile['scene'] = dict(mode='command', wait_for_first_tracking_packet=True,
        argv=['/usr/bin/xr-shell-session', '--prefix', '/usr'], working_directory='/home/xr',
        environment={'XR_RUNTIME_JSON': profile['steamvr'] + '/steamxr_linuxarm64.json',
                     'DISABLE_GAMESCOPE_WSI': '1', 'DISABLE_VULKAN_FDM_INJECTION_LAYER': '1'})
    device_api.validate_device(profile)
    args.output.mkdir(parents=True)
    root = args.output / 'root'
    def write(path, contents, mode=0o644):
        target = root / Path(path).relative_to('/')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(contents)
        target.chmod(mode)
    for name, obj in (('vr700-session', profile), ('vr700-controller', controller), ('hand-tracking', hand)):
        write('/etc/xr/' + name + '.json', (json.dumps(obj, indent=2) + '\n').encode())
    write(hand['calibration'], payload, 0o600)
    write(profile['head_tracking']['config'], config6, 0o600)
    write(profile['steamvr_settings'], (json.dumps({
        'steamvr': {'forcedDriver': 'monado', 'requireHmd': True,
                    'activateMultipleDrivers': False, 'enableHomeApp': False,
                    'motionSmoothing': False},
        'driver_monado': {'enable': True}, 'driver_cv': {'enable': False},
        'driver_deckard': {'enable': False}, 'driver_frame_hmd': {'enable': False},
        'driver_frame_controller': {'enable': False}
    }, indent=2) + '\n').encode())
    if args.hand_assets:
        shutil.copytree(args.hand_assets, root / Path(hand['assets']).relative_to('/'))
    receipt = dict(schema=1, device='vr700', tracking='physical-input-only',
        session_commit=args.session_commit, hand_commit=args.hand_commit,
        calibration_sha256=digest, config6_sha256=config_digest, calibration_camera_count=4,
        original_hand_assets_checked=bool(args.hand_assets),
        camera_synchronization=rig['synchronization'],
        shared_camera_owner='head producer; hand and controller consumers subscribe',
        controller_transport=transport, services_started=False,
        hardware_tracking_validated=False, physical_wearer_validated=False)
    (args.output / 'manifest.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
