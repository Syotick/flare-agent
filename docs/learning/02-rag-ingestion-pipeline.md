# Flare Agent · RAG 入库管线与向量检索（实践 + 真理）

> 版本：v1.0 ｜ 日期：2026-08-27 ｜ 状态：draft
> 定位：M3a 知识库的配套教学文档。先讲真理（RAG 通用设计），再讲实践（我们在 services/rag 的落地）。
> 关联需求：FR-5（RAG 知识库）、FR-10（面试考点）——可结合面试题库一起背。

---

## 1. RAG 是什么，为什么需要它

- 真理：RAG（Retrieval-Augmented Generation，检索增强生成）= 把「外部知识检索」接到 LLM 生成之前。
  原因：LLM 知识有截止时间、会幻觉、不掌握私有数据。RAG 让模型**先查资料再回答**，
  可溯源（引用来源）、可更新（换库即换知识）、可控（按库/文档粒度管权限）。
- 实践：Flare Agent 把知识检索做成 Agent 的**一个工具 kb_search**——模型自主决定何时查库，
  而不是每条消息都强制检索。这是 Agent 化 RAG（自主 RAG）区别于固定 RAG 管线的关键。

## 2. 入库管线（Ingestion Pipeline）五大步骤

- 真理：入库 = 原文 → 清洗 → 切块 → 向量化 → 存储。任何一个环节质量差都直接拉低召回。
  常见坑：切块太大会稀释语义、太小会丢失上下文；chunk 之间要留 overlap；重复入库要能 upsert。
- 实践（services/rag/pipeline.py 的 KnowledgeBase.ingest）：
  1. 清洗：去空行、去首尾空白；
  2. 切块（chunking.py）：**段落优先**——非空行贪心合并进 chunk，单段落超长才按窗口硬切并留 overlap；
  3. 向量化（embedder.py）：统一 embed(texts) 接口，开发用 HashEmbedder、生产换 DashScope；
  4. 存储（store.py）：统一 VectorStore 协议，开发用 SqliteVectorStore（aiosqlite 落盘）、生产换 PgVectorStore；
  5. 返回 IngestResult（doc_id / 块数 / 字符数），重复 doc_id 自动覆盖（upsert）。

## 3. 检索（Retrieval）：查询向量化 + top-k

- 真理：检索 = 把查询向量化，在向量空间找最相似的 chunk（余弦相似度），返回 top-k 并**带来源**。
  进阶（M3c 评测后补）：混合检索（向量 + BM25 关键词）、重排（Rerank）把候选从数百压到 top-k。
- 实践（KnowledgeBase.search）：查询嵌入 → store.search 计算余弦 → 按分数倒序取 top-k；
  命中带溯源字段（title + chunk 序号 + score），kb_search 工具把来源拼进模型观察，
  模型才能「引用」而不是「编造」。

## 4. 接口为什么用 Protocol（可插拔）

- 真理：向量库/嵌入模型迭代极快，架构上要**面向接口**而不是绑死某一家。
  同一套管线换嵌入模型/向量库，只换实现类，上层（路由、工具、Web）零改动。
- 实践：

      rag/
        chunking.py   切块策略（纯函数，好测）
        embedder.py   Embedder 协议 + HashEmbedder(dev) + DashScopeEmbedder(prod)
        store.py      VectorStore 协议 + SqliteVectorStore(dev) + PgVectorStore(prod 占位)
        pipeline.py   KnowledgeBase 门面（上层唯一入口）
        kb_tools.py   kb_search 工具（绑定指定知识库实例）

## 5. 工程要点与踩坑

- **事件循环**：aiosqlite 连接绑定创建它的 event loop。TestClient 必须用 with TestClient(...) as client
  保持单一 portal loop，否则后台任务在请求返回时被丢（status 卡 running、event_count=0）。
  这也是 M5 迁 Redis/DB 存储的解耦动机之一——跨 worker/跨 loop 共享状态必须走外部存储。
- **确定性嵌入**：Python 内置 hash() 对 str 每次进程加盐，跨进程结果不稳定；用 zlib.crc32 保证可复现、可回归。
- **fail-fast**：生产嵌入/向量库未配置时不静默降级，直接抛带错误码的 FlareError（如 EMBEDDING_NOT_CONFIGURED），
  避免把错误数据灌进知识库。

## 6. 验收

- [ ] POST /v1/kb/documents 入库 → GET /v1/kb/search?q= 命中正确文档且带 title/score 溯源
- [ ] DELETE /v1/kb/documents/{id} 删除后不再命中
- [ ] Agent 对话能自主调用 kb_search 并基于来源作答（tests/unit/test_rag.py::test_agent_uses_kb_search_tool）
- [ ] pytest 全绿（42 passed）
- 下一步：M3c RAG 评测（RAGAS：召回/忠实度/答案相关性）+ 混合检索/重排；M3b 分层记忆（会话短期→项目长期→向量记忆）。
