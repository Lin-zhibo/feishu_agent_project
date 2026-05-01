我现在前端公网页面已经部署好了：
https://feishu-agent-project.vercel.app

目前只完成了前端公网部署，后端公网接口还没接。

接口我先定为：
POST /api/run

前端请求体：

```json
{
  "input": "用户输入的需求文本"
}
```

后端返回六个阶段结果：

```json
{
  "success": true,
  "message": "运行成功",
  "stages": {
    "requirements": "需求分析阶段输出",
    "solution": "方案设计阶段输出",
    "code_gen": "代码生成阶段输出",
    "test_gen": "测试生成阶段输出",
    "review": "代码审查阶段输出",
    "delivery": "交付集成阶段输出"
  },
  "final_output": "最终汇总结果"
}
```
