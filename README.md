# openKylin XR integration

型号配置、独立资产锁定与发行版元包的维护入口。

`devices/a081/` 保存硬件 overlay 和 vendor.lock.json；原厂字节由 xr-vendor-assets Release 提供。安装时固件进入 /usr/lib/firmware/xr/a081，启动配方消费 model.json 的 kernel_command_line，通过独立固件搜索路径选择资产。该包不覆盖发行版常规固件文件。

`debian/` 提供公共基础、串流、SteamVR 候选和调试元包。原生 OpenXR 组合需要对应后端完成后再加入。设备服务安装为禁用状态，启动分区、活动运行时与硬件会话由明确的部署或 session 操作选择。

在目标发行版执行 `dpkg-buildpackage -us -uc -b`；构建结果与实机验收分别记录。
