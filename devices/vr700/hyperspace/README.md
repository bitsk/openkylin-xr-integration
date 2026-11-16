# VR700 HyperSpace initial display profile

The `xr-image-tools` profile `vr700-simulated` builds a standalone ARM64
Monado service and OpenXR runtime from `components.lock.json`. The profile's
CMake recipe disables all physical drivers, including A081, and enables only
simulated devices. Its external compiler/SDK inputs are explicitly supplied
and hashed by the build manifest.

Install the seven generic component packages listed by that profile, preserving
their normal Debian dependencies. Place its runtime tree and the exact builder
commit's `tools/common` and `tools/native` directories below
`/opt/xr/vr700-simulated`. Install `launch-simulated` as
`/usr/local/bin/vr700-hyperspace-simulated`. No service or autostart is installed.
Do not install A081 device or tracking packages.

From the `xr` user's existing Kylin Wayland session, run:

```sh
vr700-hyperspace-simulated --ack-simulated --seconds 60
```

The launcher uses the installed private Freedreno ICD and existing desktop
Wayland endpoint. The common session helper owns and cleans up Monado, Shell,
window-server, dock and system UI. Audio and IME are explicitly disabled for
this first graphics stage. Its default bounded run is 60 seconds; zero requests
an operator-stopped session. Lifecycle logs and captures remain under the user's
state directory. A root maintenance console must switch to the actual logged-in
user and obtain that session's display environment before invoking it.

Success means GPU/runtime/UI startup with synthetic poses and desktop presentation.
It does not establish physical headset, controller or hand tracking, VR700 optics,
direct scanout, audio, IME or wearer acceptance. All remain separate validation.
