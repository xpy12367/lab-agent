from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    """用户响应参数"""
    id: int
    username: str
    name: str
    role: str
    email: str | None = None
    phone: str | None = None
    avatar: str | None = None
    status: int

    model_config = ConfigDict(from_attributes=True)
    # 作用是让模型除了能读字典，还能读对象的属性。

class UserCreateRequest(BaseModel):
    """创建用户请求参数"""
    username: str
    password: str = "123"
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    avatar: str | None = None
    role: str = "student"
    status: int = 1


class UserUpdateRequest(BaseModel):
    """修改用户请求参数"""
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    avatar: str | None = None
    role: str | None = None
    status: int | None = None


class PasswordUpdateRequest(BaseModel):
    """修改密码请求参数"""

    old_password: str
    new_password: str
