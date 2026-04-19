# ADR 0002 — Memory Instrumentation for Self-Improving Operational Memory

> **Status**: Accepted · **Date**: 2026-04-18 · **Author**: Architect (Opus)
> **Context**: Phase 1, Story P1-3 · **Blocks**: P1-4 (memory ablation benchmark) · **Extends**: ADR 0001
> **Linear**: HOS-P1-3

---

## 1. Context

Phase 0 shipped the `operational_memory` table: `vector(1024)` embedding column, HNSW cosine_ops index, per-hotel scoping. ADR 0001 shipped `submit_feedback_to_memory` (write) and `get_recommendations_with_memory_context` (read). Both are wired in `backend/app/mcp_server.py`.

**The gap**: `tool_submit_feedback_to_memory` writes a `[0.0] * 1024` placeholder (`mcp_server.py:193`), and `tool_get_recommendations_with_memory_context` orders by `created_at DESC`, not cosine similarity. The HNSW index is unused. Without real embeddings, the "self-improving intelligence" claim is unsubstantiated and P1-4 ablation has nothing to measure.

**Goal**: replace stubs with real Mistral embeddings on both paths, introduce `MemoryRecallService`, and lock the `MemoryProvider` interface so Phase 3 Hive Memory requires zero caller refactor.

**Non-goals**: cross-hotel retrieval (Phase 3), retraining signal on feedback (ADR 0001 OQ1), re-embedding job for existing zero-vector rows (one-shot migration, separate PR).

---

## 2. Decisions

### D1 — Embedding site: **inline on write, `await provider.embed(payload)`**

The `EmbeddingProvider` singleton lives in `app.state.embedding`. Mistral `mistral-embed` p95 is ~150–250 ms for short inputs — inside the 500 ms MCP budget (ADR 0001 §3). `MemoryService.store_reflection` already embeds inline with the same provider, so consistency is free.

Rejected — **outbox/background task**: adds a worker, a queue, eventual consistency, and makes `memory_id` unavailable at tool-return time (MCP response contract promises one). No latency win over inline at current call rate.

### D2 — Embedding payload: **structured concat**

```
f"[{memory_type}] outcome={outcome} | rec_context={recommendation_context} | notes={sanitized_notes} | actual={actual_value}"
```

Options:
- **Verbatim `reflection`** — strings like `"[rec=uuid] outcome=accepted"` have uuid dominating bag-of-tokens; manager words get buried.
- **`notes` only** — drops the outcome signal, which is the strongest retrieval key.
- **Structured concat (chosen)** — explicit field prefixes give the embedder stable anchor tokens; uuid omitted from embedded string (stored in `reco_json` for audit only); manager notes carry full weight.

For `memory_type=reflection` (no outcome/rec_id): payload = `f"[reflection] {reflection_text}"`.

The embedded string is distinct from the stored `reflection` column. `reflection` keeps the audit-friendly format (ADR 0001 D10 — never re-fed to LLM without escaping); embedding is computed from a parallel payload via `MemoryRecallService._build_embedding_payload()`.

### D3 — Query embedding: **same `app.state.embedding` singleton**

One process-wide instance — no drift possible. Switching models requires bumping `EMBEDDING_MODEL` env var AND a re-embed migration. A startup check comparing `provider.dimensions` against a `system_config` row is sketched but deferred (OQ1).

### D4 — Recall API

New module `backend/app/services/memory_recall_service.py`:

```python
@dataclass(frozen=True)
class MemoryHit:
    id: UUID
    similarity: float       # 1 - cosine_distance (0..1, higher = closer)
    reflection: str
    outcome: str | None
    manager_feedback: str | None   # followed|rejected|neutral
    memory_type: str
    source: str             # "private" | "fb_pattern"
    created_at: datetime

class MemoryRecallService:
    def __init__(self, db: AsyncSession, embedding: EmbeddingProvider): ...

    async def recall(
        self,
        hotel_id: str,
        query_text: str,
        k: int = 5,
        min_similarity: float = 0.5,
        memory_types: Sequence[str] = ("feedback", "reflection"),
        since: datetime | None = None,
        only_followed: bool = False,
    ) -> list[MemoryHit]: ...
```

SQL pattern:
```sql
SELECT *, 1 - (embedding <=> CAST(:q AS vector)) AS similarity
FROM operational_memory
WHERE hotel_id = :h
  AND memory_type = ANY(:types)
  [AND created_at >= :since]
  [AND manager_feedback = 'followed']
ORDER BY embedding <=> CAST(:q AS vector) ASC
LIMIT :k
```

