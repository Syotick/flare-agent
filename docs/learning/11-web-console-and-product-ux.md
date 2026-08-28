# Flare Agent · Web 控制台与产品化 UX（实践 + 真理）

> 版本：v1.0 ｜ 日期：2026-08-28 ｜ 状态：draft
> 定位：M3a/M3b 配套 + 产品化教学文档——管理页怎么建、会话切换为什么这样设计、
> 为什么不能把工程参数（max_steps / thread_id）暴露给用户。
> 配套：01-Web Console 用户功能清单（features）、08-技术架构 §4（前端）、ADR-0012（前端形态：本地 Web 优先）。

---

## 1. Web 控制台定位与形态（真理先行）

- 真理：控制台是 Agent 平台的**门面**——最终用户只看到它。它必须：
  1. 把"能力"翻译成用户能懂的动作（对话、建知识库、看记忆），而不是让用户看见内部接口；
  2. 一个页面管一件事（单一职责），导航清晰；
  3. 后台完成的事（分块、向量化、线程续聊、评测打分）在界面上如实呈现结果，不暴露过程参数。
- 形态（ADR-0012 落地）：本地 Web 优先——React 18 + Vite 5 + Tailwind 4 + Radix UI 原语，
  构建产物 `services/web/dist` 由后端 main.py 在 `/` 挂载（StaticFiles 按磁盘读取，**改 dist 无需重启后端**）。
- 访问：生产/本地后端端口 **8000**（非 3080——DSH 控制台占用了 3080，本项目绝不碰）；
  开发热更新 `npm run dev`（5173，Vite proxy `/v1 → :8000`，同源免跨域）。
- 反面（避免）：把 8000 当"后端 API"、把 3080 当"前端"——本项目前端就是被后端静态托管的，
  一套端口打通，用户少记一个地址。

## 2. 三个工作区：单一职责的页面划分

