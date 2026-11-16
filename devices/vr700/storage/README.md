# Explicit storage maintenance

These scripts are for a reviewed, private VR700 partition plan in a dedicated
maintenance boot. They do not run during package installation or normal boot.
`/plan/storage.env` supplies identity, exact geometry, UUIDs and SHA-256 values;
`/plan/original` contains original GPT metadata, both F2FS superblocks and the
original footer, and `/plan/candidate` contains the reviewed GPT replacement.
No device identity or partition image belongs in this source repository.

The operator first runs `inspect.sh original`. After reviewing the private plan
and the data-retention decision, invoke the separate explicit phases:

```
sh shrink.sh --execute-shrink
sh apply-gpt.sh --apply-gpt
sh format-osstore.sh --format-osstore
```

All phases require the expected board, bootloader serial and UFS geometry, and
reject mounted UFS filesystems and active block holders. Shrink uses the pinned
unmodified resize tool, checks both superblocks and segment bounds, and compares
the original Android fsck tree and valid allocation counts. It stops on fsck
errors; quota normalization is never automatic. `-F` acknowledges the tool's
prompt; lowercase `-f`, which ignores errors, is not used.

GPT writes require the same maintenance boot's successful shrink marker and
byte-identical original metadata immediately before writing. Backup GPT is
written first; primary GPT follows. Full readback and a successful kernel
partition-table reread precede formatting only the new osstore partition.
Formatting also requires its same-boot marker, and refuses a recognizable
existing filesystem. These markers are bound to the private plan digest.

If a phase fails, preserve `/run/vr700-storage` logs and inspect the actual device
state. Do not delete a lock or marker and rerun blindly, and do not reboot during
data relocation. A failed partition-table reread needs a reviewed recovery path;
the scripts do not bypass the prerequisite after a reboot. Metadata backups do
not substitute for a full userdata backup. Android data, boot/root return, and
the installed openKylin system require separate verification.
