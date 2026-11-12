# 既有维护控制工具兼容补丁

`explicit-debian-selector.patch` 修改既有 `control.py` 的 Debian 分支：
通过原来的原子临时文件/rename 写入 `next-system=debian`，不再仅删除一次性选择。
这样显式维护启动可以覆盖非 Debian 的 persistent default，旧版默认 Debian 的 init 也保持兼容。
osstore UUID、fallback marker/init、可选系统安装检查和写后 sync/ack 均保留；
不改写 boot slot、GPT 或 recovery 镜像。

此补丁的原控制文件 SHA-256 为
`5c2461e5c8503b7cea4f5c529543105a97770f06351fd8331951a2b72bac44d2`，
修改后为 `aa700dca735bd1aa612dd4c43800a31a6f31e3f42e9e0110ff8714653655ead0`。
在维护工具所在目录核对原件并应用补丁；该目录应包含 `control.py`：

```sh
patch --dry-run -p1 < /path/to/explicit-debian-selector.patch
patch -p1 < /path/to/explicit-debian-selector.patch
```

本仓库维护兼容差异，不复制含本机 ADB/osstore 身份的完整控制工具。
镜像构建 manifest 与维护工具 manifest 的字段不同；后者必须提供
`sha256`、`image` 和包含目标系统的 `one_shot_systems`，并保留离线/未刷写状态。
选择 manifest 本身不会安装候选镜像或晋升基线。
