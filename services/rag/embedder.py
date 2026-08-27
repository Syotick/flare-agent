"""文本向量化（M3a-F5.1）。

统一 async embed(texts) -> list[list[float]] 接口：
  - HashEmbedder：开发默认（零依赖、确定性、可测；字符 n-gram 哈希 + L2 归一化）
  - DashScopeEmbedder：生产（阿里云 text-embedding-v3，需 DASHSCOPE_API_KEY）
"""

from __future__ import annotations

import math
import re
import zlib
from typing import Protocol

from flare_common.errors import FlareError


class EmbeddingUnavailableError(FlareError):
    code = "EMBEDDING_NOT_CONFIGURED"
    status_code = 503


class Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbedder:
    """开发用确定性嵌入。

    字符 n-gram -> crc32 哈希 -> 固定维向量（hash trick + L2 归一化）。
    语义近似的文本共享大量 n-gram，余弦相似度可排序——足以支撑
    管线 / 检索 / 测试；生产请换真实模型嵌入（DashScopeEmbedder）。
    """

    def __init__(self, dim: int = 256, ngram: int = 2) -> None:
        if dim < 16:
            raise ValueError("dim 至少 16")
        self._dim = dim
        self._ngram = ngram

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", text).lower()

    def _tokens(self, text: str) -> list[str]:
        text = self._normalize(text)
        if len(text) < self._ngram:
            return [text] if text else []
        return [text[i : i + self._ngram] for i in range(len(text) - self._ngram + 1)]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self._dim
        for tok in self._tokens(text):
            h = zlib.crc32(tok.encode("utf-8"))
            idx = h % self._dim
            sign = 1.0 if (h >> 4) & 1 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]


class DashScopeEmbedder:
    """生产嵌入：阿里云 DashScope text-embedding-v3（M3-F5.1）。

    未配置 DASHSCOPE_API_KEY 时调用抛 EmbeddingUnavailableError（fail-fast，R4 风格），
    避免静默降级把错误数据灌进知识库。
    """

    _ENDPOINT = (
        "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
    )

    def __init__(
        self, api_key: str | None = None, model: str = "text-embedding-v3", timeout: float = 30.0
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self._api_key:
            raise EmbeddingUnavailableError("未配置 DASHSCOPE_API_KEY，无法调用生产嵌入模型")
        import httpx

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                self._ENDPOINT,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": self._model, "input": texts},
            )
            resp.raise_for_status()
            data = resp.json()
            return [item["embedding"] for item in data["output"]["embeddings"]]
