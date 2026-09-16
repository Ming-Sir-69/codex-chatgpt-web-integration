# 仓库合并与来源

本仓库统一承接此前两个个人仓库的成果：旧私有部署实验与公开 macOS 经验记录。保留公开仓库的干净历史，整合独有配置和复现材料；不把私有历史直接公开。

## 对照核验

- 两边共有的 **14 个** `ops/` 配置、管理、探针、夹具和测试文件，经 Git blob 哈希核对完全一致；统一保留一份。
- 旧仓库独有的 Full 模式暂存适配保留为 [reference/stage-full.ts](../reference/stage-full.ts)，用途和真实副作用在维护说明中交代。
- 上游 smoke 脚本的小改动保留为独立 patch，并保留原项目 MIT 版权声明。
- 旧部署手册、补丁说明、状态与验证总结的公开部分，整合到 implementation、maintenance-and-reproduction、validation、context-and-retirement 文档中。
- 私人原始会话、截图和历史状态保存在本机经过哈希核验的小体积压缩档案，不进入公开仓库。
- 没有复制可从原作者重新获取的完整源码、依赖和安装包；没有混入独立只读 MCP 项目。

核心产品属于 [miuuyy/codex-chatgpt-web](https://github.com/miuuyy/codex-chatgpt-web) 及其贡献者。我们的贡献是本机适配、可逆配置、验证工具和实测结论。安装、更新、产品发布仍使用原作者入口。
