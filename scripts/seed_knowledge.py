#!/usr/bin/env python3
"""Seed initial F&B operational insights into the ``operational_memory`` table.

Replaces the previous Backboard.io seeding.  Run once after applying
the pgvector migrations and before the first pilot session.

Usage
-----
    cd /path/to/repo/backend
    python ../scripts/seed_knowledge.py

Requirements
------------
- DATABASE_URL  — Supabase PostgreSQL connection string
- MISTRAL_API_KEY — for generating embeddings (optional; zeros used in dev)
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

# Ensure the backend app package is on the path when running from repo root
_backend_dir = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(_backend_dir))

from app.services.memory_service import MemoryService  # noqa: E402

INITIAL_INSIGHTS = [
    {
        "tenant_id": "pilot_hotel",
        "reflection": (
            "The local Tuesday market significantly increases lunch walk-ins; "
            "increase server count projections by 2 on Tuesdays."
        ),
    },
    {
        "tenant_id": "pilot_hotel",
        "reflection": (
            "Friday night guests are predominantly wine-focused; ensure a second "
            "Sommelier is scheduled if predicted covers exceed 140."
        ),
    },
    {
        "tenant_id": "pilot_hotel",
        "reflection": (
            "Historical data shows a 15% revenue lift when cross-selling the "
            "'Chef's Table' during mid-week surpluses."
        ),
    },
]


async def seed() -> None:
    memory = MemoryService()
    print(f"Seeding {len(INITIAL_INSIGHTS)} insights into operational_memory…")

    for insight in INITIAL_INSIGHTS:
        try:
            await memory.store_reflection(
                tenant_id=insight["tenant_id"],
                reflection=insight["reflection"],
            )
            preview = insight["reflection"][:60]
            print(f"  OK  {preview}…")
        except Exception as exc:
            print(f"  ERR {insight['reflection'][:60]}…  ({exc})")


if __name__ == "__main__":
    if not os.getenv("DATABASE_URL"):
        print("ERROR: DATABASE_URL not set.")
        sys.exit(1)
    asyncio.run(seed())
