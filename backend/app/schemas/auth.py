from pydantic import BaseModel
from app.schemas.user import UserResponse


class LoginRequest(BaseModel):
    """登录请求参数"""
    username: str
    password: str


class LoginResponse(BaseModel):
    """登录响应参数"""
    token: str
    user: UserResponse


class RegisterRequest(BaseModel):
    """注册请求参数"""
    username: str
    password: str
    name: str | None = None
