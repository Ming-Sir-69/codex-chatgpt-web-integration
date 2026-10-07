<picture>
  <source media="(prefers-color-scheme: dark)" srcset="readme-assets/header-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="readme-assets/header-light.svg">
  <img alt="Codex × ChatGPT Web · Integration Experiments · ✦ EricMingle69" src="readme-assets/header-light.svg" width="100%">
</picture>

<p align="center">
  <a href="README.md">简体中文</a> · <a href="README.en.md">English</a> · <a href="PERSONAL-NOTICE.md">✦ EricMingle69</a>
</p>

# Codex × ChatGPT Web · Integration Experiments

macOS adaptations and engineering records based on **[miuuyy/codex-chatgpt-web](https://github.com/miuuyy/codex-chatgpt-web)**.
The reasoning bridge, desktop launcher and MCP tool loop come from miuuyy and upstream contributors; this repository records optional adaptations and experiment boundaries.

## Install upstream, then select adaptations

1. Follow [the author's installation and quickstart](https://github.com/miuuyy/codex-chatgpt-web#readme).
2. Read [upstream and adaptation responsibilities](docs/upstream-and-adaptations.md).
3. Use the configuration tools only when facing the same documented compatibility issue.

Installation and updates use upstream entries; this repository does not redistribute the original software or provide a replacement installer.

## Reading route

| Content | Entry |
| --- | --- |
| Proxy, routing, desktop integration and reversal | [Implementation](docs/implementation.md) |
| Successful, failed and invalid experiments | [Validation](docs/validation.md) |
| Context budgets and retirement decision | [Context tradeoffs](docs/context-and-retirement.md) |
| Configuration and reproduction | [Maintenance and reproduction](docs/maintenance-and-reproduction.md) |
| Consolidated older materials | [Consolidation](docs/consolidation.md) |
| Optional management and acceptance tools | [ops](ops/) |

## Interpret historical results

Observations through 2026-09-16 recorded development tasks completed with Instant, Medium, High, Extra High and Pro.
The local setup nevertheless returned to native Codex for long-context switching without compaction; historical success does not guarantee current Web compatibility.

The recorded practical Pro compaction budget was 95k, or 285k with experimental 3× context—not the native approximately 900k working budget.
Source, standalone CLI, desktop-bundled app-server and the current UI are separate validation targets.

## Reproduction requirements

Offline tools require Python 3.11+; live integration additionally needs matching upstream software, Codex, Web login and Tunnel.
Check versions and reversal paths in [the reproduction guide](docs/maintenance-and-reproduction.md) before selecting an experiment.
Do not upload login materials, tokens or complete private sessions.

## Sources and license

New tools and documents use [MIT License](LICENSE), Copyright (c) 2026 Ming-Sir-69.
Upstream software follows its author's license; patches retain [upstream MIT notices](LICENSES/upstream-MIT.txt). Personal maintenance does not replace upstream authorship.

---

Documentation maintained by **✦ EricMingle69** · [Ming-Sir-69](https://github.com/Ming-Sir-69)  
[Personal identity, licensing and permissions](PERSONAL-NOTICE.md) · The header follows your GitHub theme.
