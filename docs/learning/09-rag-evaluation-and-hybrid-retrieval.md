# Flare Agent · RAG 评测与混合检索（实践 + 真理）

> 版本：v1.0 ｜ 日期：2026-08-27 ｜ 状态：draft
> 定位：M3c 配套教学文档——怎么用数据证明"我的 RAG 到底行不行"，以及混合检索/重排怎么参与。
> 配套：02-rag-ingestion-pipeline（入库）、08-技术架构 §3/§4（运行机制/数据）、05-生产部署指南（评测回归放 CI）。

---

## 1. 为什么必须评测（真理先行）

- 真理：不评测 = 拍脑袋。RAG 的每个环节（切块、嵌入、检索、排序、生成）都可能有病，
  但没有数据时谁也说不清病在哪；有了评测，每次改 嵌入/检索/提示词 都能用数字说话。
- 真理：评测要分两层——
  1. 检索质量（离线、零依赖、可天天跑）：召回对了吗？相关的东西排到前面了吗？
  2. 生成质量（在线、需要真实模型）：答案忠实上下文吗？答到问题上吗？
- 反面（避免）：只在 demo 里"看着像"就上线；或拿几十条手挑数据自证优秀（过拟合评测集）。

## 2. 第一层：确定性检索指标（services/rag/eval/metrics.py）

| 指标 | 直觉 | 公式要点 |
| --- | --- | --- |
| recall@k | 相关文档被召回了多少（怕漏） | 命中相关数 / 相关总数 |
| precision@k | top-k 里有多少是真的（怕脏） | 命中相关数 / k |
| hit_rate | top-k 有没有命中至少一条 | 0 或 1 |
| MRR | 第一个相关排在第几位（第一名对不对） | 1 / 首个相关排名 |
| NDCG@k | 整体排序质量（带位置折损） | 折损 DCG / 理想 DCG |

- 这些指标不依赖 LLM，pytest 里可以手算校验（test_eval.py::test_metrics_hand_computed）。

## 3. 评测数据集（services/rag/eval/dataset.py）

- 一条用例 = 查询 + 相关文档标题列表；相关按"标题"标（doc_id 是随机的，
  运行时用 kb.list_documents() 把标题解析成 doc_id，解析不到的进 skipped 诚实报告）。
- 内置集（builtin_dataset）覆盖三类：精确关键词、语义改写、多文档综合——
  这是起点不是终点，上线前要用真实业务问题持续扩充（否则会过拟合这 4 篇语料）。

## 4. 第二层：RAGAS 式生成质量（services/rag/eval/ragas.py）

- 忠实度 faithfulness：答案内容是否都能在给定上下文里找到依据（防幻觉）；
- 答案相关性 answer_relevance：答案是否回答到问题上（防答非所问）；
- 实现：
  - CoverageProxyJudge（开发默认）：用词元覆盖近似两个分数——零依赖可跑 CI，
    但只是"自洽性"的代理，不能当真实生成质量；
  - LLMJudge（生产，M4 接入真实模型）：用非 mock 的 ModelProvider 生成答案并打分，
    未配置时 fail-fast 抛 RagJudgeUnavailableError（不静默用假评分冒充）。

## 5. 混合检索：BM25 + 向量，RRF 融合（services/rag/hybrid.py）

- 真理：向量召回擅长"语义相近"，但专有名词/编号/代码/精确要求它可能漏；
  BM25 擅长字面命中，但不懂改写。两者融合（RRF）通常优于单一策略——用评测数据说话。
- RRF：score(d) = Σ 1/(60 + rank_i(d))——只吃排名不吃分数，
  因此向量余弦和 BM25 分数无需可比。
- 使用：kb.search(q, k, strategy="hybrid")；关键词索引懒构建，入库/删除自动失效重建。
- 注意：开发用的是字面 HashEmbedder，向量≈关键词，所以内置集上三策略持平——
  这恰恰证明评测是诚实的；接真实嵌入（DashScope text-embedding-v3）后，
  语义改写类查询会拉开差距，届时用 /v1/kb/eval 复跑即可量化。

## 6. 重排（services/rag/rerank.py）

- 真理：检索器做"宽召回"，重排器做"精排序"。重排可以比检索贵，因为只处理前几十条。
- CoverageReranker：开发默认，按 query 词元在片段里的覆盖度重排（字面相关增强）；
  DashScopeReranker：生产占位，text-rerank 语义重排，未配置 fail-fast（不降级冒充）。
- 使用：strategy="hybrid_rerank" = hybrid 召回后再重排 top-k。

## 7. 怎么跑（demo + API）

- scripts/demo_eval.py：临时库入库内置语料 -> 三策略对比 -> RAGAS 代理判定，跑完即删；
- POST /v1/kb/eval：只读评测当前知识库（不改库）；body 可带 k/cases/strategies/judge；
  judge=llm 需真实模型（当前 mock 返回 503，诚实 fail-fast）；
- 输出：每个策略的 aggregate（recall/precision/hit_rate/MRR/NDCG）+ 每 query 明细 + skipped。

## 8. 真理与坑

- 评测必须走和生产一模一样的检索路径（同一个 kb.search），不然测了个寂寞；
- RAGAS 的真实价值在真实模型 + 真实业务数据下才显现，proxy 只保证"管线自洽"；
- 评测集要随产品演进持续扩充，并纳入 CI（M6 做评测回归），防止改坏召回不自知；
- RRF 融合的对象必须是"同 identity"（(doc_id, chunk_index)），并保留首路对象字段（踩坑：
  曾因覆盖赋值把 SearchHit 换成无 title 的 KeywordHit）。

## 9. 练习

1. 给内置集加 3 条"语义改写"用例（问题不出现文档原词），看 vector 与 hybrid 的 MRR 是否拉开。
2. 把评测跑进 pytest（新增一条断言：hybrid 的 recall 不低于 vector），为什么这条要进 CI？
3. 思考：接真实嵌入后，如果 vector 反而变差，可能的原因有哪些？（提示：嵌入质量、
   切块粒度、维度失配、数据未重嵌入）
