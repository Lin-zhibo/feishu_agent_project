# DevFlow Engine：基于 AI 驱动的需求交付流程引擎

## directory

```
feishu_agent_project/
├── agents/                  # 6 LLM agents (wrapped LangChain RunnableSequences)
│   └── __init__.py         # Agent entry points (run_requirements, run_solution, ...)
├── chains/                  # LangChain RunnableSequence factories (one per stage)
│   ├── __init__.py
│   ├── requirements_chain.py
│   ├── solution_chain.py
│   ├── code_gen_chain.py
│   ├── test_gen_chain.py
│   ├── review_chain.py
│   └── delivery_chain.py
├── config/
│   ├── model.json           # LLM API key / base URL / model name
│   └── settings.json        # Pipeline stage toggles, output dir
├── doc/
│   └── TODO.md              # Development progress tracker
├── out/                     # Pipeline output artifacts (auto-created)
├── pipeline/                # Pipeline engine and data models
│   ├── __init__.py
│   ├── engine.py            # Stage orchestration (SequentialChain driver)
│   ├── models.py            # PipelineConfig, PipelineState, StageInput, StageOutput
│   └── config_loader.py     # JSON config loader with env var override
├── prompts/                  # LangChain PromptTemplate definitions (one per stage)
│   ├── __init__.py
│   ├── requirements.py
│   ├── solution.py
│   ├── code_gen.py
│   ├── test_gen.py
│   ├── review.py
│   └── delivery.py
├── test/
│   └── test_pipeline.py     # Models, config, agents, chains, prompts tests
├── tools/
│   ├── shell_exec.py        # Shell execution tool
│   └── web_search.py        # Web search tool
├── cli.py                   # CLI entry point
├── main.py                  # Top-level run_pipeline() wrapper
├── CLAUDE.md                # Project instructions (Chinese)
└── README.md
```



## Quick to Start

**config/model.json**

```json
{
    "API_KEY": "<your api key>",
    "BASE_URL": "<model base url>",
    "MODEL": "<model name>"
}
```

### config/ 目录说明

- `config/settings.json` — 项目配置，包含 Pipeline 各阶段开关 (`stage_enabled`) 和输出目录 (`output_dir`)
- `config/model.json` — 大模型相关配置，包含 API Key、Base URL、Model 名称



## Workflow

```mermaid
flowchart TB
    subgraph INPUT
        A["User Input<br/>'用户登录功能'"]
    end

    subgraph STAGE_1["Stage 1: Requirements"]
        R1["run_requirements<br/>requirements_chain"]
        R2["StageOutput<br/>content: str<br/>artifacts: dict"]
    end

    subgraph STAGE_2["Stage 2: Solution"]
        S1["run_solution<br/>solution_chain"]
        S2["StageOutput<br/>content: solution<br/>artifacts: dict"]
        CP1["Checkpoint<br/>confirm_checkpoint"]
    end

    subgraph STAGE_3["Stage 3: Code Gen"]
        C1["run_code_gen<br/>code_gen_chain"]
        C2["StageOutput<br/>content: code_diff<br/>artifacts: dict"]
    end

    subgraph STAGE_4["Stage 4: Test Gen"]
        T1["run_test_gen<br/>test_gen_chain"]
        T2["StageOutput<br/>content: test_code<br/>artifacts: dict"]
    end

    subgraph STAGE_5["Stage 5: Review"]
        R5["run_review<br/>review_chain"]
        R6["StageOutput<br/>content: review_report<br/>review_decision: ReviewDecision"]
        CP2["Checkpoint<br/>AI Decision + Human Override"]
    end

    subgraph STAGE_6["Stage 6: Delivery"]
        D1["run_delivery<br/>delivery_chain"]
        D2["StageOutput<br/>content: final_output<br/>artifacts: dict"]
    end

    subgraph STATE["PipelineState (累积)"]
        PS1["requirements: str"]
        PS2["solution: str"]
        PS3["code_diff: str"]
        PS4["test_code: str"]
        PS5["review_report: str<br/>review_decision: ReviewDecision"]
        PS6["final_output: str"]
    end

    A --> R1
    R1 --> R2
    R2 --> PS1

    PS1 --> S1
    S1 --> S2
    S2 --> PS2
    PS2 --> CP1

    CP1 -->|APPROVE| C1
    CP1 -->|REJECT| S1

    PS2 --> C1
    C1 --> C2
    C2 --> PS3

    PS3 --> T1
    T1 --> T2
    T2 --> PS4

    PS4 --> R5
    R5 --> R6
    R6 --> PS5

    PS5 --> CP2

    CP2 -->|AI PASS + Human APPROVE| D1
    CP2 -->|AI FAIL + Human OVERRIDE| D1
    CP2 -->|AI PASS + Human REJECT| R5
    CP2 -->|AI FAIL + Human REJECT| C1

    PS2 --> D1
    D1 --> D2
    D2 --> PS6

    style PS6 fill:#90EE90
    style CP1 fill:#FFE4B5
    style CP2 fill:#FFE4B5
```

### PipelineState 字段生命周期

| 字段 | 生命周期 | 说明 |
|------|---------|------|
| `original_input` | 始终 | 用户原始需求 |
| `requirements` | S1→S2→... | 需求分析输出 |
| `solution` | S2→S3→... | 方案设计输出 |
| `code_diff` | S3→S4→S5→... | 代码 diff |
| `test_code` | S4→S5→... | 测试代码 |
| `review_report` | S5→S6 | 审查报告 |
| `review_decision` | S5→CP2 | AI 判断 + 人类Override |
| `final_output` | S6结束 | 最终交付物 |

### Review Checkpoint 状态机

| AI 判断 | 人类操作 | 路由 |
|---------|---------|------|
| PASS | APPROVE | → delivery |
| FAIL | OVERRIDE | → delivery (allow_human_override=true) |
| PASS | REJECT | → 重新 review |
| FAIL | REJECT | → code_gen |

