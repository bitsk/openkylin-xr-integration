#!/usr/bin/python3
"""Use the selected native OpenXR environment without owning device hardware."""
import os
from pathlib import Path
import shutil


def main():
    env = dict(os.environ)
    if not env.get('DISPLAY') or not Path(env.get('XR_RUNTIME_JSON', '')).is_file():
        raise RuntimeError('SaberV requires the selected native XR session')
    env['RVVR_REQUIRE_XR'] = '1'
    data = Path(env.get('XDG_DATA_HOME') or Path.home() / '.local/share') / 'rvvr-saberv'
    songs = data / 'OpenSaber/Songs'
    songs.mkdir(parents=True, exist_ok=True)
    for source in Path('/usr/share/rvvr-saberv/songs').iterdir():
        if source.is_dir() and not (songs / source.name).exists():
            shutil.copytree(source, songs / source.name)
    logs = Path(env.get('XDG_STATE_HOME') or Path.home() / '.local/state') / 'rvvr-saberv'
    logs.mkdir(parents=True, exist_ok=True)
    binary = '/usr/lib/rvvr-saberv/godot-native'
    os.execve(binary, [binary, '--rendering-method', 'mobile', '--rendering-driver', 'vulkan',
                      '--display-driver', 'x11', '--xr-mode', 'on',
                      '--log-file', str(logs / 'game.log')], env)


if __name__ == '__main__':
    main()
