<p align="center">
  <img src="https://raw.githubusercontent.com/ellmos-ai/clutch/master/logo.jpg" alt="clutch" width="100%">
</p>

[English](README.md) · [Deutsch](README_de.md) · [Español](README_es.md) · [简体中文](README_zh-Hans.md) · [日本語](README_ja.md) · [Русский](README_ru.md)

# clutch

> 供应商无关的 LLM 编排引擎，内置自动学习功能

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)
![License MIT](https://img.shields.io/badge/License-MIT-green)
![Version 0.4.0](https://img.shields.io/badge/Version-0.4.0-orange)

**clutch**（德语：*Kupplung*，即"离合器"）采用驾驶隐喻，将任务智能路由至跨多个供应商的最优 LLM 模型。它分析任务复杂度与目的，选择合适的模型和推理级别，追踪预算，并从经验中学习。可作为**库**、**CLI** 或**本地 Web 应用**使用。

## 功能特性

- **供应商无关** — 支持 Anthropic（Claude）、Google（Gemini）、Ollama（本地与远程）、Claude Code 以及 **Kimi**（Moonshot API / CLI / Ollama Cloud）
- **自动路由** — 分析任务复杂度*和目的*（编程、视觉、研究、批量处理），选择最优模型 + 推理级别
- **目的与视觉感知** — 将图像/文档输入路由至具有视觉能力的模型；将任务与模型优势相匹配
- **CLI + Web 界面** — `clutch route/run/chat/models/stats`，以及可选的 FastAPI Web 聊天界面（`clutch serve --web`）
- **凭据存储** — 将 API 密钥保存在 `~/.clutch/credentials.json` 中（`clutch keys ...`）；环境变量优先级更高
- **模型发现** — 自动检测已安装的 Ollama 模型（本地/远程）和 OpenAI 兼容的 `/v1/models` 端点
- **预算追踪** — 四区燃油表（绿/黄/橙/红），设有每日和每月限额
- **学习引擎** — 适应度评分与 epsilon-greedy 探索策略，随时间推移持续优化路由
- **执行模式** — 单任务、链式（Kolonne/车队）、并行团队及蜂群处理
- **健康监控** — 熔断器、延迟追踪、过度调用/token 爆炸告警、供应商故障转移
- **SQLite 指标** — 持久化行程日志、聊天会话、提示词库和配置文件

## 架构

整个系统遵循**汽车/驾驶隐喻**（代码标识符使用德语术语）：

```
                    +----------------------------------+
                    |            FAHRER                 |
                    |        (Driver / Orchestrator)    |
                    |     Any LLM: Opus, Gemini, ...   |
                    +--------+----------+--------------+
                             |          |
                +------------+          +-------------+
                |                                     |
        +-------v--------+                   +--------v-------+
        |    STRECKE      |                   |    GETRIEBE    |
        | (Road / Task    |                   | (Gearbox /     |
        |  Analysis)      |                   |  Model Registry|
        +----------------+                   |                |
                                              | G1: Haiku      |
        +----------------+                   | G2: Flash      |
        |   GAS / BREMSE  |                   | G3: Sonnet     |
        | (Throttle/Brake |                   | G4: Gemini Pro |
        |  Reasoning Lvl) |                   | G5: Opus       |
        +----------------+                   | + Ollama local |
                                              +----------------+
        +----------------+
        |    KUPPLUNG     |    +------------+    +-------------+
        | (Clutch / Model |    |   TACHO    |    |  TANKUHR    |
        |  Switching)     |    | (Metrics)  |    | (Budget)    |
        +----------------+    +------------+    +-------------+
```

| 组件 | 作用 | 模块 |
|-----------|------|--------|
| **Fahrer**（司机） | 编排器 — 选择模型、推理方式和执行模式 | `fahrer.py` |
| **Strecke**（路段） | 任务分析与分类 | `strecke.py` |
| **Getriebe**（变速箱） | 供应商无关的模型注册表 | `getriebe.py` |
| **Gang**（档位） | 具体模型（G1--G5） | `getriebe.py` |
| **Gas/Bremse**（油门/刹车） | 推理级别（0--100%） | `gas_bremse.py` |
| **Kupplung**（离合器） | 模型切换机制 | `kupplung.py` |
| **MotorBlock**（发动机） | 统一 API 调用层 | `motorblock.py` |
| **Tacho**（速度表） | 指标采集 | `tacho.py` |
| **Tankuhr**（油量表） | 预算追踪（4 个区域） | `tankuhr.py` |
| **Bordcomputer**（车载电脑） | 健康监控、熔断器 | `bordcomputer.py` |
| **Fahrtenbuch**（行程记录） | SQLite 指标存储 | `fahrtenbuch.py` |
| **Fahrschule**（驾校） | 学习 / 进化引擎 | `fahrschule.py` |

## 路段类型

| 路段 | 难度 | 默认档位 | 油门 | 模式 |
|------|-----------|-------------|----------|---------|
| Feldweg（土路） | 简单 | Haiku (G1) | 30% | 单任务 |
| Landstrasse（乡道） | 标准 | Sonnet (G3) | 50% | 单任务 |
| Bundesstrasse（国道） | 修复 Bug | Sonnet (G3) | 70% | 单任务 |
| Autobahn（高速公路） | 架构设计 | Opus (G5) | 90% | 单任务 |
| Rallye（拉力赛） | 批量操作 | Haiku (G1) | 30% | 蜂群 |
| Konvoi（车队） | 流水线 | Sonnet (G3) | 50% | 链式 |
| Teamfahrt（团队行程） | 多文件 | Sonnet (G3) | 50% | 团队 |
| Langstrecke（长途） | 复杂任务 | Opus (G5) | 90% | 混合 |

## 安装

```bash
git clone https://github.com/ellmos-ai/clutch.git
cd clutch
pip install -e .
```

### 依赖要求

- Python 3.10+
- 所需供应商的 API 密钥（设置为环境变量）：
  - `ANTHROPIC_API_KEY`（Claude 模型）
  - `GOOGLE_API_KEY`（Gemini 模型）
  - 本地运行 Ollama（用于本地模型）

## 快速上手

```python
from clutch import Fahrer

# 创建司机（使用所有已配置的供应商）
fahrer = Fahrer()

# 描述任务 — 司机处理一切
result = fahrer.fahren(
    "Fix the authentication bug in the login module",
    handler=my_handler,
)

# 查看所选配置
print(result.config.gang.name)       # "claude-sonnet"
print(result.config.gang.provider)   # "anthropic"
print(result.config.gas.wert)        # 0.7

# 仪表板
status = fahrer.status()
print(status["tankuhr"]["zone"])     # "green"
print(status["getriebe"])            # "Getriebe[haiku(G1), flash(G2), ...]"

# 从历史运行中学习
fahrer.trainieren()
```

## 命令行界面

执行 `pip install -e .` 后，`clutch` 命令即可使用：

```bash
clutch route "Fix the auth bug"      # 显示路由决策（dry-run，不调用 LLM）
clutch "Explain quantum computing"    # 一次性：路由 + 执行，打印答案
clutch run "..." --json               # 机器可读输出（供其他 Agent 使用）
clutch chat                           # 交互式 REPL
clutch models [--json]                # 列出所有档位（模型）
clutch stats                          # 使用量 / 预算 / 健康仪表板
clutch config <key> [value]           # 读取/设置 CLI 配置
clutch keys set MOONSHOT_API_KEY      # 存储 API 密钥（隐藏输入；值从不显示）
clutch keys list                      # 列出已存储密钥名称（不显示值）
clutch serve --web                    # 启动 Web 界面（需要：pip install -e ".[web]"）
```

三种使用模式：**控制台**（人工使用）、**Web 界面**（人工使用，图形化）和 **CLI/API**（其他 LLM/Agent 通过 `--json` 或 OpenAI 兼容 Web 端点路由任务）。

## API 密钥与凭据

clutch 按以下顺序解析密钥（第一个非空值优先）：

1. 环境变量（例如 `MOONSHOT_API_KEY`）— CI/服务器首选
2. clutch 存储 `~/.clutch/credentials.json`（通过 `clutch keys set`，文件权限 0600）
3. `~/.credentials/<name>` 文件（与同类工具互操作）

值从不被打印、记录或提交到仓库。

## 配置

默认配置位于 `clutch/config/`，使可编辑安装和 wheel 包使用相同的内置路由默认值。如需项目特定的覆盖配置，可向 `Fahrer` 传入包含自定义 `config/` 文件夹的 `base_dir`。

| 文件 | 用途 |
|------|---------|
| `kupplung.json` | 全局设置（司机默认值、蜂群限制、预算） |
| `getriebe.json` | 所有档位 + 供应商映射 |
| `strecken.json` | 路段类型到档位/油门的映射 |
| `fitness_criteria.json` | 学习引擎阈值 |

### 预算区域

| 区域 | 使用率 | 允许档位 |
|------|-------|--------------|
| 绿色 | 0--30% | 全部（G1--G5） |
| 黄色 | 30--60% | G1--G3 |
| 橙色 | 60--80% | 仅 G1--G2 |
| 红色 | 80--100% | 无（预算耗尽） |

## 支持的供应商

| 供应商 | 模型 | 本地 |
|----------|--------|-------|
| **Anthropic** | Claude Haiku、Sonnet、Opus | 否 |
| **Google** | Gemini Flash、Pro | 否 |
| **Ollama** | Qwen、Mistral 等（本地与远程） | 是 |
| **Claude Code** | 通过子进程（CLI 会话） | 是 |
| **Kimi (Moonshot)** | `kimi-k2.7-code`、`kimi-k2.6`，通过 OpenAI 兼容 API；`kimi-cli`/`kimi-code` CLI；Ollama Cloud | API / CLI |
| **OpenAI 兼容** | 任何 `/v1/chat/completions` 端点（设置 `base_url`） | 否 |

## 执行模式

- **单任务** — 一个模型，一个任务
- **车队（Kolonne/Convoy）** — 顺序链式，第 N 步输出作为第 N+1 步输入
- **团队** — 并行专业 Worker，结果合并
- **蜂群** — 大规模并行微任务（例如 20 个 Haiku），然后聚合

## 项目结构

```
clutch/
+-- clutch/
|   +-- __init__.py
|   +-- fahrer.py          # 编排器
|   +-- strecke.py         # 任务分析
|   +-- getriebe.py        # 模型注册表
|   +-- kupplung.py        # 模型切换
|   +-- motorblock.py      # 统一 API 层
|   +-- gas_bremse.py      # 推理级别
|   +-- fahrtenbuch.py     # SQLite 指标
|   +-- bordcomputer.py    # 健康监控
|   +-- tankuhr.py         # 预算追踪
|   +-- tacho.py           # 指标
|   +-- fahrschule.py      # 学习引擎
|   +-- patterns/
|       +-- kolonne.py     # 链式模式
|       +-- team.py        # 并行模式
|       +-- schwarm.py     # 蜂群模式
|       +-- hybrid.py      # 混合模式
|   +-- config/
|       +-- kupplung.json
|       +-- getriebe.json
|       +-- strecken.json
|       +-- fitness_criteria.json
+-- tests/
|   +-- test_clutch.py
|   +-- test_learning.py
|   +-- test_patterns.py
|   +-- test_route.py
+-- data/                  # 运行时数据（不跟踪）
```

## 测试

```bash
pip install -e . pytest
pytest -q
```

Pytest 配置为仅收集 `tests/` 目录。根目录下的脚本如 `demo.py`、`live_test.py` 和 `claude_code_test.py` 是手动供应商检查脚本。

## 贡献

请参阅 [CONTRIBUTING.md](CONTRIBUTING.md) 了解贡献指南。
德语汽车 API 术语说明请参阅 [GLOSSARY.md](GLOSSARY.md)。

## 许可证

MIT 许可证。详情请参阅 [LICENSE](LICENSE)。

---

## 免责声明 / Haftung

本项目是一项**无偿开源捐赠**，符合德国民法典（BGB）第 516 条及以后条款的规定。根据 **BGB 第 521 条**，作者的责任限于**故意和重大过失**。此外适用 GPL-3.0 / MIT / Apache-2.0 第 15–16 条（根据所选许可证）的免责条款。

使用风险自担。不提供维护承诺、可用性保证，不保证无错误或适用于特定用途。

This project is an unpaid open-source donation. Liability is limited to intent and gross negligence (§ 521 German Civil Code). Use at your own risk. No warranty, no maintenance guarantee, no fitness-for-purpose assumed.
