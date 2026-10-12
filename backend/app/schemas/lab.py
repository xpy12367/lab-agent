from pydantic import BaseModel, ConfigDict


class LabResponse(BaseModel):
    """实验室响应参数"""
    id: int
    name: str
    location: str | None = None
    capacity: int
    open_time: str | None = None
    close_time: str | None = None
    description: str | None = None
    img: str | None = None
    status: int

    model_config = ConfigDict(from_attributes=True)


class LabCreateRequest(BaseModel):
    """创建实验室请求参数"""
    name: str
    location: str | None = None
    capacity: int = 0
    open_time: str | None = None
    close_time: str | None = None
    description: str | None = None
    img: str | None = None
    status: int = 1


class LabUpdateRequest(BaseModel):
    """更新实验室请求参数"""
    name: str | None = None
    location: str | None = None
    capacity: int | None = None
    open_time: str | None = None
    close_time: str | None = None
    description: str | None = None
    img: str | None = None
    status: int | None = None
