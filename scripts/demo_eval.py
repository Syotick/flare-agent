"""M3c 演示：入库内置评测语料 -> 三检索策略对比 -> RAGAS 式代理判定。

运行：PYTHONPATH=services python scripts/demo_eval.py
用独立临时库（data/_demo_eval.sqlite3），不污染线上 kb.sqlite3，跑完即删。
"""

import asyncio
import os

from rag.eval import builtin_dataset, run_retrieval_eval
from rag.eval.ragas import CoverageProxyJudge, run_ragas
from rag.pipeline import KnowledgeBase
from rag.store import SqliteVectorStore

DB = "data/_demo_eval.sqlite3"


async def main() -> None:
    kb = KnowledgeBase(SqliteVectorStore(DB))
    ds = builtin_dataset()
    print("== 入库评测语料 ==")
    for title, content in ds.corpus:
        r = await kb.ingest(title=title, content=content)
        print(f"  + {title}: {r.chunk_count} chunks / {r.chars} chars")
    report = await run_retrieval_eval(kb, ds, k=5)
    print("\n== 检索策略对比 (k=5) ==")
    header = f"{'策略':<14}{'recall@5':<11}{'precision@5':<13}{'hit_rate':<10}{'MRR':<9}{'NDCG@5'}"
    print(header)
    for s in report.strategies:
        a = s.aggregate
        print(
            f"{s.strategy:<14}{a['recall@k']:<11}{a['precision@k']:<13}{a['hit_rate']:<10}{a['mrr']:<9}{a['ndcg@k']}"
        )
    print(f"\n  skipped cases: {report.skipped}")
    ragas = await run_ragas(kb, ds.cases, judge=CoverageProxyJudge(), k=5)
    agg = ragas["aggregate"]
    print("\n== RAGAS 式判定 (CoverageProxyJudge 开发代理) ==")
    print(
        f"  faithfulness={agg.get('faithfulness')}  answer_relevance={agg.get('answer_relevance')}"
    )
    await kb.close()
    if os.path.exists(DB):
        os.remove(DB)


if __name__ == "__main__":
    asyncio.run(main())
