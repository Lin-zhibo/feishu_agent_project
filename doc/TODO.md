# TODO

## 已完成

- **LangChain 重构（升级到 RunnableSequence）**：将 Pipeline 从直接调用 `openai.AsyncOpenAI` 改为使用 LangChain
  - 升级 `LLMChain` → `RunnableSequence`（`prompt | llm` 语法）
  - 升级 `arun()` → `ainvoke()`（返回 `AIMessage`，需提取 `.content`）
  - 新增 `prompts/` 模块（6 个 `PromptTemplate`）
  - 新增 `chains/` 模块（6 个 `LLMChain` 工厂函数）
  - 重写 `agents/__init__.py`（包装 chains 为 async run 函数）
  - 删除旧 agent 文件（ReqirementsAnalysis.py 等 6 个）
  - 删除旧 `prompt/template.py`
  - 更新 `test/test_pipeline.py`（mock 改为 `MagicMock` + patch 工厂函数）
  - 19 个测试全部通过

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
- 6 个 Agent 已实现，均调用 DeepSeek API
- 测试覆盖：models 创建、config 验证、Agent mock 测试

## 已知问题

- 需要真实 API Key 才能端到端运行（当前配置从 config/model.json 读取）
- Agent 之间传递的 `previous_output` 目前仅传递 `requirements` 和 `solution`，其他字段依赖 engine 中的累积字典

## 下一步

- [ ] 配置真实 API Key 并端到端测试 `python cli.py --input "用户登录功能"`
- [ ] 实现输出文件的实际写入逻辑（out/ 目录）
- [ ] 补充 Agent 间更多上下文传递
- [ ] 添加集成测试或 E2E 测试
