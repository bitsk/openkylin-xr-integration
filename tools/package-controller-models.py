#!/usr/bin/env python3
"""Package checksum-locked stock controller resources for an installed system."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess

VERSION = '0.1.2'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_anchors(path, manifest):
    anchors = json.loads(path.read_text())
    require(anchors.get('schema') == 1 and anchors.get('device') == 'a081',
            'Unsupported A081 controller anchor schema')
    require(anchors.get('hands') == ['left', 'right'], 'Anchors must describe both hands')
    source = anchors.get('source', {})
    require(source.get('apk_sha256') == manifest['source']['sha256'],
            'Controller anchors and model extraction must use the same source APK SHA-256')
    require(isinstance(source.get('scene_id'), str) and source['scene_id'],
            'Controller anchors need a serialized source scene ID')
    require(anchors.get('coordinates', {}).get('unit') == 'meters'
            and anchors['coordinates'].get('rotation_unit') == 'degrees',
            'Controller anchors must use meters and rotate_xyz degrees')
    require(anchors.get('validation', {}).get('serialized_parameters_verified') is True,
            'Controller anchors need verified serialized parameters')
    components = anchors.get('component_anchors', {})
    required = {'body', 'openxr_grip', 'openxr_aim', 'tip', 'handgrip'}
    require(set(components) == required, 'Missing or unsupported controller components')
    transforms = anchors.get('anchors', {})
    for component, reference in components.items():
        require(reference in transforms, f'Unknown anchor for {component}')
        transform = transforms[reference]
        for field in ['origin', 'rotate_xyz']:
            vector = transform.get(field)
            require(isinstance(vector, list) and len(vector) == 3
                    and all(type(v) in (int, float) and math.isfinite(v) for v in vector),
                    f'Invalid {field} for controller anchor {reference}')
    return anchors


def steamvr_model(anchors):
    components = {}
    for component, reference in anchors['component_anchors'].items():
        transform = anchors['anchors'][reference]
        components[component] = {'component_local': {
            'origin': transform['origin'], 'rotate_xyz': transform['rotate_xyz']}}
    components['body']['filename'] = 'controller.obj'
    return {'components': components}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--anchors', type=Path, required=True,
                        help='qiyu-vr-runtime devices/a081/controller-anchors.json')
    parser.add_argument('--variant', choices=['qiyi3s', 'qiyi3'], default='qiyi3s')
    args = parser.parse_args()
    assets = args.assets.resolve()
    manifest = json.loads((assets / 'manifest.json').read_text())
    require(manifest['schema'] == 1, 'Unsupported controller extraction schema')
    anchors = read_anchors(args.anchors, manifest)
    selected = [m for m in manifest['models'] if m['variant'] == args.variant]
    require(sorted(m['hand'] for m in selected) == ['left', 'right'],
            'Extraction must contain exactly one model per hand')
    sources = {}
    required_files = {'mesh.json', 'texture.png', 'controller.glb', 'parts.json',
                      'controller.obj', 'controller.mtl'}
    for model in selected:
        files = {}
        for entry in model['files']:
            relative = Path(entry['path'])
            require(not relative.is_absolute() and '..' not in relative.parts,
                    'Controller resource path must stay inside the extraction')
            original = assets / relative
            require(original.is_file() and not original.is_symlink(),
                    f'Missing or symlink controller resource: {relative}')
            require(sha(original) == entry['sha256']
                    and original.stat().st_size == entry['bytes'],
                    f'Controller resource checksum mismatch: {relative}')
            require(original.name not in files, f'Duplicate controller resource: {relative}')
            files[original.name] = original
        require(required_files <= files.keys(), f'Incomplete {model["hand"]} model resources')
        sources[model['hand']] = files
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    stage = output / 'xr-device-a081-controller-models'
    stage.mkdir(exist_ok=False)
    target = stage / 'usr/share/xr/devices/a081/controllers'
    target.mkdir(parents=True)
    records = []

    def record(destination):
        destination.chmod(0o644)
        records.append({'path': str(destination.relative_to(stage)),
                        'sha256': sha(destination), 'bytes': destination.stat().st_size})

    for model in selected:
        hand = model['hand']
        for name in ['mesh.json', 'texture.png', 'controller.glb', 'parts.json']:
            destination = target / hand / name
            destination.parent.mkdir(exist_ok=True)
            shutil.copyfile(sources[hand][name], destination)
            record(destination)
        name = f'a081_controller_{hand}'
        rendermodel = target / 'steamvr/rendermodels' / name
        rendermodel.mkdir(parents=True)
        for filename in ['controller.obj', 'controller.mtl', 'texture.png']:
            destination = rendermodel / filename
            shutil.copyfile(sources[hand][filename], destination)
            record(destination)
        destination = rendermodel / f'{name}.json'
        destination.write_text(json.dumps(steamvr_model(anchors), indent=2) + '\n')
        record(destination)
    installed_anchors = target / 'controller-anchors.json'
    shutil.copyfile(args.anchors, installed_anchors)
    record(installed_anchors)
    install_manifest = {**manifest, 'models': selected, 'installed_variant': args.variant,
                        'installation': records,
                        'controller_anchors_sha256': sha(installed_anchors),
                        'physical_grip_alignment_verified': False}
    (target / 'manifest.json').write_text(json.dumps(install_manifest, indent=2) + '\n')
    notice = stage / 'usr/share/doc/xr-device-a081-controller-models'
    notice.mkdir(parents=True)
    (notice / 'copyright').write_text(
        'Stock QiyuHome controller meshes and textures. Copyright their original authors.\n'
        'Extracted from the locally supplied system image for this device.\n'
        'No additional redistribution license is asserted.\n')
    control = stage / 'DEBIAN'
    control.mkdir()
    (control / 'control').write_text(
        f'Package: xr-device-a081-controller-models\nVersion: {VERSION}\n'
        'Architecture: all\nSection: non-free/graphics\nPriority: optional\n'
        'Maintainer: bits <bigbits@hackx.cc>\n'
        'Description: Original A081 controller models and runtime components\n'
        ' Checksum-locked meshes, textures, portable GLB files and SteamVR components.\n')
    package = output / f'xr-device-a081-controller-models_{VERSION}_all.deb'
    subprocess.run(['dpkg-deb', '--build', '--root-owner-group', str(stage), str(package)], check=True)
    receipt = {'package': package.name, 'sha256': sha(package), 'variant': args.variant,
               'source_apk_sha256': manifest['source']['sha256'], 'files': records,
               'controller_anchors_sha256': sha(installed_anchors),
               'physical_grip_alignment_verified': False, 'service_started': False}
    (output / 'models-package.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
