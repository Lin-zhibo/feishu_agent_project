# TODO

## 已完成

- **修复工具调用循环缺失 + DeepSeek reasoning_content 400 错误**：重构 agent loop，使用原生 API dict 消息格式
  - 新增 `agents/_tool_runner.py`（使用 `llm.async_client` + 纯 dict 消息 + `model_dump()` 保留所有 provider 专有字段）
  - 修改 6 个 `agents/*.py`（`run_*()` 均使用新 utility）
  - 修改 `test/test_pipeline.py`（mock `invoke_agent_with_tools`）
  - 解决已知问题：#1 requirements 阶段输出残缺、#2 astream() 工具调用失效
  - 修复：reasoning_content 在工具调用后第二轮请求时丢失导致 400 错误（DeepSeek thinking mode 兼容）
  - 通用方案：不绑定任何单一 provider，任何 OpenAI 兼容 API 的专有字段均可完整保留

- **AskUserQuestion 多选支持**：新增 `multiselect` 参数，支持编号多选
  - `tools/ask_user.py`：新增 `multiselect: bool = False` 参数 + `_parse_multiselect()` 解析函数
  - 多选时显示编号列表，用户输入逗号分隔的数字或选项文本
  - 支持 `1,3,5` 数字索引和 `收入/支出记录, 分类管理` 文本两种输入方式
  - 19 个测试全部通过

- **Checkpoint 流程重构 + 资源预算控制 + 暂停/恢复 + LLM 重试**：
  - Review 简化：AI FAIL → 自动跳 code_gen；AI PASS → 人类审批（Y→delivery / n→review 重跑强制 FAIL+修复方案）
  - Solution：拒绝理由通过 `human_feedback` 注入 agent 输入
  - 预算超限 → 暂停写盘（`out/pipeline_<id>.json`），可通过 `--resume` 恢复
  - LLM API 瞬态故障 → `max_retry`=3 指数退避重试（1s/2s/4s），耗尽 → RuntimeError 终止
  - 新增 CLI：`--resume [id]` / `--list` / `--terminate <id>` / `--terminate-all`
  - `settings.json` 新增 `max_retry: 3`；删除 `allow_human_override_on_ai_fail`
  - `PipelineState` 新增 `pipeline_id` / `current_stage_idx` / `paused_at` / `pause_reason`
  - `engine.py` 新增 `resume()` + `_try_pause()` + pause 文件管理 helpers
  - `_tool_runner.py` 新增 `_call_llm_with_retry()` 指数退避
  - 19 个测试全部通过，ruff 零告警

- **新增 4 个用户配置项 + 删除 stage_enabled**：
  - `config/settings.json`：新增 `temperature: 0.3` / `max_tool_iterations: 20` / `preserve_session: false` / `verbose: false`；删除 `stage_enabled` 块
  - `pipeline/models.py`：`PipelineConfig` 新增对应 4 个字段
  - `pipeline/config_loader.py`：加载 4 个新字段
  - `agents/_tool_runner.py`：`invoke_agent_with_tools()` 新增 `max_tool_iterations` / `verbose` 参数，删除 `MAX_TOOL_ITERATIONS` 常量；`verbose` 时打全量 LLM 请求响应日志
  - 6 个 `agents/*.py`：`ChatOpenAI` 构造改为 `temperature=inp.config.temperature`；`invoke_agent_with_tools()` 调用新增 `max_tool_iterations=inp.config.max_tool_iterations` / `verbose=inp.config.verbose`
  - `pipeline/engine.py`：`preserve_session`=true 时跳过 `_cleanup_paused_state`
  - 19 个测试全部通过，ruff 零告警

- **文件交互工具增强 + 新增 Glob/Grep/Bash**：
  - `tools/file_ops.py`：`Read` 新增 `offset`/`limit` 参数、二进制检测；`Edit` 新增 `replace_all` 参数
  - 新增 `tools/glob.py`（`Glob`）：文件模式匹配，自动跳过 .git/node_modules 等目录，限 200 条
  - 新增 `tools/grep.py`（`Grep`）：正则内容搜索，支持 `include` 文件过滤，限 100 条
  - 新增 `tools/bash.py`（`Bash`）：增强版 shell_exec，新增 `description`/`workdir`/`timeout`，Y/n 确认
  - `tools/__init__.py` 重构 stage 工具分配：AskUserQuestion 仅 requirements；git_cmd_exec 仅 delivery；其余全 stage 通用
  - 19 个测试全部通过，ruff lint 零告警