Filter `similarity >= min_similarity` in Python post-fetch (cheaper than a `HAVING` clause; allows returning `< k` items cleanly).

### D5 — Filters: opinionated defaults

- **`memory_type`** default `("feedback", "reflection")` — exclude `recommendation_cache` (a cache, not a learning signal).
- **`since`** default `None` (full history) — a 2-year-old reflection may still be the best hit. Callers pass `since=now - 90d` for recency bias.
- **`only_followed`** default `False` — managers learn from rejections too. Flag exposed for P1-4 ablation benchmark.
- `recommendation_cache` accessible only via separate `get_latest_cached_recommendation()` — surfaces kept distinct.

### D6 — Cold-start: two-tier fallback

1. Recall on `operational_memory` for `hotel_id`. If ≥1 hit above `min_similarity`, return.
2. Else delegate to `RAGService.find_similar_patterns(query_text, service_type, tenant_id=hotel_id, limit=k)`, which already returns tenant-scoped + global (`tenant_id IS NULL`) patterns. Wrap each row as `MemoryHit(memory_type="fb_pattern", source="fb_pattern")`.

Caller sees a uniform `list[MemoryHit]` with `source` tag. Preserves Decision #2 privacy boundary — `fb_patterns` is curated/anonymized; no cross-hotel `operational_memory` access.

### D7 — Dedup: **tuple pre-check + cosine second-chance**

Coarse tuple `(hotel_id, recommendation_id, outcome)` stays as cheap first pass. On miss, compute embedding, then:

```sql
SELECT id FROM operational_memory
WHERE hotel_id = :h
  AND memory_type = 'feedback'
  AND created_at > NOW() - INTERVAL '7 days'
  AND 1 - (embedding <=> CAST(:new AS vector)) > 0.98
LIMIT 1;
```

7-day window bounds HNSW scan cost. Threshold 0.98 (Mistral-embed: typo variants ≥ 0.99, genuinely different notes < 0.95). Configurable via `MEMORY_DEDUP_THRESHOLD` env var.

### D8 — `MemoryProvider` interface (Phase 3 forward-compat)

Extend existing `MemoryProvider` Protocol in `memory_service.py`:

```python
class MemoryProvider(Protocol):
    # existing methods unchanged
    async def recall(
        self, tenant_id: str, query_text: str, k: int = 5,
        min_similarity: float = 0.5,
    ) -> list[MemoryHit]: ...
```

`PrivateMemoryProvider` wraps `MemoryRecallService` (Phase 1). Phase 3 `HiveMemoryProvider` implements same method against anonymized cross-hotel store. `CompositeMemoryProvider(private, hive, weights)` merges lists — interface sketched, not built. Phase 1 callers receive a `PrivateMemoryProvider`; Phase 3 swap is a single-file change in `app/providers/memory_factory.py`.

### D9 — Failure mode: Mistral API down at write time

**Chosen: (b) write with null embedding + `embedding_pending=TRUE`.**

Migration adds nullable `embedding`, boolean `embedding_pending`, CHECK `(embedding IS NOT NULL) OR (embedding_pending = TRUE)`. On embed failure: insert row with `embedding=NULL, embedding_pending=TRUE`, return MCP `status="stored_pending_embedding"`. Row excluded from HNSW queries; a `re_embed_worker` (5-min cron, separate PR) backfills.

Rejected — **(a) block with 503**: losing a manager's feedback on a Mistral blip is unacceptable. The self-improving loop depends on never-losing signal.

Rejected — **(c) local fallback model**: two embedding models in one column — cosine dedup threshold breaks. Never mix models in `operational_memory`.

### D10 — Metrics

`agent_action_log` fields per write: `embedding_latency_ms`, `embedding_backend` (`"mistral"` / `"pending"`), `dedup_hit` (`"tuple"` | `"cosine"` | `"none"`), `embedding_norm`.

Per recall: `recall_latency_ms`, `k_requested`, `k_returned`, `top_similarity`, `mean_similarity`, `source` (`"private"` | `"fb_pattern_fallback"` | `"empty"`), `cold_start` (bool).

Materialized view `memory_instrumentation_daily` (refreshed nightly): `hotel_id, date, writes, recalls, cold_start_pct, mean_top_similarity, p50_recall_ms, p95_recall_ms`. This is P1-4's dataset.

### D11 — Testing strategy

