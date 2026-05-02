import { useEffect, useMemo, useState } from "react";
import "./App.css";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const defaultStages = [
  {
    id: "requirements",
    name: "需求分析",
    order: 1,
    depends_on: [],
    agents: ["Requirement Agent"],
    checkpoint: false,
    desc: "理解用户需求，拆解功能点、边界条件和验收标准。",
  },
  {
    id: "solution",
    name: "方案设计",
    order: 2,
    depends_on: ["requirements"],
    agents: ["Architect Agent"],
    checkpoint: true,
    desc: "生成技术方案、模块划分、数据流设计和实现路线。",
  },
  {
    id: "code_gen",
    name: "代码生成",
    order: 3,
    depends_on: ["solution"],
    agents: ["Coder Agent", "Test Agent"],
    checkpoint: false,
    desc: "根据方案生成代码变更，并输出核心文件修改说明。",
  },
  {
    id: "test_gen",
    name: "测试生成",
    order: 4,
    depends_on: ["code_gen"],
    agents: ["Test Agent"],
    checkpoint: false,
    desc: "生成测试用例、验证步骤和回归测试建议。",
  },
  {
    id: "review",
    name: "代码审查",
    order: 5,
    depends_on: ["test_gen"],
    agents: ["Review Agent"],
    checkpoint: true,
    desc: "检查代码质量、安全风险、可维护性和潜在问题。",
  },
  {
    id: "delivery",
    name: "交付集成",
    order: 6,
    depends_on: ["review"],
    agents: ["Delivery Agent"],
    checkpoint: false,
    desc: "整理最终产物、运行说明、交付文档和代码变更摘要。",
  },
];

const mockRunStatus = {
  success: true,
  run_id: "mock_run_001",
  status: "waiting_checkpoint",
  current_stage: "solution",
  stages: [
    {
      id: "requirements",
      name: "需求分析",
      status: "completed",
      duration: 8.2,
      tokens: 1200,
      output:
        "已完成需求分析：用户希望构建一个 AI DevFlow 前端控制台，支持 Pipeline 阶段展示、Agent 编排、模型选择、人工检查点和运行状态可视化。",
    },
    {
      id: "solution",
      name: "方案设计",
      status: "waiting_checkpoint",
      duration: 12.5,
      tokens: 1800,
      output:
        "方案设计结果：前端采用 React + Vite 实现，页面划分为需求输入区、Pipeline 配置区、Agent 配置区、运行状态区、检查点审批区和可观测性面板。",
    },
    {
      id: "code_gen",
      name: "代码生成",
      status: "pending",
      duration: 0,
      tokens: 0,
      output: "",
    },
    {
      id: "test_gen",
      name: "测试生成",
      status: "pending",
      duration: 0,
      tokens: 0,
      output: "",
    },
    {
      id: "review",
      name: "代码审查",
      status: "pending",
      duration: 0,
      tokens: 0,
      output: "",
    },
    {
      id: "delivery",
      name: "交付集成",
      status: "pending",
      duration: 0,
      tokens: 0,
      output: "",
    },
  ],
  checkpoint: {
    id: "checkpoint_solution",
    stage_id: "solution",
    title: "方案设计审批",
    artifact:
      "当前方案已经生成，请人工确认是否继续进入代码生成阶段。如果方案不完整，可以填写 Reject 理由并退回重做。",
    status: "pending",
  },
};

