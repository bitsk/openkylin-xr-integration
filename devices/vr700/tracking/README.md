# VR700 real-input HyperSpace session

The installed pipeline uses one head/camera/IMU producer, shared frame consumers
for the real controller SDK and original-weight hand backend, and the Monado
SteamVR provider. HyperSpace selects `/opt/steamvr/steamxr_linuxarm64.json` through
`xr-shell-session`. The standalone simulated Monado profile is a separate display
exercise and is never selected here.

`prepare.py` generates an inactive target root from explicit private resources.
Pass clean exact Git component snapshots and their commits, the original VR700
tracker configuration and per-device calibration with their expected SHA-256,
and optionally an already imported original-weight hand asset set. It uses the
actual hand calibration reader; it does not rename or substitute MIX calibration.
The example specifies the observed four OV7251 routes and flips. The mainline UART
pathname must be checked against the actual serial controller before activation.

```sh
python3 prepare.py --private-input private-resources.json \
  --stock VR700_CAPTURE_ROOT --stock-manifest COMPLETE_CAPTURE_MANIFEST \
  --calibration device_calibration.xml --calibration-sha256 CALIBRATION_SHA256 \
  --config6 trinity_6dof_config.xml --config6-sha256 CONFIG_SHA256 \
  --session-source LOCKED_SESSION_SOURCE --session-commit SESSION_COMMIT \
  --hand-source LOCKED_HAND_SOURCE --hand-commit HAND_COMMIT \
  --hand-assets IMPORTED_ORIGINAL_MODELS --output NEW_STAGING_DIRECTORY
```

The generated root contains `/etc/xr/vr700-session.json`, its UART controller
plan, `/etc/xr/hand-tracking.json`, private XML, and neutral runtime settings.
Hand sampling and runtime input are enabled. Deploy the runtime version that separates real hand input from physical-controller anchor availability before applying this profile. Missing VR700 controller anchors keep physical-controller candidates unavailable; hand input must not fabricate those transforms. There is no startup unit activation. Install staged files as root, retaining
private XML permissions. Use the component builder with an updated exact source
lock to install these project packages:

- `xr-hexagonrpc-daemon`, `xr-device-tools`, `xr-head-tracking`,
  `xr-head-tracking-tools`, `xr-controller-worker-bionic`, `xr-controller-tools`;
- `xr-hand-tracking`, `xr-hand-backend-quest-dsp`, `xr-session-manager`,
  `xr-monado-steamvr-driver`, and `xr-native-interop`;
- `xr-shell-session`, `xr-shell`, `xr-window-server`, `xr-dock`, `xr-system-ui`,
  `xr-environment-qingkong`, `xr-spatial-style-ukui`, and `xr-mesa-vulkan-drivers`.

The controller worker package must use its VR700-capable dependency recipe; never
satisfy an old `xr-vendor-a081-controller` dependency with MIX assets. Install the
model-specific `vr700-sensors-files.service` from the board overlay without
enabling it. Its registry root is `/usr/share/qcom/sm8250/iqiyi/vr700`.

Additional private inputs and installed paths:

| Input | Target | Requirement |
| --- | --- | --- |
| Complete upstream ARM64 SteamVR package | `/opt/steamvr` | Preserve all runtime resources, bin/linuxarm64, and OpenXR manifest; record external package hash. |
| Gamescope, gamescopereaper, their library closure | `/usr/bin` and explicit native library path | Use verified external packages; resolve against the installed openKylin loader. |
| VR700 Bionic ARM32 dependency closure and controller config/data | `/opt/xr/vr700/controller-root` | Original linker, system/lib, system/etc/controller/data and a private manifest. Empty proc/dev/tmp mountpoints are created by the SDK launcher. |
| VR700 DSP runtime, sensor registry and SoC files | `/opt/xr/vr700/session/tracking/stock-runtime/qcom` | Model-specific dsp/cdsp, dsp/sdsp, sensors and socinfo; never another headset's registry. |
| Device controller grip/aim anchors | `/usr/share/xr/devices/vr700/controllers/controller-anchors.json` | Derive from VR700 assets. Do not use MIX transforms or identity transforms as a claimed calibration. |
| Optional VR700 controller artwork | Same directory, left/right mesh.json and texture.png | Shell's neutral built-in mesh is acceptable when artwork is absent; this does not replace grip/aim anchors. |
| Installed project binaries | Capsule paths used by profile | Use `xr-session configure` to copy from current packages, or copy the explicit package files listed below. |

