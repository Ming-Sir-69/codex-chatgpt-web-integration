# 可选适配的维护与复现

桥接应用的安装、更新和账号设置始终使用[原作者入口](https://github.com/miuuyy/codex-chatgpt-web#readme)。下列工具是本仓库的可选配置增强，适用性以记录的 macOS / v5.0.6 环境为基准；它们不替代原软件安装器。

## 操作对应关系

| 用途 | 本仓库入口 |
| --- | --- |
| 安装本地具名配置 | `python3 ops/manage.py install-profiles` |
| 安装独立管理命令 | `python3 ops/manage.py install-command` |
| 继承系统代理启动已安装应用 | `codex-web open` |
| 获取真实目录、补齐首轮工具元数据 | `codex-web refresh-catalog` |
| 可逆配置桌面四项字段 | `codex-web install-desktop`，之后完整重开 Codex |
| 跟随三倍开关/原生窗口变化更新目录 | `codex-web catalog-watch-on` |
| 网页与原生独立入口 | `codex-web web` / `codex-web native` |
| 查看路由、健康与目录同步情况 | `codex-web status` |
| 停用同步并完整撤销 | `codex-web catalog-watch-off`，再 `codex-web disconnect` |
| 停用自有登录启动 | `codex-web autostart-off` |

全局配置的撤销遵循自有字段归属，拒绝覆盖冲突修改。原生上下文设置不会为了匹配网页而被缩小。原生入口会使用原生额度，不是失败后的静默回退。

## 复现与验证

- `ops/test_*.py`：12 项离线回归，覆盖 CLI 实际请求路由、桌面恢复与目录设置同步。
- `ops/acceptance/run.py`：从合成 stub 开发校验器并在同一线程增加 CLI；独立验证测试与退出码，可选择假原生凭据隔离模式。
- `ops/desktop_probe.py` 与 `ops/acceptance/desktop.py`：桌面随附程序的真实目录与开发接口。执行前按实际安装位置核对二进制路径。
- `ops/probe_context_switch.py`：本机哨兵模拟用量，验证客户端是否在切到较小窗口时请求压缩。运行前准备匹配的私有模型目录及 `ops/evidence/` 输出目录；不执行真实模型推理。
- `patches/smoke-catalog-native-model.patch`：针对上游 v5.0.6 验收脚本的参数化小补丁，保留上游版权声明。

## 从旧实验仓库保留的 Full 暂存脚本

[reference/stage-full.ts](../reference/stage-full.ts) 是历史配置适配，原先放在上游源码树的 `ops/` 目录。它依赖 v5.0.6 的 `src/` 导出函数；本仓库没有复制完整上游源码，不能在这里直接运行。

它要求已有已登录的 Automatic browser-only 实例，读取本机私有 Tunnel ID/key 文件，复用上游安装/连接/健康函数，写出带原配置 SHA-256 的候选 Full 配置，并在 finally 停止本次 Tunnel。它**会操作真实隧道并写私有暂存状态**；不是 dry-run，也不会替用户创建 ChatGPT 连接器。日常设置仍优先使用原作者 GUI，不建议为了复现而重复创建凭据。

升级先检查上游是否已提供等效修复；不再需要的适配应移除。源码、应用二进制、CLI 和桌面版本分开核验，不用一次聊天或绿色安装提示替代开发验收。
