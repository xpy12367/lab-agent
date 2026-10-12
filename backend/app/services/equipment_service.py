from operator import or_
from app.common.exceptions import BusinessException
from app.common.response import PageResponse
from app.models.equipment import Equipment
from app.models.lab import Lab
from app.schemas.equipment import (
    EquipmentResponse,
    EquipmentCreateRequest,
    EquipmentUpdateRequest,
)
from sqlalchemy.orm import Session


def get_equipment_page_list(
    db: Session,  # 数据库会话，用于执行查询
    page: int,  # 页码，从 1 开始
    page_size: int,  # 每页条数
    keywords: str | None = None,  # 关键字，按设备名称模糊匹配；不传表示不过滤
    lab_id: int | None = None,  # 实验室 id，只看某个实验室的设备；不传表示不过滤
):
    """分页模糊查询列表"""
    # select * from equipment where name like '%计算机%';
    query = db.query(Equipment)
    # 按实验室筛选：lab_id 为 0/None 时视为不过滤
    if lab_id:
        query = query.filter(Equipment.lab_id == lab_id)
    # 按名称模糊查询：ilike 不区分大小写，% 表示任意字符
    if keywords:
        query = query.filter(Equipment.name.ilike(f"%{keywords}%"))

    # 先统计满足条件的总条数（用于前端分页组件显示总数），必须在分页之前统计
    total = query.count()
    # 按 id 倒序（新数据在前），再按页码计算偏移量取出当前页数据
    # offset = 前面跳过的条数 = (页码 - 1) * 每页条数
    items = (
        query.order_by(Equipment.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # 把数据库实体转成响应模型，并补充关联的实验室名称
    result = []
    for item in items:
        res = EquipmentResponse.model_validate(item)
        # item.lab 是关联查询出来的实验室对象，可能为空，所以要判空
        res.lab_name = item.lab.name if item.lab else None
        result.append(res)
    return PageResponse(list=result, total=total)


def create_equipment(db: Session, data: EquipmentCreateRequest):
    """新增设备"""
    exist = db.query(Equipment).filter(Equipment.name == data.name).first()
    if exist:
        raise BusinessException(message="实验室设备已存在")
    equipment = Equipment(**data.model_dump())
    # data.model_dump()：把 Pydantic 请求对象 data 转换为字典，例如 {"name": "物理实验室", "capacity": 30}
    # **:相当于把{"key1": value1, "key2": value2}-> Lab(key1=value1, key2=value2)
    db.add(equipment)
    db.commit()
    db.refresh(equipment)
    res = EquipmentResponse.model_validate(equipment)
    res.lab_name = equipment.lab.name if equipment.lab else None
    return res


def update_equipment(db: Session, equipment_id: int, data: EquipmentUpdateRequest):
    """更新设备"""
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not equipment:
        raise BusinessException(message="实验室设备不存在")
    payload = data.model_dump(exclude_none=True)
    lab_id = payload.get("lab_id", equipment.lab_id)
    name = payload.get("name", equipment.name)
    lab = db.query(Lab).filter(Lab.id == lab_id).first()
    if not lab:
        raise BusinessException(message="实验室不存在")
    exist = (
        db.query(Equipment)
        .filter(
            Equipment.lab_id == lab_id,
            Equipment.name == name,
            Equipment.id != equipment.id,
        )
        .first()
    )
    if exist:
        raise BusinessException(message="同一个实验室不能存在同名的设备")

    for filed, value in payload.items():
        setattr(equipment, filed, value)

    db.commit()
    db.refresh(equipment)
    res = EquipmentResponse.model_validate(equipment)
    res.lab_name = equipment.lab.name if equipment.lab else None
    return EquipmentResponse.model_validate(equipment)


def delete_equipment(db: Session, equipment_id: int):
    """删除设备"""
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not equipment:
        raise BusinessException(message="实验室设备不存在")
    db.delete(equipment)
    db.commit()
