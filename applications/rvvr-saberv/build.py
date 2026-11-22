#!/usr/bin/env python3
"""Build SaberV from locked upstream Git and the locked runtime engine recipe."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(argv, **kwargs):
    subprocess.run([str(v) for v in argv], check=True, **kwargs)


def main():
    # Package permissions must not inherit a group-writable build-host umask.
    # The privileged session owner accepts only root-controlled descriptors.
    os.umask(0o022)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--packages', type=Path, required=True)
    parser.add_argument('--sources', type=Path, required=True)
    args = parser.parse_args()
    recipe = Path(__file__).resolve().parent
    lock = json.loads((recipe / 'upstream.json').read_text())
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    packages = args.packages.resolve()
    packages.mkdir(parents=True, exist_ok=True)
    editor = Path(os.environ['XR_SABERV_EDITOR']).resolve()
    if sha(editor) != lock['editor_sha256']:
        raise ValueError('Editor differs from the source lock')
    projects = {}
    for key, cache_key in [('repository', 'XR_SABERV_SOURCE_CACHE'),
                           ('sample_repository', 'XR_SABERV_SONG_CACHE')]:
        source = output / key
        if not source.exists():
            run(['git', 'clone', '--no-checkout', os.environ.get(cache_key, lock[key]), source])
        commit = lock['commit' if key == 'repository' else 'sample_commit']
        run(['git', '-C', source, 'checkout', '--detach', commit])
        projects[key] = source
    project = projects['repository']
    run(['git', '-C', project, 'reset', '--hard', lock['commit']])
    run(['git', '-C', project, 'apply', recipe / 'application.patch'])
    # Import only ARM64 texture formats; a host editor needs no desktop copy.
    p = project / 'project.godot'
    text = p.read_text()
    if 'textures/vram_compression/import_s3tc_bptc=false' not in text:
        text = text.replace('textures/vram_compression/import_etc2_astc=true',
                            'textures/vram_compression/import_etc2_astc=true\n'
                            'textures/vram_compression/import_s3tc_bptc=false')
        p.write_text(text)
    engine = output / 'engine'
    if not (engine / 'root/godot-native').is_file() and os.environ.get('XR_GODOT_ENGINE_CACHE'):
        # Reuse only a checksummed result of this same locked engine recipe.
        cache = Path(os.environ['XR_GODOT_ENGINE_CACHE'])
        saved = json.loads((cache / 'build-manifest.json').read_text())
        current = json.loads((args.sources / 'xr-monado/compat/native-interop/godot-engine/upstream.json').read_text())
        if (saved['upstream'] != current['commit'] or saved['patches'] != current['patches'] or
                saved['archive_sha256'] != current['archive_sha256'] or
                sha(cache / 'godot-native') != saved['binary_sha256']):
            raise ValueError('Cached engine does not match the selected source recipe')
        shutil.copytree(cache, engine / 'root')
    if not (engine / 'root/godot-native').is_file():
        argv = [sys.executable, args.sources / 'xr-monado/compat/native-interop/godot-engine/build.py',
                '--archive', os.environ['XR_GODOT_ARCHIVE'], '--output', engine,
                '--jobs', os.environ.get('XR_BUILD_JOBS', '12')]
        if os.environ.get('XR_GODOT_TARGET_LIBM'):
            argv += ['--target-libm', os.environ['XR_GODOT_TARGET_LIBM']]
        run(argv)
    engine_manifest = json.loads((engine / 'root/build-manifest.json').read_text())
    engine_lock = json.loads((args.sources / 'xr-monado/compat/native-interop/godot-engine/upstream.json').read_text())
    if (engine_manifest['upstream'] != engine_lock['commit'] or
            sha(engine / 'root/godot-native') != engine_manifest['binary_sha256']):
        raise ValueError('Engine output differs from its locked recipe')
    env = dict(os.environ)
    for name in ('DATA', 'CACHE', 'CONFIG'):
        path = output / 'xdg' / name.lower()
        path.mkdir(parents=True, exist_ok=True)
        env['XDG_' + name + '_HOME'] = str(path)
    run([editor, '--headless', '--editor', '--path', project, '--import'], env=env)
    pack = output / 'SaberV.pck'
    run([editor, '--headless', '--path', project, '--export-pack',
         'MIX openKylin ARM64', pack], env=env)
    root = output / 'root'
    if root.exists():
        shutil.rmtree(root)

    def install(src, destination, mode=0o644):
        target = root / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
        target.chmod(mode)

    install(pack, 'usr/share/rvvr-saberv/SaberV.pck')
    install(engine / 'root/godot-native', 'usr/lib/rvvr-saberv/godot-native', 0o755)
    (root / 'usr/lib/rvvr-saberv/godot-native.pck').symlink_to('../../share/rvvr-saberv/SaberV.pck')
    install(recipe / 'launch.py', 'usr/lib/rvvr-saberv/launch.py', 0o755)
    install(project / 'arts/ok_logo.png', 'usr/share/pixmaps/rvvr-saberv.png')
    install(project / 'LICENSE', 'usr/share/doc/rvvr-saberv/LICENSE')
    for name in ('LICENSE.txt', 'COPYRIGHT.txt', 'build-manifest.json'):
        install(engine / 'root' / name, 'usr/share/doc/rvvr-saberv/godot-' + name)
    for name, expected in lock['sample_files'].items():
        source = projects['sample_repository'] / 'TheFatRat_Timelapse' / name
        if sha(source) != expected:
            raise ValueError('Sample file differs from the source lock: ' + name)
        install(source, 'usr/share/rvvr-saberv/songs/TheFatRat_Timelapse/' + name)
    entry = root / 'usr/bin/rvvr-saberv'
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text('#!/bin/sh\nexec /usr/bin/xr-shell-session --launch-application rvvr-saberv\n')
    entry.chmod(0o755)
    definition = root / 'usr/share/xr/applications/rvvr-saberv.json'
    definition.parent.mkdir(parents=True, exist_ok=True)
    definition.write_text(json.dumps({'schema': 1, 'argv': ['/usr/lib/rvvr-saberv/launch.py']}) + '\n')
    desktop = root / 'usr/share/applications/rvvr-saberv.desktop'
    desktop.parent.mkdir(parents=True, exist_ok=True)
    desktop.write_text('[Desktop Entry]\nType=Application\nName=RVVR SaberV\n'
                       'Name[zh_CN]=SaberV 节奏光剑\nExec=rvvr-saberv\n'
                       'Icon=rvvr-saberv\nCategories=Game;\nX-XR-Immersive=true\nTerminal=false\n')
    control = root / 'DEBIAN/control'
    control.parent.mkdir(parents=True)
    control.write_text('Package: rvvr-saberv\nVersion: 0.0.1-ok1+mix10\nArchitecture: arm64\n'
                       'Maintainer: openKylin XR SIG <xr@lists.openkylin.top>\n'
                       'Depends: python3, xr-shell-session (>= 0.2.9), xr-session-manager (>= 0.3.22), '
                       'libc6 (>= 2.38), libstdc++6, libgcc-s1, libvulkan1, libx11-6\n'
                       'Description: OpenXR SaberV rhythm game for MIX openKylin\n')
    manifest = {'upstream': lock, 'patch_sha256': sha(recipe / 'application.patch'),
                'component_commit': subprocess.check_output(
                    ['git', '-C', recipe, 'rev-parse', 'HEAD'], text=True).strip(),
                'engine': json.loads((engine / 'root/build-manifest.json').read_text()),
                'pack_sha256': sha(pack), 'device_validated': False}
    (root / 'usr/share/doc/rvvr-saberv/source-lock.json').write_text(json.dumps(manifest, indent=2) + '\n')
    run(['dpkg-deb', '--root-owner-group', '-Zxz', '-z3', '--build', root,
         packages / 'rvvr-saberv_0.0.1-ok1+mix10_arm64.deb'])


if __name__ == '__main__':
    main()
