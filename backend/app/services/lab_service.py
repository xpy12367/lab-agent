from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.common.response import PageResponse
from app.models.lab import Lab
from app.schemas.lab import LabCreateRequest, LabResponse, LabUpdateRequest


def get_lab_page_list(
    db: Session,
    page: int,
    page_size: int,
    keywords: str | None = None,
    status: int | None = None,
):
    """分页模糊查询列表"""
    # select * from lab where name like '%计算机%';
    query = db.query(Lab)
    if keywords:
        query = query.filter(Lab.name.ilike(f"%{keywords}%"))
    if status:
        query = query.filter(Lab.status == status)
    total = query.count()
    items = (
        query.order_by(Lab.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PageResponse(
        list=[LabResponse.model_validate(item) for item in items], total=total
    )


def get_lab(db: Session, lab_id: int):
    """按 id 查询实验室详情"""
    lab = db.query(Lab).filter(Lab.id == lab_id).first()
    if not lab:
        raise BusinessException(message="实验室不存在")
    return LabResponse.model_validate(lab)


def create_lab(db: Session, data: LabCreateRequest):
    """创建实验室"""
    exists = db.query(Lab).filter(Lab.name == data.name).first()
    if exists:
        raise BusinessException(message="实验室名称已存在")

    lab = Lab(**data.model_dump())  
    # data.model_dump()：把 Pydantic 请求对象 data 转换为字典，例如 {"name": "物理实验室", "capacity": 30}
    # **:相当于把{"key1": value1, "key2": value2}-> Lab(key1=value1, key2=value2)
    db.add(lab)
    db.commit()
    db.refresh(lab)
    return LabResponse.model_validate(lab)


def update_lab(db: Session, lab_id: int, data: LabUpdateRequest):
    """更新实验室"""
    lab = db.query(Lab).filter(Lab.id == lab_id).first()
    if not lab:
        raise BusinessException(message="实验室不存在")

    payload = data.model_dump(exclude_none=True)  # exclude_none=True:去掉值为 None 的字段
    # if "name" in payload:
    #     exists = (
    #         db.query(Lab).filter(Lab.name == payload["name"], Lab.id != lab_id).first()
    #     )
    #     if exists:
    #         raise BusinessException(message="实验室名称已存在")

    for field, value in payload.items():
        setattr(lab, field, value) # setattr(lab, field, value) # setattr() 函数用于设置对象的属性值，相当于 lab.field = value
    db.commit()
    db.refresh(lab)
    return LabResponse.model_validate(lab)


def delete_lab(db: Session, lab_id: int):
    """删除实验室"""
    lab = db.query(Lab).filter(Lab.id == lab_id).first()
    if not lab:
        raise BusinessException(message="实验室不存在")
    db.delete(lab)
    db.commit()
