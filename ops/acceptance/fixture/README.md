# checksum-audit

一个无第三方依赖的本地发布文件校验器，供下载更新后的文件核验使用。

## 当前任务

实现 `audit.py` 的 `audit(root, manifest)`：

- manifest 是 `{相对路径: 小写 SHA-256}` 字典；返回 `{ok: bool, missing: list[str], mismatched: list[str]}`。
- 两个列表均按路径排序；不能修改被检查文件。
- 拒绝绝对路径、任何 `..` 路径组件、空路径及格式错误的摘要，抛出 ValueError。
- 拒绝指向 root 外部的软链接，抛出 ValueError。
- 空清单成功；清单未列出的文件不检查。

验证：`python3 -m unittest -v`。

后续会增加命令行 JSON 输出。本目录是独立验收项目，只能读取和修改此目录内的代码。
