# 代码审查 Round 3 — Web Console 前端交付（M2-4e）

> 审查对象：services/web/src/（App/api/styles/main）+ 对接后端契约（routes/tasks.py、tasks.py、app.py）
> 验证：tsc 通过 + live 全链路（POST 202 / SSE / GET 详情与列表）。

## 结论

单页 React 壳整体健康，但发现 1 个架构级局部最优（假实时）与若干生命周期/健壮性缺口，已全部修复。

## 处置明细

| 编号 | 严重度 | 意见 | 处置 | 落实 |
| --- | --- | --- | --- | --- |
| L1 | 高危 | 假实时：POST 阻塞到任务完成，SSE 只是回放 | 后端 POST 立即返回 202 + asyncio 后台执行；SSE 轮询 events 实时推送（多客户端各带索引）；前端不再 await POST 结果 | 已修复 + 测试 |
| L2 | 高危 | SSE 生命周期裸奔（无卸载清理/无错误提示/无取消/无超时） | SSE 移入 useEffect（依赖 task_id，清理自动 close）；取消按钮；30s stall 超时；onerror 显式错误卡（finished/closed 守卫防误报） | 已修复 |
| L3 | 中 | 前后端能力不对齐（maxSteps 硬编码、无 thread、无历史入口） | 前端 maxSteps/thread_id 输入 + 最近任务历史面板（GET /v1/tasks），点击可重连 | 已修复 |
| L4 | 中 | 流事件无防御（JSON.parse 裸奔、node 字段异常崩回调） | parseSSE try/catch + Array.isArray(node) 防御 | 已修复 |
| 问题2 | 中 | 超长内容无上限/无滚动/无折叠 | pre max-height:320px + overflow:auto；>2000 字符折叠+展开；timeline 自动滚底；textarea maxLength=10000 | 已修复 |
| 问题3 | 中 | 刷新全部丢失，无恢复路径 | 新增 GET /v1/tasks/{id}；前端 URL #task= + localStorage，刷新自动重连 SSE + 回放 | 已修复 |
| 问题4 | - | 无切换场景；先排雷（SSE effect 化） | L2 已把 SSE 改为 effect 管理，后续引入 modal/路由不再泄漏 | 已排雷 |

## 做得好（保留）
- 199→406 行仍单文件可读，StepCard/ResultCard/CodeBlock 纯展示组件
- api.ts 统一 json() 错误映射（detail.message 兜底）
- running 禁连点、新任务清空旧轨迹、取消按钮

## Round 4 复查清单
- [ ] 接真实 LLM 后验证：POST 立即返回 + SSE 逐事件推送，白屏期消除（L1 终验）
- [ ] 多实例部署时任务存储迁移 Redis/DB（L1 进程内 dict 上限）
- [ ] 引入 modal/路由前，先确认 SSE 依赖边界（已 effect 化，✅）
