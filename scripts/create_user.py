"""Admin-only user creation script (HOS-149 AC6).

Creates a user directly via the fastapi-users UserManager, bypassing the
disabled public /auth/register endpoint.

Usage:
    cd backend
    python ../scripts/create_user.py --email admin@example.com --password changeme123

Requirements: DATABASE_URL env var must be set.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

# Ensure backend/ is on the path when running from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


async def create_user(email: str, password: str, is_superuser: bool) -> None:
    from fastapi_users.exceptions import UserAlreadyExists

    from app.db.session import async_session_maker
    from app.services.users import get_user_db, get_user_manager

    async with async_session_maker() as session:
        async for user_db in get_user_db(session):
            async for user_manager in get_user_manager(user_db):
                from fastapi_users.schemas import BaseUserCreate

                class _Create(BaseUserCreate):
                    pass

                try:
                    user = await user_manager.create(
                        _Create(
                            email=email,
                            password=password,
                            is_superuser=is_superuser,
                            is_active=True,
                            is_verified=True,
                        )
                    )
                    print(f"User created: id={user.id} email={user.email} superuser={user.is_superuser}")
                except UserAlreadyExists:
                    print(f"User already exists: {email}", file=sys.stderr)
                    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an Aetherix user (admin-only)")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--superuser", action="store_true", default=False)
    args = parser.parse_args()

    if not os.getenv("DATABASE_URL"):
        print("ERROR: DATABASE_URL env var is required.", file=sys.stderr)
        sys.exit(1)

    asyncio.run(create_user(args.email, args.password, args.superuser))


if __name__ == "__main__":
    main()