The capsule needs `controller-sdk-pose`, `liba081-sdk-log.so`, and
`controller-dsp/{libcdsprpc.so,libcdsprpc_system.so,liba081-snpe-runtime.so}` from
`/usr/lib/aarch64-linux-gnu/xr/controller`. It also needs
`tracking/hexagonrpcd-a081` from `/usr/bin/xr-hexagonrpcd`. These retained filenames
are ABI names, not permission to import old MIX binaries. Head producer and plugin
paths come from `/usr/lib/aarch64-linux-gnu/xr/head-tracking`.

Start only after dependencies and actual resources are present:

```sh
QIYU_VR_SESSION_PROFILE=/etc/xr/vr700-session.json xr-session start --seconds 60
QIYU_VR_SESSION_PROFILE=/etc/xr/vr700-session.json xr-session stop
```

Session helpers validate the VR700 DT compatible, installed root marker, selected
kernel, graphics account, and private tracker XML before hardware mutation.
Free-running mode never requests GPIO15/144 and never performs Nordic SPI reset.
It keeps real QCFT timestamps and the producer's unchanged frame matching rules;
streaming four cameras does not itself establish valid paired 6DoF tracking.
The UART owner handles radio lifetime. The camera owner remains unique; hands
consume its shared stream. Physical poses, accepted controller/hand packets,
scene startup, and later wearer/optical acceptance must be recorded separately.

The board overlay orders SLPI startup, the single resident sensor-files owner,
then CDSP startup after actual listener and SEE readiness. Each DSP selection
checks VR700 identity and installed firmware; missing inputs fail explicitly.
This service ordering is not itself a claim that cold startup is validated.
The preparation tools do not enable services. Install `v4l-utils` (`media-ctl`, `v4l2-ctl`), `kbd`
(`chvt`), and the locked Python gpiod package before session activation.

When creating a deployment archive for openKylin, map staged `opt/` contents to
`var/opt/` to preserve the distribution's `/opt -> var/opt` link. Store numeric
owner/group 0 and directory mode 0755, preserve private XML mode 0600, omit the
archive root entry, and extract with `--no-overwrite-dir`. Do not transfer host
ownership or replace the system root directory.

The direct SEE IMU launcher selects `tracking/stock-runtime/qcom/dsp/slpi`.
VR700 names the original directory `vendor/dsp/sdsp`; create the explicit
`slpi -> sdsp` alias and include the original
`system/lib/rfsa/adsp/libsns_low_lat_stream_skel.so` there. `import-dsp.py`
accepts `--stock`, its complete capture `--manifest`, and a new `--output`
qcom runtime directory, checks every input digest, and creates this mapping
offline. The output is now the parent of `dsp/`, not `dsp/` itself. It must
use this headset's capture, including its SLPI shell; no MIX fallback exists.

The same importer includes the CDSP RFSA QVR driver, camera/3DoF helpers, XR2
8250 tracker, camera receiver, SNPE V66 and calculator libraries alongside the
original vendor CDSP runtime. Vendor DSP directories alone are insufficient;
RFSA inputs are checked against the same independent VR700 capture manifest.

`prepare.py --native-libraries-root VERIFIED_EXTERNAL_SDK` imports the five
pinned libraries in `native-libraries.json`, including pixman 0.46.4 required
by the selected Gamescope. A dependency listing alone does not prove lazy
symbol resolution; use a bind-now startup check with the target loader.

