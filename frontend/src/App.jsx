import { useState } from "react";
import "./App.css";

const stageList = [
  {
    key: "requirements",
    title: "需求分析",
    desc: "理解用户输入，提取功能点、使用场景和约束条件。",
  },
  {
    key: "solution",
    title: "方案设计",
    desc: "规划整体实现思路，包括页面结构、组件划分和数据流。",
  },
  {
    key: "code_gen",
    title: "代码生成",
    desc: "根据方案生成核心代码和项目文件。",
  },
  {
    key: "test_gen",
    title: "测试生成",
    desc: "生成测试思路、测试用例或验证步骤。",
  },
  {
    key: "review",
    title: "代码审查",
    desc: "检查代码问题、结构问题和潜在风险。",
  },
  {
    key: "delivery",
    title: "交付集成",
    desc: "整理最终结果，形成可交付内容。",
  },
];

function App() {
  const [input, setInput] = useState("");
  const [running, setRunning] = useState(false);
  const [activeStage, setActiveStage] = useState(-1);
  const [outputs, setOutputs] = useState({});

  const handleRun = async () => {
  if (!input.trim()) {
    alert("请先输入一个需求");
    return;
  }

  setRunning(true);
  setActiveStage(0);
  setOutputs({});

  try {
    // 这里是为了让前端看起来有“执行过程”
    // 后端真正结果还没返回前，前端先显示阶段推进
    const progressTimer = setInterval(() => {
      setActiveStage((prev) => {
        if (prev >= stageList.length - 1) {
          return prev;
        }
        return prev + 1;
      });
    }, 1200);

    // 请求后端接口
    const response = await fetch("http://localhost:8000/api/run", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        input: input,
      }),
    });

    clearInterval(progressTimer);

    if (!response.ok) {
      throw new Error("后端接口请求失败");
    }

    const data = await response.json();

    if (!data.success) {
      throw new Error(data.message || "Pipeline 运行失败");
    }

    setActiveStage(stageList.length - 1);

    setOutputs({
      requirements: data.stages.requirements || "",
      solution: data.stages.solution || "",
      code_gen: data.stages.code_gen || "",
      test_gen: data.stages.test_gen || "",
      review: data.stages.review || "",
      delivery: data.stages.delivery || "",
    });
  } catch (error) {
    console.error(error);
    alert("运行失败：" + error.message);
  } finally {
    setRunning(false);
  }
};

  const getStageStatus = (index, key) => {
    if (outputs[key]) return "done";
    if (running && activeStage === index) return "running";
    return "waiting";
  };

  return (
    <div className="page">
      <header className="header">
        <div>
          <div className="logo">DevFlow</div>
          <div className="sub-title">AI 驱动的需求交付流程引擎</div>
        </div>

        <div className="header-badge">/plan 模式</div>
      </header>

      <main className="layout">
        <section className="left-panel card">
          <div className="section-title">输入需求</div>

          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="例如：帮我生成一个用户登录功能，包括前端页面、接口设计、测试用例和代码审查。"
          />

          <button onClick={handleRun} disabled={running}>
            {running ? "正在运行 Pipeline..." : "开始生成计划"}
          </button>

          <div className="tip">
            当前版本先用前端模拟流程，后面再对接 Python Pipeline 接口。
          </div>
        </section>

        <section className="center-panel card">
          <div className="section-title">执行过程</div>

          <div className="timeline">
            {stageList.map((stage, index) => {
              const status = getStageStatus(index, stage.key);

              return (
                <div className="timeline-item" key={stage.key}>
                  <div className={`dot ${status}`}>
                    {status === "done" ? "✓" : index + 1}
                  </div>

                  <div className="stage-content">
                    <div className="stage-header">
                      <span>{stage.title}</span>
                      <span className={`status ${status}`}>
                        {status === "done"
                          ? "已完成"
                          : status === "running"
                          ? "进行中"
                          : "等待中"}
                      </span>
                    </div>

                    <p>{stage.desc}</p>

                    {outputs[stage.key] && (
                      <pre>{outputs[stage.key]}</pre>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        <section className="right-panel card">
          <div className="section-title">最终结果</div>

          {Object.keys(outputs).length === 0 ? (
            <div className="empty">
              运行后，这里会展示每个阶段的输出结果。
            </div>
          ) : (
            <div className="result-list">
              {stageList.map((stage) => (
                <div className="result-card" key={stage.key}>
                  <div className="result-title">{stage.title}</div>
                  <div className="result-text">
                    {outputs[stage.key] || "等待生成..."}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;
