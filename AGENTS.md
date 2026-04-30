# Agent Behavior Guide

## Core Beliefs
- 交付物是**可运行的代码文件**，不是文档
- 遇到歧义先澄清（AskUserQuestion），不猜测
- 多用子 agent 并行：一个文件 = 一个 SpawnSubAgent
- 渐进式加载：先从本文件获取方向，再去 docs/ 查细节

## Knowledge Map
| 需要了解 | 去看 |
|----------|------|
| 系统架构 | docs/ARCHITECTURE.md |
| 设计原则 | docs/DESIGN.md |
| 产品需求 | docs/product-specs/ |
| 当前执行计划 | docs/exec-plans/active/ |
| 安全规范 | docs/SECURITY.md |
| 技术参考 | docs/references/ |

## Sub-Agent Types
| 类型 | 工具 | 用途 |
|------|------|------|
| file-writer | Write | 创建单个文件（只写不读） |
| code-reviewer | Read, Grep | 审查指定文件 |
| test-writer | Read, Write, Bash | 写测试 + 运行 + 修复 |
| researcher | WebSearch, WebFetch | 技术调研 |

完整规范见 docs/SUB_AGENTS.md

## Tool Rules
- **SpawnSubAgent**：多文件操作必须用，1 文件 = 1 子 agent
- **Write / Edit**：只改 workspace 内的文件
- **Bash**：仅用于运行测试/构建，不安装依赖
- **AskUserQuestion**：仅 requirements 阶段可用
- **git_cmd_exec**：仅 delivery 阶段可用

## Workspace
- 所有文件操作在 working directory（见 Context）下进行
- 绝对路径以 `out/<timestamp>/` 开头

## Pipeline
```
requirements → solution → [Checkpoint ①] → code_gen → test_gen → review → [Checkpoint ②] → delivery
```
