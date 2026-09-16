# 接入方法与兼容问题

## 独立组织

上游官方应用负责网页、会话和隧道。自有适配集中在 ops/；日常命令复制到用户私有运行目录，不依赖工作区固定位置、个人 Harness 或另一套 Agent 平台。

主要路径：应用 `/Applications/Codex Web GPT.app`，本地 Responses `http://127.0.0.1:17841/v1`，私有状态 `~/.codex-chatgpt-web/`，管理命令 `~/.local/bin/codex-web`。这些是路径约定，不是需要提交到 Git 的状态内容。

## 设置顺序

1. 使用上游官方 v5.0.6 安装器，核验发布校验和，安装 arm64 包。
2. 在桥接应用内完成自己的 ChatGPT 登录。
3. 完成 Full 模式：官方 Tunnel、仅 Tunnels Read + Use 的普通 key、名为 Codex Native2 的 ChatGPT 连接器，以及运行时验证。
4. 安装 `ops/` 的具名配置和独立命令，获取真实模型目录，再安装桌面字段。
5. 用桌面随附二进制检查模型列表与真实任务，而非只看安装提示。

登录和密钥属于每个人自己的私有配置。本仓库不包含可复用账号或授权；不要把 key 放到命令行明文、截图或 Git。

## 系统代理

曾出现网页能联网但 Bun 后台模型目录请求超时。原因是 GUI 启动的后台没有继承终端代理变量。管理入口读取 macOS 当前 HTTP/HTTPS 代理，使用 LaunchServices 环境参数启动应用，并让环回地址绕过代理。已运行的应用不会因再次 open 自动更新环境。

## CLI 路由陷阱

在测试的 0.154.0 中，`--ignore-user-config` 忽略了 profile；exec / resume 又分别解析参数。外层覆盖参数不足以保证最内层任务沿用网页路由。

入口把 provider、base URL 和模型覆盖放到最内层命令末尾，并拒绝非网页模型以及会吞掉后续参数的 `--`。离线哨兵测试用真实 CLI 验证首轮和续接实际请求，不以模型回答自述判断路由。

早期两次请求确实走了原生默认路径，因此被排除出网页成功证据。

## 首轮工具元数据

缺少网页模型元数据时，CLI 使用 fallback metadata，原生 apply_patch 可能缺失，模型还可能误用导入的同名连接器。修复方法是从实际桥接获取带 freeform 补丁元数据的目录，再显式加载 model_catalog_json。之后原生 file_change 和开发闭环通过。

元数据 fallback 与推理自动回退是不同概念；本实验没有配置后者。

## 桌面安装提示不是桌面验收

上游 v5.0.6 保留已有 model_provider。原配置为 custom 时，真实新启动的桌面 app-server 只返回原生模型。应用却可能因任意客户端的一次目录请求而显示安装成功。

部署入口单独管理四个顶层字段：model_provider=openai、model=chatgpt-web/high、model_catalog_json 指向私有目录、service_tier=default。原 custom 定义保留，原始行存入自有私有 journal，不修改上游恢复日志。

恢复时只处理自有字段，保留无关并发改动；用户后来另选原生模型时保留其选择；如仍选网页模型，撤销时恢复先前原生模型，避免留下不可用别名。

## 静态目录的代价

目录快照修复了首次工具装配，但没有自动跟随 Bigger Context 开关。开启三倍后仍显示 95k，是本地适配遗漏。

最后补入按设置指纹同步的修复：监听桥接配置和原生上下文配置变化，重新读取目录；失败保留旧快照并报告不一致。只做元数据读取，不调用推理。launchd 没有 Homebrew 的 PATH，后台取版本需使用独立桌面二进制。真实 launchd 环境下已验证可重新生成目录。

这个修复只能更新真实容量，不能把网页变成 900k 模型。

## 撤销

先 `codex-web catalog-watch-off`，确认无活动网页任务，再 `codex-web disconnect` 和 `codex-web autostart-off`。独立命令会先恢复四项桌面字段，再调用上游撤销路由。仅在应用内点 Remove integration 不能恢复自有的额外字段。

核对 config.toml 的 provider、模型、目录与上下文设置；不要整份覆盖旧备份，避免破坏并发修改。退出旧桥接并移除其自有 profile/命令/启动项后，原生 Codex 不再依赖本地桥接端口。