function App() {
  const [requirement, setRequirement] = useState("");
  const [templateId, setTemplateId] = useState("feature-dev");
  const [provider, setProvider] = useState("deepseek");
  const [model, setModel] = useState("deepseek-chat");
  const [repoPath, setRepoPath] = useState("");
  const [includePaths, setIncludePaths] = useState("frontend/src, pipeline, agents");

  const [runId, setRunId] = useState("");
  const [runStatus, setRunStatus] = useState(null);
  const [running, setRunning] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [message, setMessage] = useState("");

  const stages = useMemo(() => {
    if (runStatus?.stages?.length) {
      return defaultStages.map((stage) => {
        const realStage = runStatus.stages.find((item) => item.id === stage.id);
        return {
          ...stage,
          ...realStage,
        };
      });
    }

    return defaultStages.map((stage) => ({
      ...stage,
      status: "pending",
      duration: 0,
      tokens: 0,
      output: "",
    }));
  }, [runStatus]);

  const currentCheckpoint = runStatus?.checkpoint;

  const getStatusText = (status) => {
    const map = {
      pending: "等待中",
      running: "运行中",
      completed: "已完成",
      failed: "失败",
      paused: "已暂停",
      waiting_checkpoint: "等待人工确认",
      terminated: "已终止",
    };

    return map[status] || "等待中";
  };

  const getStatusClass = (status) => {
    if (status === "completed") return "done";
    if (status === "running") return "running";
    if (status === "waiting_checkpoint") return "checkpoint";
    if (status === "failed" || status === "terminated") return "failed";
    if (status === "paused") return "paused";
    return "pending";
  };

  const startPipeline = async () => {
    if (!requirement.trim()) {
      alert("请先输入需求描述");
      return;
    }

    setRunning(true);
    setMessage("正在启动 Pipeline...");
    setRunStatus(null);
    setRunId("");

    const payload = {
      requirement,
      template_id: templateId,
      provider,
      model,
      repo_context: {
        repo_path: repoPath,
        include_paths: includePaths
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
      },
    };

    try {
      const response = await fetch(`${API_BASE_URL}/api/pipeline/runs`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error("启动 Pipeline 失败");
      }

      const data = await response.json();

      if (!data.success) {
        throw new Error(data.message || "Pipeline 启动失败");
      }

      setRunId(data.run_id);
      setMessage(`Pipeline 已启动，运行 ID：${data.run_id}`);

      await fetchRunStatus(data.run_id);
    } catch (error) {
      console.error(error);

      setMessage(
        "当前后端接口暂未连通，已切换为前端模拟运行状态。后端完成后会自动接真实接口。"
      );

      setRunId("mock_run_001");
      setRunStatus(mockRunStatus);
    } finally {
      setRunning(false);
    }
  };

  const fetchRunStatus = async (targetRunId = runId) => {
    if (!targetRunId) return;

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/pipeline/runs/${targetRunId}`
      );

      if (!response.ok) {
        throw new Error("查询运行状态失败");
      }

      const data = await response.json();

      if (!data.success) {
        throw new Error(data.message || "查询运行状态失败");
      }

      setRunStatus(data);
    } catch (error) {
      console.error(error);
      setMessage("状态查询失败，当前显示模拟数据。");
      setRunStatus(mockRunStatus);
    }
  };

  const pausePipeline = async () => {
    if (!runId) return;

    try {
      await fetch(`${API_BASE_URL}/api/pipeline/runs/${runId}/pause`, {
        method: "POST",
      });

      setMessage("已发送暂停请求");
      await fetchRunStatus();
    } catch {
      setMessage("暂停接口暂未连通");
    }
  };

  const resumePipeline = async () => {
    if (!runId) return;

    try {
      await fetch(`${API_BASE_URL}/api/pipeline/runs/${runId}/resume`, {
        method: "POST",
      });

      setMessage("已发送恢复请求");
      await fetchRunStatus();
    } catch {
      setMessage("恢复接口暂未连通");
    }
  };

  const terminatePipeline = async () => {
    if (!runId) return;

    try {
      await fetch(`${API_BASE_URL}/api/pipeline/runs/${runId}/terminate`, {
        method: "POST",
      });

      setMessage("已发送终止请求");
      await fetchRunStatus();
    } catch {
      setMessage("终止接口暂未连通");
    }
  };

  const approveCheckpoint = async () => {
    if (!runId || !currentCheckpoint?.id) return;

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/pipeline/runs/${runId}/checkpoints/${currentCheckpoint.id}/approve`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            comment: "人工确认通过，可以继续执行",
          }),
        }
      );

      if (!response.ok) {
        throw new Error("审批通过失败");
      }

      setMessage("检查点已通过，Pipeline 继续执行");
      await fetchRunStatus();
    } catch {
      setMessage("Approve 接口暂未连通，当前为前端展示状态。");
    }
  };

  const rejectCheckpoint = async () => {
    if (!runId || !currentCheckpoint?.id) return;

    if (!rejectReason.trim()) {
      alert("请填写 Reject 理由");
      return;
    }

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/pipeline/runs/${runId}/checkpoints/${currentCheckpoint.id}/reject`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            reason: rejectReason,
          }),
        }
      );

      if (!response.ok) {
        throw new Error("驳回失败");
      }

      setMessage("检查点已驳回，Pipeline 将回退重做");
      setRejectReason("");
      await fetchRunStatus();
    } catch {
      setMessage("Reject 接口暂未连通，当前为前端展示状态。");
    }
  };

  useEffect(() => {
    if (!runId || runId.startsWith("mock")) return;

    const timer = setInterval(() => {
      fetchRunStatus(runId);
    }, 3000);

    return () => clearInterval(timer);
  }, [runId]);

  const totalTokens = stages.reduce((sum, stage) => sum + Number(stage.tokens || 0), 0);
  const completedCount = stages.filter((stage) => stage.status === "completed").length;

  return (
    <div className="page">
      <header className="topbar">
        <div>
          <div className="brand">AI DevFlow</div>
          <div className="subtitle">Pipeline 控制台 · Agent 编排 · Human-in-the-Loop</div>
        </div>

        <div className="top-actions">
          <span className="tag">API-First</span>
          <span className="tag">/plan 模式</span>
          <span className="tag">Feishu Style</span>
        </div>
      </header>

      <main className="dashboard">
        <section className="panel input-panel">
          <div className="panel-title">需求与运行配置</div>

          <label>需求描述</label>
          <textarea
            value={requirement}
            onChange={(e) => setRequirement(e.target.value)}
            placeholder="例如：为当前平台新增用户登录功能，包括前端页面、后端接口、测试用例和代码审查。"
          />

          <div className="form-row">
            <div>
              <label>Pipeline 模板</label>
              <select value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
                <option value="feature-dev">新功能开发流程</option>
                <option value="bug-fix">Bug 修复流程</option>
                <option value="refactor">重构流程</option>
              </select>
            </div>

            <div>
              <label>LLM Provider</label>
              <select value={provider} onChange={(e) => setProvider(e.target.value)}>
                <option value="deepseek">DeepSeek</option>
                <option value="openai">OpenAI</option>
              </select>
            </div>
          </div>

          <label>模型</label>
          <select value={model} onChange={(e) => setModel(e.target.value)}>
            {provider === "deepseek" ? (
              <>
                <option value="deepseek-chat">deepseek-chat</option>
                <option value="deepseek-coder">deepseek-coder</option>
              </>
            ) : (
              <>
                <option value="gpt-4o">gpt-4o</option>
                <option value="gpt-4.1">gpt-4.1</option>
              </>
            )}
          </select>

          <label>代码库路径</label>
          <input
            value={repoPath}
            onChange={(e) => setRepoPath(e.target.value)}
            placeholder="例如：F:/飞书ai/feishu_agent_project-main"
          />

          <label>上下文路径</label>
          <input
            value={includePaths}
            onChange={(e) => setIncludePaths(e.target.value)}
            placeholder="例如：frontend/src, pipeline, agents"
          />

          <button className="primary-btn" onClick={startPipeline} disabled={running}>
            {running ? "正在启动..." : "启动 Pipeline"}
          </button>

          <div className="lifecycle-buttons">
            <button onClick={pausePipeline} disabled={!runId}>暂停</button>
            <button onClick={resumePipeline} disabled={!runId}>恢复</button>
            <button onClick={terminatePipeline} disabled={!runId}>终止</button>
          </div>

          {message && <div className="message-box">{message}</div>}
        </section>

        <section className="panel stage-panel">
          <div className="panel-title">Pipeline 执行过程</div>

          <div className="run-meta">
            <div>
              <span>Run ID</span>
              <strong>{runId || "尚未启动"}</strong>
            </div>
            <div>
              <span>状态</span>
              <strong>{getStatusText(runStatus?.status || "pending")}</strong>
            </div>
            <div>
              <span>完成阶段</span>
              <strong>{completedCount}/{stages.length}</strong>
            </div>
            <div>
              <span>Token 消耗</span>
              <strong>{totalTokens}</strong>
            </div>
          </div>

          <div className="stage-list">
            {stages.map((stage, index) => (
              <div className="stage-card" key={stage.id}>
                <div className={`stage-dot ${getStatusClass(stage.status)}`}>
                  {stage.status === "completed" ? "✓" : index + 1}
                </div>

                <div className="stage-main">
                  <div className="stage-head">
                    <div>
                      <h3>{stage.name}</h3>
                      <p>{stage.desc}</p>
                    </div>

                    <span className={`status-pill ${getStatusClass(stage.status)}`}>
                      {getStatusText(stage.status)}
                    </span>
                  </div>

                  <div className="stage-info">
                    <span>依赖：{stage.depends_on?.length ? stage.depends_on.join(", ") : "无"}</span>
                    <span>Agent：{stage.agents?.join(" / ")}</span>
                    <span>耗时：{stage.duration || 0}s</span>
                    <span>Tokens：{stage.tokens || 0}</span>
                  </div>

                  {stage.output && <pre className="stage-output">{stage.output}</pre>}
                </div>
              </div>
            ))}
          </div>
        </section>

        <aside className="right-column">
          <section className="panel">
            <div className="panel-title">Human-in-the-Loop 检查点</div>

            {currentCheckpoint ? (
              <div className="checkpoint-box">
                <h3>{currentCheckpoint.title}</h3>
                <p>当前阶段：{currentCheckpoint.stage_id}</p>

                <div className="artifact">
                  {currentCheckpoint.artifact}
                </div>

                <textarea
                  className="reject-input"
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  placeholder="如果需要驳回，请填写 Reject 理由，例如：方案中缺少权限控制设计。"
                />

                <div className="checkpoint-actions">
                  <button className="approve-btn" onClick={approveCheckpoint}>
                    Approve 继续
                  </button>
                  <button className="reject-btn" onClick={rejectCheckpoint}>
                    Reject 回退
                  </button>
                </div>
              </div>
            ) : (
              <div className="empty-box">
                暂无人工检查点。Pipeline 运行到方案设计或代码审查阶段时，会在这里展示审批内容。
              </div>
            )}
          </section>

          <section className="panel">
            <div className="panel-title">Agent 编排</div>

            <div className="agent-list">
              {defaultStages.map((stage) => (
                <div className="agent-card" key={stage.id}>
                  <strong>{stage.name}</strong>
                  <p>{stage.agents.join(" / ")}</p>
                  <span>{stage.checkpoint ? "包含人工检查点" : "自动执行阶段"}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="panel">
            <div className="panel-title">可观测性面板</div>

            <div className="observe-grid">
              <div>
                <span>阶段总数</span>
                <strong>{stages.length}</strong>
              </div>
              <div>
                <span>已完成</span>
                <strong>{completedCount}</strong>
              </div>
              <div>
                <span>Token</span>
                <strong>{totalTokens}</strong>
              </div>
              <div>
                <span>检查点</span>
                <strong>2</strong>
              </div>
            </div>
          </section>
        </aside>
      </main>
    </div>
  );
}

export default App;
