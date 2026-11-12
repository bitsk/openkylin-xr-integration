# Native Python gpiod v2 dependency

This recipe supplies the official `gpiod==2.2.4` API used by the A081 camera rig (`gpiod.request_lines`, `LineSettings`, `Direction`, `Value`) when the target distribution has no usable Python gpiod package. It does not modify camera ownership, GPIO policy, system pip or libc.

`source.lock.json` pins the official PyPI source and build-tool wheels. The source distribution already contains `lib/`, `include/gpiod.h`, and `libgpiod-version.txt` (`2.2`). Upstream `setup.py` compiles eleven bundled C files into `gpiod._ext` and clears its external library list. No `libgpiod-dev` package or system `libgpiod.so` is needed. The recipe removes `LIBGPIOD_VERSION` (which otherwise enables upstream source fetching) and `LINK_SYSTEM_LIBGPIOD` (which otherwise selects the system library).

The pinned setuptools wheel retains its private vendored dependencies, including `jaraco.text`. It is unpacked alongside wheel and packaging in the build output and selected with `PYTHONPATH`; `python -S` excludes system site-packages. The recipe never invokes pip, creates a venv, or installs these build tools.

On a build host, explicitly fetch the four checksum-locked files once:

```sh
python3 devices/a081/gpiod/build.py --cache /work/inputs/gpiod --download-only
```

Transfer that cache and this recipe together. On the target, native ARM64 CPython 3.12, its development headers (`libpython3.12-dev`), a native C compiler, libc headers, binutils/readelf and dpkg-deb must already be present. The generic `python3-dev`, setuptools and wheel distribution packages are unnecessary.

```sh
python3.12 devices/a081/gpiod/build.py \
  --cache /work/inputs/gpiod --output /work/build/gpiod-native
```

Build output includes the native wheel, a small `python3-gpiod` Deb under `/usr/lib/python3/dist-packages`, a compile log and checksum/dependency manifest. The recipe imports the built module to confirm its API and version, checks ARM64 ELF identity and rejects external `libgpiod` linkage. It does not request a line, open a gpiochip or install the package. Installation and actual camera-rig acceptance remain separate, explicit session-owner actions.

`dpkg -i` installs the resulting Deb through the package database; no system pip files are touched. The Deb conflicts with the alternative `python3-libgpiod` provider to prevent duplicate module ownership. Its libc dependency is derived from the native extension's actual symbol versions, and it depends on Python 3.12. Original source SPDX headers and upstream metadata are unchanged; the pinned source archive remains available for the bundled LGPL C library.