- **Review 阶段增强**：实现 AI 判断 + 人类审核的两阶段 checkpoint
  - `pipeline/models.py`：新增 `ReviewDecision` 数据结构、`allow_human_override_on_ai_fail` 配置开关
  - `prompts/review.py`：修改 prompt 要求结构化 VERDICT 输出（PASS/FAIL + Reason + Critical Issues）
  - `agents/__init__.py`：新增 `_parse_review_decision()` 解析函数，填充 `StageOutput.review_decision`
  - `pipeline/checkpoint.py`：`confirm_checkpoint` 支持展示 AI 判断结果（VERDICT 显示 + 不同操作提示）
  - `pipeline/engine.py`：实现两阶段 checkpoint 状态机（AI PASS/FAIL + 人类审核组合）
  - `config/settings.json`：新增 `skip_checkpoints`、`allow_human_override_on_ai_fail` 配置项
  - `pipeline/config_loader.py`：加载新配置项
  - 19 个测试全部通过

- **Pipeline 运行状态实时可视化**：每次 LLM 调用后输出耗时、Token 消耗、累计总量
  - 新增 `pipeline/callbacks.py`（`PipelineCallbackHandler`，基于 LangChain `BaseCallbackHandler`）
  - 修改 `agents/__init__.py`（为 6 个 agent 函数添加 `callbacks` 参数）
  - 修改 `pipeline/engine.py`（注入 handler，输出每个 Stage 可视化块 + Pipeline 汇总）
  - 19 个测试全部通过

- **LangChain 重构（升级到 RunnableSequence）**：将 Pipeline 从直接调用 `openai.AsyncOpenAI` 改为使用 LangChain
  - 升级 `LLMChain` → `RunnableSequence`（`prompt | llm` 语法）
  - 升级 `arun()` → `ainvoke()`（返回 `AIMessage`，需提取 `.content`）
  - 新增 `prompts/` 模块（6 个 `PromptTemplate`）
  - 新增 `chains/` 模块（6 个 `LLMChain` 工厂函数）
  - 重写 `agents/__init__.py`（包装 chains 为 async run 函数）
  - 删除旧 agent 文件（ReqirementsAnalysis.py 等 6 个）
  - 删除旧 `prompt/template.py`
  - 更新 `test/test_pipeline.py`（mock 改为 `MagicMock` + patch 工厂函数）

- **最小化 Pipeline 搭建**：完成 6 阶段 Pipeline 的基础结构
  - 新增 `pipeline/` 目录（models.py, engine.py, config_loader.py, __init__.py）
  - 新增 `agents/` 目录（requirements.py, solution.py, code_gen.py, test_gen.py, review.py, delivery.py, __init__.py）
  - 新增 `config/settings.json`（Pipeline 全局配置）
  - 修改 `prompt/template.py`（Python dict 存储 6 阶段 prompt 模板）
  - 新增 `out/` 目录（Pipeline 输出目录）
  - 新增 `cli.py`（CLI 入口，支持 --skip-* 和 --output-dir）
  - 新增 `main.py`（最上层封装）
  - 新增 `test/test_pipeline.py`（冒烟测试，7 个用例全部通过）

## 当前状态

- Pipeline 基础架构已完整搭建，CLI 可运行
- 6 个 Agent 均使用 `invoke_agent_with_tools()` 实现工具调用循环
- Agent loop 使用原生 `llm.async_client` API 调用 + 纯 dict 消息格式，保证所有 provider 专有字段（如 reasoning_content）完整保留
- 每个 agent 使用各自 stage 的专属工具集（`STAGE_TOOLS[stage_name]`）
- 测试覆盖：models 创建、config 验证、Agent mock 测试、chain 创建、prompt 变量
- 新增实时可视化回调，输出格式示例：
  - 每个 Stage：`┌─ Stage: requirements ───────────────────── [SUCCESS] ─┐ │ Time: 1,234 ms │ Tokens: prompt=128 | completion=64 | total=192 │ Cumulative: time=1,234ms | tokens=192 └─────────────┘`
  - 汇总：`═══════════════════════════════════════════════════════ Pipeline Summary Total Time: 8,456 ms Total Tokens: prompt=1,024 | completion=512 | total=1,536 ════════════════════════════════════════════════════════`
- 已实现 10 个工具并集成到相关 stage 的工具集

## 已知问题

- Agent 之间传递的 `previous_output` 目前仅传递 `requirements` 和 `solution`，其他字段依赖 engine 中的累积字典

## 下一步

- [ ] 配置真实 API Key 并端到端测试 `python cli.py --input "用户登录功能"`
- [ ] 实现输出文件的实际写入逻辑（out/ 目录）
- [ ] 补充 Agent 间更多上下文传递
- [ ] 添加集成测试或 E2E 测试