- **`FakeEmbeddingProvider`** in `backend/tests/providers/fake_embedding.py`: `embed(text) -> [b/255 for b in blake2b(text.encode(), digest_size=1024).digest()]`. Deterministic, 1024-d, no network.
- **Pure-logic unit tests**: payload builder, dedup decision tree, cold-start branch, `MemoryHit` mapping. No DB required — mock SQLAlchemy session.
- **Integration tests**: asyncpg-gated (`@pytest.mark.skipif`). Full loop: write feedback → assert non-zero embedding → recall with semantically-close query → assert hit.
- **Ablation harness seed** (for P1-4): test flipping `only_followed=True` vs `False` on identical corpus, recording top-k similarity deltas.

---

## 3. Open questions (deferred)

- **OQ1** — Embedding model change policy. `system_config.memory_embedding_dim` sketched in D3; migration path not detailed.
- **OQ2** — Memory TTL/decay. 3-year-old reflections may pollute recall after property renovation. Add `relevance_decay` scoring? (Phase 2.)
- **OQ3** — Should `recommendation_cache` participate in recall with a heavy penalty for "have I seen this situation before" dedup? (Current answer: no — D5.)

---

## 4. Implementation checklist (for the Dev agent)

1. **DB migration** `supabase/migrations/20260419000000_memory_instrumentation.sql`:
   - `ALTER TABLE operational_memory ALTER COLUMN embedding DROP NOT NULL;`
   - `ALTER TABLE operational_memory ADD COLUMN embedding_pending BOOLEAN NOT NULL DEFAULT FALSE;`
   - `ALTER TABLE operational_memory ADD CONSTRAINT embedding_or_pending CHECK (embedding IS NOT NULL OR embedding_pending = TRUE);`
   - `CREATE INDEX operational_memory_pending_idx ON operational_memory (created_at) WHERE embedding_pending = TRUE;`

2. **New file** `backend/app/services/memory_recall_service.py`: `MemoryHit` dataclass, `MemoryRecallService.recall()`, `_build_embedding_payload()`, `_cold_start_fallback()`.

3. **Edit** `backend/app/mcp_server.py`:
   - `tool_submit_feedback_to_memory`: real embedding (D1), structured payload (D2), tuple+cosine dedup (D7), D9 pending fallback, D10 logging.
   - `tool_get_recommendations_with_memory_context`: replace `created_at DESC` SELECT with `MemoryRecallService.recall()`, map `MemoryHit` → response dict, D10 logging.

4. **Edit** `backend/app/services/memory_service.py`: add `recall()` to `MemoryProvider` Protocol; add `PrivateMemoryProvider` class.

5. **New file** `backend/app/providers/memory_factory.py`: `get_memory_provider(db, embedding) -> MemoryProvider`.

6. **New file** `backend/tests/providers/fake_embedding.py`: `FakeEmbeddingProvider` (D11).

7. **New tests**: `test_memory_recall_service.py` (pure logic), `test_mcp_memory_instrumentation.py` (dispatcher-level, dedup paths, pending path).

8. **DB metric migration** `supabase/migrations/20260419000100_memory_instrumentation_metrics.sql`: `memory_instrumentation_daily` materialized view (D10).

9. **Docs**: `docs/mcp/memory-instrumentation.md` — embed payload format, env vars (`MEMORY_DEDUP_THRESHOLD`, `MEMORY_MIN_SIMILARITY`), cold-start behavior.

---

## 5. Decision record

| # | Decision | Chosen | Alternatives |
|---|----------|--------|--------------|
| D1 | Embed site | Inline on write | Outbox, batch |
| D2 | Embed payload | Structured concat | Verbatim reflection, notes-only |
| D3 | Query embed | Same singleton, no drift | Separate read model |
| D4 | Recall API | `MemoryRecallService` + `MemoryHit` | Extend MemoryService directly |
| D5 | Filters | type, since, only_followed | hotel_id only |
| D6 | Cold-start | Two-tier → `fb_patterns` | Empty array, cross-hotel (blocked) |
| D7 | Dedup | Tuple + cosine 0.98, 7-day window | Tuple only, cosine only |
| D8 | Phase 3 interface | `MemoryProvider.recall()` + factory | Refactor in Phase 3 |
| D9 | Mistral down | Null-embed + pending flag + worker | 503, local fallback model |
| D10 | Metrics | `agent_action_log` + daily MV | OTel only |
| D11 | Tests | `FakeEmbeddingProvider` (blake2b) + asyncpg-gated | Live Mistral in CI |
