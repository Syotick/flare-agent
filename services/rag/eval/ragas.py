"""RAGAS 式生成质量评测（M3c）：忠实度 + 答案相关性。

- CoverageProxyJudge：开发默认（确定性），用词元覆盖近似"忠实/相关"——零依赖可测，
  明确标注是代理不是真 RAGAS；
- LLMJudge：真实 RAGAS 式判定，需要非 mock 的 ModelProvider（M4 接入真实模型后启用），
  未配置时 fail-fast 抛 RagJudgeUnavailableError（不静默用假评分）。
"""

from __future__ import annotations

from typing import Protocol

from flare_common.errors import FlareError
from model_gateway.mock import MockModelProvider
from model_gateway.providers import LLMMessage, ModelProvider
from rag.eval.dataset import EvalCase
from rag.lexical import tokenize
from rag.pipeline import KnowledgeBase


class RagJudgeUnavailableError(FlareError):
    code = "RAG_JUDGE_NOT_READY"
    status_code = 503


class RagJudge(Protocol):
    async def answer(self, question: str, contexts: list[str]) -> str: ...
    async def faithfulness(self, contexts: list[str], answer: str) -> float: ...
    async def answer_relevance(self, question: str, answer: str) -> float: ...


class CoverageProxyJudge:
    """确定性代理判定（开发）。

    答案 = 最相关上下文的原文（无生成，因此忠实度天然接近满分——只能说明管线自洽，
    不能说明真实生成质量）；真正上线前请用 LLMJudge + 真实模型。
    """

    async def answer(self, question: str, contexts: list[str]) -> str:
        return contexts[0] if contexts else ""

    async def faithfulness(self, contexts: list[str], answer: str) -> float:
        toks = tokenize(answer)
        if not toks:
            return 1.0
        ctx = set()
        for c in contexts:
            ctx.update(tokenize(c))
        return sum(1 for t in toks if t in ctx) / len(toks)

    async def answer_relevance(self, question: str, answer: str) -> float:
        q = set(tokenize(question))
        if not q:
            return 1.0
        a = set(tokenize(answer))
        return sum(1 for t in q if t in a) / len(q)


class LLMJudge:
    """RAGAS 式 LLM 判定：用真实模型生成答案并打分（M4 接入真实模型后启用）。"""

    def __init__(self, provider: ModelProvider, *, model: str | None = None) -> None:
        if isinstance(provider, MockModelProvider):
            raise RagJudgeUnavailableError(
                "RAGAS LLM 判定需要真实模型（配置 FLARE_MODEL_API_KEY），当前是 mock"
            )
        self._provider = provider
        self._model = model

    async def _ask(self, system: str, user: str) -> str:
        resp = await self._provider.chat(
            [LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)]
        )
        return resp.content

    async def answer(self, question: str, contexts: list[str]) -> str:
        ctx = "\n".join(f"- {c}" for c in contexts)
        return await self._ask(
            "你是评测助手，严格基于给定上下文回答。", f"上下文：\n{ctx}\n\n问题：{question}"
        )

    async def faithfulness(self, contexts: list[str], answer: str) -> float:
        raw = await self._ask(
            "你是忠实度评分员，只输出 0 到 1 的小数。", f"上下文：{contexts}\n答案：{answer}"
        )
        return self._parse_score(raw)

    async def answer_relevance(self, question: str, answer: str) -> float:
        raw = await self._ask(
            "你是相关性评分员，只输出 0 到 1 的小数。", f"问题：{question}\n答案：{answer}"
        )
        return self._parse_score(raw)

    @staticmethod
    def _parse_score(raw: str) -> float:
        try:
            return max(0.0, min(1.0, float(raw.strip())))
        except ValueError:
            return 0.0


async def run_ragas(
    kb: KnowledgeBase,
    cases: list[EvalCase],
    *,
    judge: RagJudge,
    k: int = 5,
    strategy: str = "hybrid_rerank",
) -> dict:
    """对每个 case：检索上下文 -> 生成答案 -> 评忠实度/答案相关性。"""
    rows: list[dict] = []
    for case in cases:
        hits = await kb.search(case.query, k=k, strategy=strategy)
        contexts = [h.text for h in hits]
        answer = await judge.answer(case.query, contexts)
        f = await judge.faithfulness(contexts, answer)
        ar = await judge.answer_relevance(case.query, answer)
        rows.append(
            {
                "query": case.query,
                "answer": answer,
                "faithfulness": round(f, 4),
                "answer_relevance": round(ar, 4),
                "context_count": len(hits),
            }
        )
    n = len(rows)
    agg = {}
    if n:
        agg = {
            "faithfulness": round(sum(r["faithfulness"] for r in rows) / n, 4),
            "answer_relevance": round(sum(r["answer_relevance"] for r in rows) / n, 4),
        }
    return {"rows": rows, "aggregate": agg}
