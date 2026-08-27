"""分层记忆（M3b-FR-4）：会话短期 + 项目长期事实 + 向量记忆 + 上下文工程。

- 短期：LangGraph checkpointer 按 thread 持久化会话（消息天然短期记忆）；
- 长期：MemoryManager 事实库（key->value，按 project_id 隔离，开发 SQLite / 生产 PG）；
- 向量：复用 rag 的 Embedder/VectorStore 协议做语义召回（开发 HashEmbedder+Sqlite）。
上下文工程（F4.3）见 context.py，Agent 工具见 mem_tools.py。
"""

from memory.memory import MemoryManager

__all__ = ["MemoryManager"]
