#!/usr/bin/env python3
"""Build three A081 Android launchers without Gradle or network dependencies."""
import argparse
from pathlib import Path
import subprocess
import zipfile

SOURCE = Path(__file__).resolve().parent
TARGETS = {
    'openkylin': ('openKylin', '#397DE8'),
    'steamos': ('SteamOS', '#21425B'),
    'debian': ('Debian', '#BD2854'),
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sdk', type=Path, required=True)
    p.add_argument('--build-tools', default='35.0.1')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    tools = args.sdk / 'build-tools' / args.build_tools
    android = args.sdk / 'platforms/android-29/android.jar'
    classes = output / 'classes'
    dex = output / 'dex'
    classes.mkdir(exist_ok=True)
    dex.mkdir(exist_ok=True)
    subprocess.run(['javac', '--release', '8', '-encoding', 'UTF-8', '-cp', str(android),
                    '-d', str(classes), str(SOURCE / 'src/BootActivity.java')], check=True)
    subprocess.run([str(tools / 'd8'), '--min-api', '26', '--lib', str(android),
                    '--output', str(dex), *map(str, classes.rglob('*.class'))], check=True)
    for target, (label, color) in TARGETS.items():
        work = output / target
        res = work / 'res/drawable'
        res.mkdir(parents=True, exist_ok=True)
        (res / 'icon.xml').write_text(f'''<vector xmlns:android="http://schemas.android.com/apk/res/android"
 android:width="96dp" android:height="96dp" android:viewportWidth="96" android:viewportHeight="96">
 <path android:fillColor="{color}" android:pathData="M0,0h96v96h-96z"/>
 <path android:fillColor="#FFFFFF" android:pathData="M47,19v9a22,22 0,1 0,21 21h-8a14,14 0,1 1,-13 -13v10l20,-15z"/>
</vector>''')
        version_code, version_name = (3, '1.2') if target == 'openkylin' else (2, '1.1')
        manifest = work / 'AndroidManifest.xml'
        manifest.write_text(f'''<manifest xmlns:android="http://schemas.android.com/apk/res/android"
 package="com.bits.qiyu.boot.{target}" android:versionCode="{version_code}" android:versionName="{version_name}">
 <uses-sdk android:minSdkVersion="26" android:targetSdkVersion="29"/>
 <application android:label="进入 {label}" android:icon="@drawable/icon"
 android:allowBackup="false" android:theme="@android:style/Theme.Material.NoActionBar">
 <activity android:name="com.bits.qiyu.boot.BootActivity" android:exported="true"
 android:screenOrientation="landscape">
 <intent-filter><action android:name="android.intent.action.MAIN"/>
 <category android:name="android.intent.category.LAUNCHER"/></intent-filter>
 </activity></application></manifest>''')
        compiled = work / 'resources.zip'
        apk = output / f'{target}-unsigned.apk'
        subprocess.run([str(tools / 'aapt2'), 'compile', '--dir', str(work / 'res'),
                        '-o', str(compiled)], check=True)
        subprocess.run([str(tools / 'aapt2'), 'link', '-I', str(android), '--manifest',
                        str(manifest), '-o', str(apk), str(compiled)], check=True)
        with zipfile.ZipFile(apk, 'a', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(dex / 'classes.dex', 'classes.dex')
        print(apk)


if __name__ == '__main__':
    main()
