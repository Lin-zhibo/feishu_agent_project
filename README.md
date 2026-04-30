# DevFlow Engine：AI 驱动的研发全流程交付引擎

**输入：** 自然语言需求描述

**输出：** `workspace/` 下可运行的项目代码

---

## 核心理念

> Pipeline 是骨架，Agent 是肌肉，人类负责监督和 Review。

把「需求 → 方案 → 编码 → 测试 → 评审 → 交付」整条链路编排成 AI 驱动的 Pipeline。每个环节由专门的 AI Agent 执行，人类在关键检查点做 Approve/Reject 决策。

---

## 快速启动

### 1. 配置

```bash
# config/model.json — LLM API
{
    "API_KEY": "<your api key>",
    "BASE_URL": "<model base url>",
    "MODEL": "<model name>"
}

# config/settings.json — Pipeline 参数（有默认值，可选改）
{
    "workspace": "./out",        # 代码产出目录
    "log_dir": "tmp",            # 日志/暂停文件目录
    "skip_checkpoints": false,   # true 跳过人工确认
    "max_total_time_ms": 600000, # 累计耗时上限
    "max_total_tokens": 50000,   # 累计 Token 上限
    "max_retry": 3,              # LLM API 重试次数
    "temperature": 0.3,          # LLM 温度
    "max_tool_iterations": 20,   # 单 stage 工具循环上限
    "preserve_session": false,   # 完成后保留暂停文件
    "verbose": false             # 输出完整 LLM 请求
}
```

### 2. 运行

```bash
pip install -r requirements.txt

# 启动新 Pipeline
python cli.py --input "打造一个开源PC端记账软件"

# 暂停后恢复
python cli.py --resume                    # 最新
python cli.py --resume 20260501_143022    # 指定 ID

# 管理
python cli.py --list                      # 列出暂停的 Pipeline
python cli.py --terminate 20260501_143022 # 删除指定
python cli.py --terminate-all             # 删除全部

# 跳过阶段
python cli.py --input "..." --skip-review --yes
```

### 3. 产出

```
out/
└── 20260501_143022/    ← 工作区（可运行的代码）
    ├── src/...
    └── ...

tmp/
└── 20260501_143022/    ← 日志（stage 输出 + 暂停文件）
    ├── requirements.md
    ├── solution.md
    ├── code_gen.md
    ├── test_gen.md
    ├── review.md
    ├── delivery.md
    └── pipeline_20260501_143022.json
```

---

## 项目结构

```
feishu_agent_project/
├── agents/                  # 6 个阶段 Agent + 子 Agent 执行器
│   ├── _tool_runner.py      # 工具调用循环（原生 API + 指数退避重试）
│   ├── sub_agent.py         # 子 Agent 执行器（file-writer/code-reviewer/...）
│   ├── requirements.py
│   ├── solution.py
│   ├── code_gen.py
│   ├── test_gen.py
│   ├── review.py
│   └── delivery.py
├── config/
│   ├── model.json           # LLM API Key / Base URL / Model
│   └── settings.json        # Pipeline 全局参数
├── pipeline/                # Pipeline 引擎
│   ├── engine.py            # 阶段编排 + pending/resume + 预算控制
│   ├── models.py            # PipelineConfig, PipelineState, StageInput/Output
│   ├── config_loader.py     # JSON 配置加载
│   ├── checkpoint.py        # 人工审批交互
│   └── callbacks.py         # 耗时/Token 实时可视化
├── prompts/                 # 每个阶段的 PromptTemplate
│   ├── requirements.py
│   ├── solution.py
│   ├── code_gen.py
│   ├── test_gen.py
│   ├── review.py
│   └── delivery.py
├── tools/                   # Agent 可调用的 12 个工具
│   ├── file_ops.py          # Read（分页）/ Edit（replaceAll）/ Write
│   ├── glob.py              # Glob 文件模式匹配
│   ├── grep.py              # Grep 正则内容搜索
│   ├── bash.py              # Bash Shell 执行（含确认/超时/目录）
│   ├── git_cmd.py           # git 命令
│   ├── sub_agent.py         # SpawnSubAgent 子 Agent 工具
│   ├── web_tools.py         # WebSearch, WebFetch
│   ├── tool_search.py       # ToolSearch 延迟加载
│   └── ask_user.py          # AskUserQuestion（单/多选）
├── test/
│   └── test_pipeline.py     # 19 个测试
├── AGENTS.md                # Agent 行为守则（知识地图 + 工具规则）
├── cli.py                   # CLI 入口
├── main.py                  # run_pipeline() / resume_pipeline() 封装
└── README.md
```

