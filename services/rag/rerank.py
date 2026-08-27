"""重排（M3c）：检索出候选后，用更细的模型/规则把最相关的排到前面。

- Reranker 协议：rerank(query, candidates, k) -> top-k；
- CoverageReranker：开发默认，按 query 词元在片段中的覆盖度加权（字面相关），零依赖可测；
- DashScopeReranker：生产占位，未配置 fail-fast 抛 RerankUnavailableError（不静默降级）。
"""

from __future__ import annotations

from typing import Protocol

from flare_common.errors import FlareError
from rag.lexical import tokenize
from rag.store import SearchHit


class RerankUnavailableError(FlareError):
    code = "RERANK_NOT_CONFIGURED"
    status_code = 503


class Reranker(Protocol):
    async def rerank(self, query: str, candidates: list[SearchHit], k: int) -> list[SearchHit]: ...


class CoverageReranker:
    """开发重排：按 query 词元覆盖度（在候选片段中出现的比例）加权。

    本质是字面相关增强，能修复"向量分数高但没答到点上"的排序；
    生产可换模型级重排（DashScope text-rerank，语义更准）。
    """

    async def rerank(self, query: str, candidates: list[SearchHit], k: int) -> list[SearchHit]:
        q_tokens = set(tokenize(query))
        if not q_tokens:
            return candidates[:k]
        scored: list[tuple[float, float, SearchHit]] = []
        for h in candidates:
            c_tokens = set(tokenize(h.text))
            overlap = sum(1 for t in q_tokens if t in c_tokens)
            coverage = overlap / len(q_tokens)
            scored.append((coverage, h.score, h))
        scored.sort(key=lambda x: (-x[0], -x[1]))  # 覆盖度优先，其次原分
        return [h for _, _, h in scored[:k]]


class DashScopeReranker:
    """生产重排占位：阿里云 text-rerank（M3c-M4 接入）。

    未配置时调用抛 RerankUnavailableError（fail-fast），避免静默用低级重排冒充高级能力。
    """

    def __init__(self, api_key: str | None = None, model: str = "text-rerank-v2") -> None:
        self._api_key = api_key
        self._model = model

    async def rerank(self, query: str, candidates: list[SearchHit], k: int) -> list[SearchHit]:
        if not self._api_key:
            raise RerankUnavailableError("未配置重排模型 API Key，无法使用模型级重排")
        # M4：接 DashScope text-rerank API（query + candidates -> scores），当前为占位
        raise RerankUnavailableError(f"重排模型 {self._model} 接入待 M4 实现")
