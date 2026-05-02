最终版前端会按正式 Pipeline 控制台来做。

接口先定成下面这一套：

1. 获取 Pipeline 配置
   `GET /api/pipeline/config`

2. 获取 Agent 配置
   `GET /api/agents`

3. 获取 LLM Provider
   `GET /api/providers`

4. 启动 Pipeline
   `POST /api/pipeline/runs`

5. 查询运行状态
   `GET /api/pipeline/runs/{run_id}`

6. 暂停
   `POST /api/pipeline/runs/{run_id}/pause`

7. 恢复
   `POST /api/pipeline/runs/{run_id}/resume`

8. 终止
   `POST /api/pipeline/runs/{run_id}/terminate`

9. 检查点通过
   `POST /api/pipeline/runs/{run_id}/checkpoints/{checkpoint_id}/approve`

10. 检查点驳回
    `POST /api/pipeline/runs/{run_id}/checkpoints/{checkpoint_id}/reject`

前端公网地址是：

`https://feishu-agent-project.vercel.app`

后端需要允许这个地址跨域访问。

