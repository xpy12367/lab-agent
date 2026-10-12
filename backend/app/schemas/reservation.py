from pydantic import BaseModel, ConfigDict

class ReservationCreateRequest(BaseModel):
    """预约创建请求"""
    lab_id: int
    equipment_id: int | None = None
    date: str
    start_time: str
    end_time: str
    remark: str | None = None


class ReservationResponse(BaseModel):
    """预约响应参数"""
    id: int
    user_id: int
    user_name: str | None = None
    lab_id: int
    lab_name: str | None = None
    equipment_id: int | None = None
    equipment_name: str | None = None
    type: str | None = None
    date: str
    start_time: str
    end_time: str
    remark: str | None = None
    status: int
    model_config = ConfigDict(from_attributes=True)
    # 作用是让模型除了能读字典，还能读对象的属性。

class AuditReservationRequest(BaseModel):
    """审核状态返回"""
    status: int  #  1 | 2
