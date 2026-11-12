#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a pinned native gpiod wheel and Deb without installing pip or opening GPIO."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import stat
import subprocess
import sys
import sysconfig
import tarfile
import urllib.request
import zipfile


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise RuntimeError('Unsafe archive path: ' + name)
    return Path(*path.parts)


def unzip(archive, destination, *, package=None):
    with zipfile.ZipFile(archive) as stream:
        for information in stream.infolist():
            name = relative(information.filename)
            if package and name.parts[0] not in (package, package + '-' + VERSION + '.dist-info'):
                raise RuntimeError('Unexpected wheel installation path: ' + str(name))
            if stat.S_ISLNK(information.external_attr >> 16):
                raise RuntimeError('Symlinks are not accepted in a build wheel')
            path = destination / name
            if information.is_dir():
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.exists():
                    raise RuntimeError('Build wheel path collision: ' + str(name))
                path.write_bytes(stream.read(information))
                path.chmod(0o755 if information.external_attr >> 16 & 0o111 else 0o644)


RECIPE = Path(__file__).resolve().parent
LOCK = json.loads((RECIPE / 'source.lock.json').read_text())
VERSION = LOCK['version']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--download-only', action='store_true', help='Explicitly fetch the locked official input files only')
    args = parser.parse_args()
    cache = args.cache.resolve()
    cache.mkdir(parents=True, exist_ok=True)
    inputs = [LOCK['source'], *LOCK['build_tools']]
    for entry in inputs:
        path = cache / entry['filename']
        if args.download_only and not path.exists():
            if not entry['url'].startswith('https://files.pythonhosted.org/'):
                parser.error('Only official locked PyPI distribution URLs are accepted')
            with urllib.request.urlopen(entry['url']) as response:
                path.write_bytes(response.read())
        if not path.is_file() or path.is_symlink() or sha256(path) != entry['sha256']:
            parser.error('Missing or mismatched locked input: ' + entry['filename'])
    if args.download_only:
        print(json.dumps({'downloaded_inputs': len(inputs), 'build_started': False}))
        return
    if not args.output:
        parser.error('--output is required for a build')
    if sys.version_info[:2] != (3, 12) or platform.machine() != 'aarch64':
        parser.error('Use native ARM64 CPython 3.12; no cross build or host wheel is substituted')
    if not (Path(sysconfig.get_path('include')) / 'Python.h').is_file():
        parser.error('Install native libpython3.12-dev headers before building')
    output = args.output.resolve()
    if output.exists():
        parser.error('Choose a new output directory to preserve previous build evidence')
    output.mkdir(parents=True)
    tools = output / 'build-tools'
    tools.mkdir()
    for entry in LOCK['build_tools']:
        unzip(cache / entry['filename'], tools)
    source_parent = output / 'source'
    source_parent.mkdir()
    with tarfile.open(cache / LOCK['source']['filename'], 'r:gz') as archive:
        for information in archive.getmembers():
            name = relative(information.name)
            if name.parts[0] != 'gpiod-' + VERSION or not (information.isfile() or information.isdir()):
                raise RuntimeError('Unexpected source archive entry')
            path = source_parent / name
            if information.isdir():
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(information) as stream:
                    path.write_bytes(stream.read())
                path.chmod(0o755 if information.mode & 0o111 else 0o644)
    source = source_parent / ('gpiod-' + VERSION)
    if (source / 'libgpiod-version.txt').read_text().strip() != LOCK['vendored_libgpiod']:
        raise RuntimeError('The pinned source lacks the expected bundled C library')
    if not (source / 'lib/chip.c').is_file() or not (source / 'include/gpiod.h').is_file():
        raise RuntimeError('The source distribution is missing its bundled C sources')
    environment = dict(os.environ)
    for name in ('LIBGPIOD_VERSION', 'LINK_SYSTEM_LIBGPIOD', 'PYTHONHOME'):
        environment.pop(name, None)
    environment.update(PYTHONPATH=str(tools), PYTHONNOUSERSITE='1',
                       PYTHONPYCACHEPREFIX=str(output / 'pycache'), SETUPTOOLS_USE_DISTUTILS='local')
    environment['CFLAGS'] = environment.get('CFLAGS', '') + ' -ffile-prefix-map=' + str(output) + '=. -fdebug-prefix-map=' + str(output) + '=.'
    wheels = output / 'wheels'
    command = [sys.executable, '-S', 'setup.py', 'bdist_wheel', '--dist-dir', str(wheels)]
    with (output / 'build.log').open('w') as log:
        subprocess.run(command, cwd=source, env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
    candidates = list(wheels.glob('gpiod-' + VERSION + '-cp312-cp312-linux_aarch64.whl'))
    if len(candidates) != 1:
        raise RuntimeError('Expected exactly one native ARM64 CPython 3.12 wheel')
    wheel = candidates[0]
    staging = output / 'deb-root'
    packages = staging / 'usr/lib/python3/dist-packages'
    packages.mkdir(parents=True)
    unzip(wheel, packages, package='gpiod')
    extensions = list((packages / 'gpiod').glob('_ext*.so'))
    if len(extensions) != 1 or int.from_bytes(extensions[0].read_bytes()[18:20], 'little') != 183:
        raise RuntimeError('The extension is not one AArch64 ELF')
    dynamic = subprocess.check_output(['readelf', '--dynamic', str(extensions[0])], text=True)
    needed = re.findall(r'\(NEEDED\).*\[([^]]+)\]', dynamic)
    if any('gpiod' in library.lower() for library in needed):
        raise RuntimeError('The extension unexpectedly links system libgpiod')
    versions = subprocess.check_output(['readelf', '--version-info', str(extensions[0])], text=True)
    glibc = max(re.findall(r'GLIBC_([0-9.]+)', versions), key=lambda version: tuple(map(int, version.split('.'))))
    check = "import sys; sys.path.insert(0, sys.argv[1]); import gpiod; from gpiod.line import Direction, Value; assert callable(gpiod.request_lines) and callable(gpiod.LineSettings); assert gpiod.__version__ == sys.argv[2]; print(gpiod.__version__)"
    api = subprocess.check_output([sys.executable, '-S', '-c', check, str(packages), VERSION], env=environment, text=True).strip()
    control = staging / 'DEBIAN'
    control.mkdir()
    (control / 'control').write_text(
        'Package: python3-gpiod\nVersion: ' + VERSION + '-0qiyu1\nArchitecture: arm64\n'
        'Maintainer: Qiyu rootfs maintainers\nSection: python\nPriority: optional\n'
        'Depends: python3.12, libc6 (>= ' + glibc + ')\n'
        'Conflicts: python3-libgpiod\n'
        'Description: Official gpiod v2 Python bindings for native A081 development\n'
        ' Bundles the pinned libgpiod C sources inside the Python extension.\n'
        ' No system libgpiod or pip installation is required.\n')
    documentation = staging / 'usr/share/doc/python3-gpiod'
    documentation.mkdir(parents=True)
    (documentation / 'copyright').write_text(
        'Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/\n'
        'Upstream-Name: gpiod\nSource: https://pypi.org/project/gpiod/' + VERSION + '/\n\n'
        'Files: *\nCopyright: Upstream libgpiod contributors; see original source SPDX headers\n'
        'License: LGPL-2.1-or-later\n'
        ' The complete LGPL version 2.1 text is available in\n'
        ' /usr/share/common-licenses/LGPL-2.1 on Debian-family systems.\n')
    (documentation / 'source.lock.json').write_bytes((RECIPE / 'source.lock.json').read_bytes())
    shutil.copyfile(source / 'README.md', documentation / 'upstream-README.md')
    artifact = output / ('python3-gpiod_' + VERSION + '-0qiyu1_arm64.deb')
    subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(staging), str(artifact)], check=True)
    receipt = {'source_lock_sha256': sha256(RECIPE / 'source.lock.json'), 'source_sha256': LOCK['source']['sha256'],
               'build_tools': {entry['filename']: entry['sha256'] for entry in LOCK['build_tools']},
               'python': sys.version, 'machine': platform.machine(), 'vendored_libgpiod': LOCK['vendored_libgpiod'],
               'api_import_version': api, 'elf_needed': needed, 'minimum_glibc': glibc,
               'artifacts': {path.name: sha256(path) for path in (wheel, artifact)},
               'system_pip_used': False, 'network_used_for_build': False, 'gpio_opened': False,
               'installed': False, 'hardware_validated': False}
    (output / 'build-manifest.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
