# A081 Android system launchers

Three independent Android packages provide openKylin, SteamOS and Debian icons.
Opening an icon performs a read-only installation check; reboot requires an
explicit button and confirmation. The helper checks the locally pinned recovery
image, installed root marker and kernel modules, then writes only the one-shot
`boot/next-system` selector and clock seed in osstore. It does not flash partitions
or change `default-system`. The recovery consumes that selector on its next boot.

Build with an Android SDK containing API 29 and build-tools 35.0.1:

```sh
python3 build.py --sdk /path/to/android-sdk --output /private/build/launchers
```

The outputs are unsigned APKs. Align and sign them with a private, stable
keystore before installation. These are ordinary 2D Android activities: Qiyu
Home hosts a single confirmation page in its VR window and supplies controller
ray clicks as Android touch events. Do not add `qiyu-sdk-flag` or draw separate
eye panes: marking this non-SDK activity as a native VR application bypasses
that window input path and leaves its buttons inaccessible to the controller.
No Qiyu Home launcher action or legacy QTI category is added.

On a rooted A081 Android B installation, install `control.sh` root-owned mode
0700 at `/data/adb/qiyu-boot/control.sh`. Supply a root-owned mode 0600
`config.sh` alongside it with `RECOVERY_SHA256` and `KERNEL_RELEASE` pinned to
the locally verified recovery and matching modules. This private configuration
and signing keys do not belong in Git. Grant root only to the three installed
launcher package UIDs; do not enable global automatic root authorization.
SteamOS displays a desktop/VR validation notice unless the local configuration
explicitly sets `STEAMOS_VR_READY=1` after validating its VR startup separately.

If the ROM's Magisk `--sqlite` command crashes its daemon and the regular
authorization dialog is unavailable in VR, `root-policy.c` provides a narrow
installer fallback using Android's SQLite library directly. Build with the
NDK's `aarch64-linux-android29-clang -Wall -Wextra -Werror -O2 root-policy.c
-ldl -o root-policy`. As root, run `root-policy --inspect` first and verify the
policy schema. After checking the installed packages' signatures and distinct
UIDs, `root-policy <openkylin-uid> <steamos-uid> <debian-uid>` grants only those
three UIDs. Save its BEFORE/AFTER rows privately for rollback and remove the
temporary executable after installation. This is an A081 ROM-specific fallback,
not a general Magisk database migration tool.

Invoke the helper with `su -mm -c 'sh /data/adb/qiyu-boot/control.sh preflight debian'`
to check without writing a selector or rebooting. Shared mount namespace access
is required; the request lock lives in the current boot's `/dev`. Configure
wireless ADB separately using the existing Android debugging configuration.
APK build, device preflight, an actual boot of each OS, and XR acceptance are
separate validation steps.