| 工作区 | 页面组件 | 能力 | 后端 API |
| --- | --- | --- | --- |
| 对话 | ChatView / Composer / ToolCallCard | SSE 实时流式对话 + 工具调用轨迹回放 | /v1/tasks/*、/v1/tasks/{id}/stream |
| 知识库 (M3a) | KnowledgeBaseView | 入库、文档列表、hybrid 检索、RAG 评测 | /v1/kb/documents、/v1/kb/search、/v1/kb/eval |
| 记忆 (M3b) | MemoryView | 事实 CRUD、向量记忆检索、上下文块预览 | /v1/memory/facts、/v1/memory/search、/v1/memory/context |

- 导航：侧栏"工作区"三个可点项（对话 / 知识库 / 记忆），高亮当前视图；
  App 持有 `view: "chat" | "kb" | "memory"` 状态切换，互不干扰。
- 真理：管理页和对话页是**同源同端口**的关系，不是两个站点——状态切换在前端完成，
  后端只暴露 REST/SSE，职责清晰。

## 3. 知识库管理页（KnowledgeBaseView）

- 入库表单：标题 + 正文（`POST /v1/kb/documents {title, content}`，**doc_id 服务端自动生成**，
  响应带回 chunk_count / chars，界面提示"已入库，N chunks / M 字符"）。
- 文档列表：GET 全量 → 每条显示标题/doc_id/相对时间 + 删除按钮（DELETE → 204，404 提示）。
- 检索：`GET /v1/kb/search?q=&k=`（**参数是 q，不是 query**）→ 片段 + 来源 + score（转百分比展示）。
- RAG 评测：`POST /v1/kb/eval {k, judge:"proxy"}` → 三种策略（vector / hybrid / hybrid_rerank）
  各自的 recall / MRR / NDCG 等聚合指标；skipped 如实展示（相关文档未入库的 case 不计分，诚实报告）。
- 真理：管理页是**产品级 RAG 工具箱**——用户能看到"我的知识库有多少文档、检索质量如何"，
  这是"可运维可上线"的产品面；评测结果宁可诚实（skipped），不给虚假的满分。

## 4. 记忆管理页（MemoryView）

- 长期事实 CRUD：`PUT /v1/memory/facts/{key}` 新增/覆盖、列表、删除；编辑=点图标回填表单再保存。
- 向量记忆检索：`POST /v1/memory/search {q,k}` → hits（source / text / score）。
- 上下文块预览：`GET /v1/memory/context?q=&budget=` → 拼接好的注入上下文 block（F4.3 上下文工程可视化）。
- 真理：把"上下文工程"变成用户能看见的东西——这既是调试工具，也是信任建立：
  用户看得见 Agent 会往上下文里放什么。

## 5. 产品化 UX：工程参数不外露（本页核心真理）

- 真理：**没有哪家 Agent 产品（ChatGPT / Claude / Codex）把 max_steps、thread_id 摆给用户填**。
  - max_steps：Agent 单次任务最多思考→行动几轮，是**服务质量/成本**的工程权衡，不是用户意图。
    用户要的是"把事办成"，不是"允许你最多干 N 步"。
  - thread_id：会话上下文的载体，是**实现细节**。用户要的是"同一对话里上下文连续"，
    不是记住一串 UUID 再手工填回去。
- 落地：Composer 只留输入框 + 发送/停止；`MAX_STEPS = 8` 内部常量（App.tsx 一处可调）；
  thread_id 由系统全自动管理（见 §6）。
- 反面（避免）：把路由参数、供应商配置、重试次数、并发数一股脑做成输入框——
  那是管理后台的"高级设置"，不是主对话入口。要暴露，就藏进"高级/设置"，默认永远最优。

## 6. 会话切换语义：回放 + 线程续聊（本期修复）

- 真理：会话切换 = **打开该会话的完整轨迹 + 在该线程上继续聊**，不是换个空标签页。
  用户对"切换"的心智模型是"回到上次的地方"，所以：
  1. 内容必须是该会话的历史（靠 SSE 回放重建）；
  2. 后续发言必须续用该会话的线程（上下文连续）。
- 实现机制（App.tsx）：
  - `pickTask(id)`：先 `setItems([])` **清空消息区**（防旧会话残留/叠加），再 `setActiveTaskId`，
    SSE 效果随之连接 `stream` 回放全部事件；同时 `setThreadId(task.thread_id)` 沿用线程。
  - `send()`：创建任务成功后 `setThreadId(created.thread_id)`——
    否则新会话第 2 条消息会开新线程，上下文断裂。
  - `newChat()`：`setThreadId("")`，服务端自动生成新线程。
  - 刷新恢复（hash `#task=`）：同样先清空再回放，并用 `d.thread_id` 续线程。
- 真理：**SSE 回放是轨迹的唯一数据源**——前端不单独缓存每个会话的消息数组，
  切换一律"清空→重放"，天然一致，不会出现 A 会话的消息混进 B 会话。

## 7. 构建与部署（非 3080 的交付路径）

```bash
cd services/web
npm run build          # tsc(strict, noUnusedLocals) && vite build → dist/
# dist 已被 .gitignore 忽略（构建产物不入库，部署/本地各自重建）
# 后端 main.py 检测到 dist/ 存在即在 "/" 挂载 → 访问 http://127.0.0.1:8000/
cd services/web && npm run dev   # 可选：Vite 热更新开发模式，端口 5173
```

- 验证：`curl http://127.0.0.1:8000/ | grep -o "index-[A-Za-z0-9_-]*\.js"`，
  再对返回的新 hash 资产 `curl .../assets/index-*.js | grep 知识库管理` 确认新页面已上线。

## 8. 踩坑经验（前端 + 本会话工程化）

- **长 heredoc 写 TSX 会被工具截断并污染文件**（提示 `here-document ... delimited by end-of-file`）：
  实际是把未闭合的 heredoc 整体写入，导致重复内容。对策：**每段 < 100 行**，写一段核对一次行数，
  发现行数异常（远超预期）立即 `rm` 重写；最后 `grep -c "export default"` 应为 1。
- **noUnusedLocals: true**：删掉 UI 控件后未用的图标导入（如 `Wrench`）会直接让 `tsc` 构建失败——
  改了组件先自查导入。
- **静态挂载免重启**：StaticFiles 按磁盘读，改 dist 只刷新浏览器即可，不用重启 uvicorn。
- **提交消息文件反复被 git 带上**：`git add -A && commit -F msg && git rm --cached msg && amend`，
  最后 `git show --stat` 核对文件清单（消息文件应不在列）。

## 9. 一页速记（面试/自检用）

1. 控制台 = 门面：能力翻译成用户动作，工程参数不外露。
2. 三个工作区单一职责：对话 / 知识库 / 记忆，同端口同源，前端切状态。
3. max_steps / thread_id 是内部实现细节，产品主入口永不暴露；要暴露就藏进高级设置。
4. 会话切换 = 清空 + SSE 回放 + 沿用线程；SSE 回放是轨迹唯一数据源。
5. 构建 `npm run build` → dist（gitignore）→ 后端 8000 静态托管，非 3080。
