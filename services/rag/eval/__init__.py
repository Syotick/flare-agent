"""RAG 评测（M3c）：确定性检索指标 + 混合检索/重排对比 + RAGAS 式 LLM 判定。

- 检索质量先用确定性指标量化（recall@k/MRR/hit_rate，零依赖可离线跑）；
- 策略对比：vector vs hybrid(BM25+向量 RRF) vs hybrid_rerank；
- RAGAS 式忠实度/答案相关性用 CoverageProxyJudge（开发）或 LLMJudge（真实模型，M4）。
"""

from rag.eval.dataset import EvalCase, EvalDataset, builtin_dataset
from rag.eval.metrics import (
    aggregate,
    hit_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from rag.eval.runner import EvalReport, StrategyReport, run_retrieval_eval

__all__ = [
    "EvalCase",
    "EvalDataset",
    "builtin_dataset",
    "aggregate",
    "hit_at_k",
    "ndcg_at_k",
    "precision_at_k",
    "recall_at_k",
    "reciprocal_rank",
    "EvalReport",
    "StrategyReport",
    "run_retrieval_eval",
]
