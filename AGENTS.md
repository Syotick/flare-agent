# AGENTS.md — Flare Agent 项目记忆（标准版）

> 与 CLAUDE.md 同源，供所有支持 AGENTS.md 的 Agent 工具读取。
> 变更时两处同步。

## 项目目标
企业级 AI Agent 平台，对标 Codex / Claude Code / DeepSeek Harness，
可上线、高可用、可拓展、可运维，估算并发百万级，部署阿里云，对象存储用阿里云 OSS，
集成 RAG / MCP / Skills / 工具系统 / 沙箱 / 记忆等先进能力。非 demo。

## 关键约束
1. 生产级（可部署、可监控、可回滚、可审计）
2. 高可用（多可用区、无单点）
3. 弹性扩展到百万级并发
4. 组件化可插拔（Tools / MCP / Skills / RAG）
5. 多模型可路由
6. 阿里云 OSS 存对象
7. 强企业级技术栈，云原生

## 当前进度
- 阶段 0 完成：Git 仓库 + GitHub 私有仓库（Syotick/flare-agent）+ 文档骨架 + 记忆
- 下一步：等待用户确认需求 → 阶段 1 需求/架构评审

## 目录速览
- `docs/research/` — 市场与技术调研报告
- `docs/requirements/` — 开发需求说明书
- `docs/architecture/` — 架构总览
- `CLAUDE.md` — 详细项目记忆（唯一权威源）

## 待决策
技术栈定夺、阿里云凭证、产品形态优先级、租户模型、预算/模型供应商、沙箱合规、运维人力。
