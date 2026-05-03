import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi_users import schemas

from app.core.security import auth_backend, fastapi_users
from app.db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class UserRead(schemas.BaseUser[uuid.UUID]):
    full_name: str | None = None
    department_role: str | None = None

class UserCreate(schemas.BaseUserCreate):
    full_name: str | None = None
    department_role: str | None = None

class UserUpdate(schemas.BaseUserUpdate):
    full_name: str | None = None
    department_role: str | None = None

router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/jwt",
)

# AC6 (HOS-149): public registration disabled by default.
# Set REGISTRATION_ENABLED=true only in controlled environments.
# Admin user creation: use scripts/create_user.py instead.
if os.getenv("REGISTRATION_ENABLED", "false").lower() == "true":
    router.include_router(fastapi_users.get_register_router(UserRead, UserCreate))
else:
    @router.post("/register", status_code=403)
    async def register_disabled() -> None:
        raise HTTPException(
            status_code=403,
            detail="Public registration is disabled. Use the admin create_user script.",
        )

@router.get("/me", response_model=UserRead)
async def get_me(user: User = Depends(fastapi_users.current_user(active=True))):
    return user