---

## Pipeline 流程

```
requirements → solution → [Checkpoint ①] → code_gen → test_gen → review → [Checkpoint ②] → delivery
                       ↑ 人类审批                                          ↑ AI判断 + 人类审批
                       └─ REJECT → 带理由重做                              ├─ AI FAIL → 自动 code_gen
                                                                          ├─ AI PASS + Y → delivery
                                                                          └─ AI PASS + n → review重跑
```

### 6 个 Stage

| Stage | 角色 | 产出 | 专属工具 |
|-------|------|------|---------|
| requirements | 需求分析 | 结构化需求文档 | AskUserQuestion |
| solution | 方案设计 | 架构设计 + 文件结构 | — |
| code_gen | 代码生成 | workspace 中的源文件 | SpawnSubAgent(file-writer) |
| test_gen | 测试生成 | 测试代码 + 运行结果 | SpawnSubAgent(test-writer) |
| review | 代码评审 | 评审报告 + PASS/FAIL | SpawnSubAgent(code-reviewer) |
| delivery | 交付集成 | 交付摘要 + 文件清单 | git_cmd_exec |

所有 stage 共用 9 个通用工具（Read/Edit/Write/Glob/Grep/Bash/WebSearch/WebFetch/SpawnSubAgent）。

### 子 Agent 系统

多文件操作时，主 Agent 调用 `SpawnSubAgent` 并行创建/审查/测试：

| 类型 | 工具 | 用途 |
|------|------|------|
| file-writer | Write | 创建单个文件 |
| code-reviewer | Read, Grep | 审查单个文件 |
| test-writer | Read, Write, Bash | 写测试 + 运行 + 修复 |
| researcher | WebSearch, WebFetch | 技术调研 |

### Checkpoint 决策

| AI 判断 | 人类操作 | 路由 |
|---------|---------|------|
| — | APPROVE | → 继续（仅 solution checkpoint） |
| — | REJECT | → 重新 solution（注入拒绝理由） |
| PASS | APPROVE | → delivery |
| PASS | REJECT | → 重新 review（强制 FAIL） |
| FAIL | —（不展示人类） | → code_gen（注入 AI 理由） |

### 暂停 / 恢复

- **预算超限**（时间/Token）→ 自动暂停，写盘 `tmp/<id>/pipeline_<id>.json`
- **LLM API 瞬态故障** → `max_retry` 次指数退避重试，耗尽后终止
- **恢复** → `python cli.py --resume <id>` 从断点继续

---

## 工具 × Stage 矩阵

| 工具 | req | sol | code | test | rev | deliv |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| AskUserQuestion | ✓ | | | | | |
| Read | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Edit | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Write | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Glob | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Grep | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Bash | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| SpawnSubAgent | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| WebSearch | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| WebFetch | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| ToolSearch | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| git_cmd_exec | | | | | | ✓ |

---

## 配置参考

### settings.json

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `workspace` | `"./out"` | 代码产出根目录 |
| `log_dir` | `"tmp"` | 日志/暂停文件目录 |
| `skip_checkpoints` | `false` | 跳过所有人工确认 |
| `max_total_time_ms` | `600000` | 累计耗时上限（ms） |
| `max_total_tokens` | `50000` | 累计 Token 上限 |
| `max_retry` | `3` | LLM API 重试次数 |
| `temperature` | `0.3` | LLM 温度 |
| `max_tool_iterations` | `20` | 单 stage 工具循环上限 |
| `preserve_session` | `false` | 完成后保留暂停文件 |
| `verbose` | `false` | 完整 LLM 日志 |

### model.json

| 字段 | 说明 |
|------|------|
| `API_KEY` | OpenAI 兼容 API Key |
| `BASE_URL` | API 地址 |
| `MODEL` | 模型名（如 `deepseek-v4-flash`） |

---

## 运行测试

```bash
pytest test/test_pipeline.py -v
```

---

## 路线图

- [x] Pipeline 引擎 + 6 个 Agent + 工具调用循环
- [x] Checkpoint 人类审批（solution + review）
- [x] 暂停/恢复（预算控制 + 磁盘持久化）
- [x] 子 Agent 并行（SpawnSubAgent）
- [x] workspace 可交付代码
- [ ] Golang RESTful API（12 端点 + Swagger）
- [ ] 前端 Dashboard + 圈选功能
- [ ] Git 集成（自动分支/提交/PR）
