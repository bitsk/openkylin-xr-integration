# RVVR SaberV

此处是 SaberV 的唯一 openKylin 适配配方。上游游戏、示例歌单与编辑器固定在
`upstream.json`，应用改动保存在 `application.patch`。Godot 引擎只从组件锁选中
的 xr-monado 原生兼容配方构建，不读取历史引擎产物或设备 prefix 中的代码。

使用 `xr-build-components build --profile saberv`；显式输入编辑器、Godot 原始
归档及目标 libm，Git 缓存只供提交对象。生成的包包含 ARM64 引擎、PCK 和
示例曲。音乐仅供本地安装使用，不包含在公开源码仓库内。

应用入口调用 xr-session-manager 所属的应用切换接口。会话管理器复制当前
profile 的硬件与运行时选择，只替换前台场景；退出清理后恢复原场景。应用
不采集相机，不选择另一套追踪或图形驱动。安装不自动启动游戏或修改开机配置。

MIX 版使用 OpenXR STAGE。启动和重新居中时，游戏等到有效头部姿态后，
调整共享追踪原点，使眼睛距离虚拟地面 1.6 米。游戏内的身高微调叠加在此基础上。

菜单射线从可见剑柄中心发出，绘制和命中共用 OpenXR aim 的 -Z 方向。光剑和切块使用 grip，剑柄
中心对齐握持原点，剑身沿 grip 的 -Z 轴。菜单点击继续使用已有扳机映射。
