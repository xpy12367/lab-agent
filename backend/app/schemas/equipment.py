from pydantic import BaseModel, ConfigDict


class EquipmentResponse(BaseModel):
    """设备响应参数"""
    id: int
    lab_id: int
    lab_name: str | None = None
    name: str
    description: str | None = None
    img: str | None = None
    spec: str | None = None
    quantity: int
    status: int

    model_config = ConfigDict(from_attributes=True)


class EquipmentCreateRequest(BaseModel):
    """设备创建请求参数"""
    lab_id: int
    name: str
    description: str | None = None
    img: str | None = None
    spec: str | None = None
    quantity: int = 1
    status: int = 1


class EquipmentUpdateRequest(BaseModel):
    """设备更新请求参数"""
    lab_id: int | None = None
    name: str | None = None
    description: str | None = None
    img: str | None = None
    spec: str | None = None
    quantity: int | None = None
    status: int | None = None
