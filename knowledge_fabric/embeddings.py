"""Embedding provider abstraction — never hard-code a single vendor."""

from __future__ import annotations

import hashlib
import math
import struct
from abc import ABC, abstractmethod
from typing import List, Sequence


class EmbeddingProvider(ABC):
    provider: str
    model: str
    dimensions: int
    version: str = "1"

    @abstractmethod
    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        ...

    def embed_one(self, text: str) -> List[float]:
        return self.embed([text])[0]


class HashEmbeddingProvider(EmbeddingProvider):
    """
    Deterministic local embedding for tests and offline use.
    Not a substitute for production semantic models — vectors are persistent
    and cosine-comparable; swap provider without changing agents.
    """

    def __init__(self, dimensions: int = 64, model: str = "hash-v1"):
        self.provider = "local_hash"
        self.model = model
        self.dimensions = dimensions
        self.version = "1"

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        return [self._vec(t) for t in texts]

    def _vec(self, text: str) -> List[float]:
        tokens = (text or "").lower().split()
        vec = [0.0] * self.dimensions
        if not tokens:
            return vec
        for tok in tokens:
            h = hashlib.sha256(tok.encode("utf-8")).digest()
            for i in range(0, min(len(h), self.dimensions * 4), 4):
                idx = (struct.unpack_from(">I", h, i)[0] % self.dimensions)
                sign = 1.0 if (h[i] % 2 == 0) else -1.0
                vec[idx] += sign
        # L2 normalize
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


_default_provider: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    global _default_provider
    if _default_provider is None:
        _default_provider = HashEmbeddingProvider()
    return _default_provider


def set_embedding_provider(provider: EmbeddingProvider) -> None:
    global _default_provider
    _default_provider = provider
