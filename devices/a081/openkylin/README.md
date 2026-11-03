# MIX A081 openKylin 3.0

先用 xr-image-tools 从锁定的官方 ARM64 ISO 准备 rootfs，再把完整文件系统安装到既有 osstore 的独立系统目录。不得覆盖 Debian/SteamOS，启动分区操作仍由设备维护流程管理。

`configure.py --root <inactive-root> --source-root <installed-board-baseline> --kernel-release <matching-release>` 必须以 root 在原生 A081 ARM64 环境运行。输入根不能是当前系统，输出不能已带板级身份标记。配置只消费现有已验证的板级固件、同版本模块、私有网络和维护 SSH 配置，不复制旧发行版 libc/Mesa 或跟踪进程。

配置后在原生 chroot 使用官方 `huanghe` 软件源安装 `openssh-server`，确认 dpkg audit、systemd 和桌面依赖可执行，再进行一次性多系统启动验证。初始默认 multi-user target，维护入口保持 USB 与只允许密钥的 SSH。UKUI 显示会话在独占 DRM 窗口单独验证后启用；不能以包含桌面软件包推定显示通过。系统安装、桌面输出和 XR 功能是独立验收项。

配置导入的 host key、authorized keys、Wi-Fi 文件和本机 UUID 只保存在本机安装中，不能打入公开分发的 overlay 或镜像。

`enable-desktop.py` 在原生 openKylin 中启用 mix 用户的 UKUI Wayland 自登录，并设置 graphical.target；脚本不立即重启显示服务或改启动分区。独占窗口中重启 LightDM 或完整重启后检查 kylin-wlcom、原生 EGL/GLX、DPU 扫描缓冲与退出。默认使用发行版 Mesa；X11 试验出现 DRI3 分配错误，不作为通过路径。