The controller namespace requires an empty regular
`system/bin/a081-controller-sdk-probe` bind target and existing `proc`/`dev`
mountpoints. The preparer creates these without importing any executable into
the placeholder. The installed launcher binds the exact packaged worker there.
The Bionic asset manifest must be root-owned mode 0644; all parent directories
are 0755, private XML remains 0600, and only namespace temporary directories
are 1777. The preparer applies these modes independently of the host umask or
asset source modes. No extra calibration alias is created.

Gamescope's deferred backend needs XCB, Xlib and Wayland Vulkan instance
extensions. Install the distribution's `mesa-vulkan-drivers` (26.0.3-ok3
in the selected image); `xr-mesa` supplies the separate compositor ICD and
does not provide X11 WSI. The generated `/etc/xr/vr700-desktop-icd.json`
selects the distribution driver by absolute library path, preventing the
private `xr-mesa` library directory from overriding its identical SONAME.
The two profile ICD paths must remain distinct.

`finish-installed-capsule.sh` copies only the installed package helpers into
the selected VR700 capsule, including `pose-watch` from the Monado driver
package. The diagnostics package alone does not provide this binary. The
formal ready path additionally consumes upstream `vrserver`, `vrcmd`, and
`libopenvr_api.so` from the complete selected SteamVR runtime.

The CDSP import also requires the original vendor RFSA CVP, FastCV, and DSP-CV
libraries. `libfastcvadsp.so` itself needs `libdspCV_skel.so`; collecting only
the system RFSA directory leaves this recursive dependency unresolved.

`runtime-files.json` fixes the complete required set of 51 DSP files plus
`sns_reg_version` and `hw_platform`, with source, destination, size and SHA-256
for every file. Both entrypoints use `runtime_import.py` to check this lock
against the independent capture manifest and actual file bytes before writes.
Missing files or mismatched versions fail; there is no guessed metadata or MIX
fallback. `prepare.py` requires `--stock` and `--stock-manifest` and writes the
same 53 files into both the capsule qcom root and the selected resident root.

The original 10-byte registry version is installed as `sensors/sns_reg_version`;
the captured platform value is installed as `socinfo/hw_platform`. FastRPC maps
them read-only. The `xr-hexagonrpc` package must include the registry-version
virtual mapping. The importer additionally copies the original per-device sensor registry and
vendor configuration files using their private capture-manifest hashes. Other
SoC files and head calibration remain separate private inputs; no missing
values or calibration aliases are generated.

The default sensor mode is `read-only-cached`. Both runtimes import the complete
original persistent registry unchanged and expose an empty `sensors/config` to
FastRPC. Vendor JSON files remain in `sensors/config.vendor-original`, with
original mtimes read from the verified `registry/sns_reg_config` cache. Their
bytes, timestamps and cache source remain recorded in the private receipt.

Restoring mtimes alone did not prevent this firmware from requesting
`temp.json` writes and failing registry initialization. With the complete
original registry and an empty exposed config directory, the observed VR700
SLPI startup registered proximity, accelerometer and gyroscope through the
single resident listener. This establishes the cached registry startup path,
not full tracking acceptance. DSP writes remain forbidden.

For an existing installation, stop the session and resident listener under the
hardware owner's control, then run `migrate-cached-registry.py --runtime ROOT
--receipt IMPORT_RECEIPT` for each runtime. It verifies every original registry
and vendor config hash before moving the config directory; it refuses ambiguous
or changed contents, never replaces a populated archive, and writes the runtime
mode metadata. The original vendor files can be restored by removing only the
empty config directory and renaming the archive back while the listener is
stopped. Do not overlay directory entries from a tar archive to perform this
migration. Library/metadata update archives contain only file members under the
physical `usr/share` and `var/opt` paths.
