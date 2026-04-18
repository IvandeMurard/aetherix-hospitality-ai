"""FakeEmbeddingProvider — deterministic 1024-d embedding for tests (ADR 0002 D11).

Uses BLAKE2b to produce a stable, normalized-ish vector from any input string.
No network call, no API key, reproducible across runs.

Usage:
    provider = FakeEmbeddingProvider()
    vec = await provider.embed("dinner service rainy tuesday")
    # returns list[float] of length 1024, same value every run
"""
from __future__ import annotations

import hashlib


class FakeEmbeddingProvider:
    """Test-only embedding provider: blake2b hash → normalized 1024-d float vector."""

    DIM = 1024

    async def embed(self, text: str) -> list[float]:
        # shake_256 produces variable-length output — 1024 bytes → 1024 floats
        digest = hashlib.shake_256(text.encode("utf-8")).digest(self.DIM)
        return [(b / 127.5) - 1.0 for b in digest]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [await self.embed(t) for t in texts]

    @property
    def dimensions(self) -> int:
        return self.DIM
