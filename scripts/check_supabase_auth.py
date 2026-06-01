r"""One-shot diagnostic: validate Supabase pooler auth with asyncpg (same driver as Fly).

Reads PGPASSWORD from env, prints OK + identity on success, or FAIL + error class on failure.
Run via: backend\.venv\Scripts\python.exe scripts\check_supabase_auth.py
"""

import asyncio
import os
import sys

import asyncpg


HOST = os.environ.get("PGHOST", "aws-1-eu-north-1.pooler.supabase.com")
PORT = int(os.environ.get("PGPORT", "5432"))
USER = os.environ.get("PGUSER", "postgres.imfrvrngxbtotmfbdtpf")
DB = os.environ.get("PGDATABASE", "postgres")


async def main() -> int:
    pwd = os.environ.get("PGPASSWORD")
    if not pwd:
        print("FAIL: PGPASSWORD not set in env", file=sys.stderr)
        return 2

    print(f"Connecting: user={USER} host={HOST}:{PORT} db={DB}")
    try:
        conn = await asyncpg.connect(
            host=HOST,
            port=PORT,
            user=USER,
            password=pwd,
            database=DB,
            timeout=10,
        )
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    try:
        row = await conn.fetchrow("SELECT current_user AS u, current_database() AS d, version() AS v")
        print(f"OK: user={row['u']} db={row['d']}")
        print(f"     {row['v'][:60]}...")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
