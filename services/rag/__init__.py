"""RAG 知识库（M3a：入库管线 + 向量检索 + kb_search 工具）。

分层（可插拔）：
  chunking(切块) -> embedder(向量化) -> store(存储/检索) -> pipeline(KnowledgeBase 门面)。
开发默认：HashEmbedder + SqliteVectorStore（零依赖、确定性、可测）。
生产替换（接口不变）：DashScopeEmbedder（阿里云 text-embedding-v3） + PgVectorStore（pgvector）。
"""

from rag.pipeline import IngestResult, KnowledgeBase, SearchHit
from rag.store import SqliteVectorStore

__all__ = ["IngestResult", "KnowledgeBase", "SearchHit", "SqliteVectorStore"]
