# 来源分工、配置适配与致谢

## 原作者是产品入口

[miuuyy/codex-chatgpt-web](https://github.com/miuuyy/codex-chatgpt-web) 是原项目。核心架构、网页自动化、桌面启动器、模型路由、MCP 完整工具回路和大上下文传输由原作者及其贡献者实现。

- [安装与快速开始](https://github.com/miuuyy/codex-chatgpt-web#readme)
- [发布与下载](https://github.com/miuuyy/codex-chatgpt-web/releases)
- [中文文档](https://github.com/miuuyy/codex-chatgpt-web/blob/main/README.zh-CN.md)
- [上游问题与维护进展](https://github.com/miuuyy/codex-chatgpt-web/issues)
- [原项目许可证](https://github.com/miuuyy/codex-chatgpt-web/blob/main/LICENSE)

我们不提供替代下载、打包副本或重写安装器，不把原项目能力归为自己的创新。感谢作者把这条探索路径开源，让本机实践、复验和问题定位成为可能。

## 本仓库增加了什么

这里的“新增”指本次针对特定本机环境编写的配置与验证，不主张这些通用方法为首创，也不宣称上游未来仍需要它们。

| 本机新增内容 | 解决的问题 | 代码/依据 |
| --- | --- | --- |
| macOS 代理感知启动 | GUI 网页联网正常但后台目录请求超时 | [manage.py](../ops/manage.py) 的 open_app |
| 最内层 CLI 路由覆盖 | ignore-user-config 和 exec/resume 各自解析导致误路由 | [CLI 哨兵测试](../ops/test_cli_route.py) |
| 首轮工具目录快照及设置同步 | apply_patch 元数据缺失、三倍开关后仍读旧目录 | [目录同步](../ops/test_catalog_sync.py) |
| 可逆桌面四项字段适配 | 原 custom 服务商使桌面不显示网页模型 | [桌面恢复测试](../ops/test_desktop_config.py) |
| 桌面随附 app-server 验收 | 不能用普通 CLI 结果代替桌面版本结果 | [桌面探针](../ops/desktop_probe.py)、[五档开发验收](../ops/acceptance/desktop.py) |
| 上下文切换哨兵 | 全局 900k 阈值不代表切换小窗口时不压缩 | [切换探针](../ops/probe_context_switch.py) |
| 目录 smoke 参数化小补丁 | 本机原生模型列表变化导致验收脚本硬编码失效 | [独立补丁](../patches/smoke-catalog-native-model.patch) |

## 使用适配的顺序

先使用原作者安装与设置入口；遇到与本文版本、环境一致的问题，再审阅对应代码与测试。保持上游程序与本机适配的归属分明。升级后若上游已经修复，应移除重叠适配，避免永久堆积。

小补丁基于 v5.0.6 / e85e3693fdb4e3e033348c08df0298c20fcdb612，只参数化验收脚本，不改变网页模型、权限或运行时。它含上游上下文片段，保留 [原始版权声明](../LICENSES/upstream-MIT.txt)。自行恢复匹配上游源码后审阅应用；本仓库不保存可重新下载的完整上游源码和依赖。

本机停止使用是个人需求与成本的选择，不是否定原作者的工作。成功、局限和失败都据实记录，供他人做自己的判断。
