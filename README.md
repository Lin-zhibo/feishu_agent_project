# DevFlow Engine

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
│   ├── model.json           # API key / base URL / model name
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