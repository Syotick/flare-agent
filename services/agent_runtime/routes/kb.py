"""知识库 API（M3a-F5.1/5.3）：入库、列表、检索、删除。

路径：/v1/kb/*（与任务 API /v1/tasks/* 并列；Web 后续做知识库管理页时直接消费）。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from rag.eval import builtin_dataset
from rag.eval.dataset import EvalCase
from rag.eval.ragas import CoverageProxyJudge, run_ragas
from rag.eval.runner import run_retrieval_eval
from rag.pipeline import KnowledgeBase
from rag.schemas import (
    DocumentCreate,
    DocumentSummary,
    EvalRequest,
    EvalResponse,
    EvalStrategyOut,
    IngestResponse,
    SearchHitResponse,
)


def build_kb_router(kb: KnowledgeBase) -> APIRouter:
    router = APIRouter(prefix="/v1/kb", tags=["knowledge-base"])

    @router.post("/documents", response_model=IngestResponse, status_code=201)
    async def ingest_document(body: DocumentCreate) -> IngestResponse:
        """入库一份文档（自动切块 + 向量化）。"""
        result = await kb.ingest(title=body.title, content=body.content)
        return IngestResponse(
            doc_id=result.doc_id,
            title=result.title,
            chunk_count=result.chunk_count,
            chars=result.chars,
        )

    @router.get("/documents", response_model=list[DocumentSummary])
    async def list_documents() -> list[DocumentSummary]:
        metas = await kb.list_documents()
        return [
            DocumentSummary(doc_id=m.doc_id, title=m.title, created_at=m.created_at) for m in metas
        ]

    @router.delete("/documents/{doc_id}", status_code=204)
    async def delete_document(doc_id: str) -> None:
        if not await kb.delete(doc_id):
            raise HTTPException(status_code=404, detail="document not found")

    @router.get("/search", response_model=list[SearchHitResponse])
    async def search_kb(q: str, k: int = Query(5, ge=1, le=20)) -> list[SearchHitResponse]:
        """语义检索：返回 top-k 片段，带来源(title + chunk 序号 + 分数)。k 限 1..20（R4）。"""
        hits = await kb.search(q, k=k)
        return [
            SearchHitResponse(
                doc_id=h.doc_id,
                title=h.title,
                chunk_index=h.chunk_index,
                text=h.text,
                score=h.score,
            )
            for h in hits
        ]

    @router.post("/eval", response_model=EvalResponse)
    async def run_eval(body: EvalRequest) -> EvalResponse:
        """M3c：对给定查询集跑检索策略对比评测（只读，不改知识库）。

        - 相关文档按标题解析到当前库中的 doc_id，解析不到的 case 进 skipped（诚实报告）；
        - cases 缺省用内置评测集（要求相关文档已入库，见 scripts/demo_eval.py）；
        - strategies 缺省 vector / hybrid / hybrid_rerank 全跑；
        - judge=proxy 用确定性代理判定（零依赖）；judge=llm 需真实模型（M4）。
        """
        if body.cases is not None:
            cases = [EvalCase(c.query, c.relevant_titles) for c in body.cases]
            eval_source = cases  # 自定义集 -> 报告 dataset="custom"
        else:
            ds = builtin_dataset()
            cases = ds.cases
            eval_source = ds  # 内置集 -> 报告 dataset="builtin"
        strategies = tuple(body.strategies or ["vector", "hybrid", "hybrid_rerank"])
        report = await run_retrieval_eval(kb, eval_source, k=body.k, strategies=strategies)
        ragas = None
        if body.judge == "proxy":
            ragas = await run_ragas(kb, cases, judge=CoverageProxyJudge(), k=body.k)
        else:
            raise HTTPException(
                status_code=503,
                detail="RAGAS LLM 判定需真实模型（FLARE_MODEL_API_KEY，M4 接入），当前未配置",
            )
        return EvalResponse(
            dataset=report.dataset,
            k=report.k,
            strategies=[
                EvalStrategyOut(
                    strategy=s.strategy, k=s.k, aggregate=s.aggregate, per_query=s.per_query
                )
                for s in report.strategies
            ],
            skipped=report.skipped,
            ragas=ragas,
        )

    return router
