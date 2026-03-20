from fastapi import APIRouter, Depends
from app.core.security import auth_backend, fastapi_users
from app.db.models import User
from pydantic import BaseModel, EmailStr
import uuid

router = APIRouter(prefix="/auth", tags=["auth"])

from fastapi_users import schemas

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

router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
)

@router.get("/me", response_model=UserRead)
async def get_me(user: User = Depends(fastapi_users.current_user(active=True))):
    return user
