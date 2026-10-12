from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_admin,get_current_user
from app.models.lab import Lab
from app.models.user import User
from app.schemas.lab import LabCreateRequest, LabUpdateRequest
from app.services import lab_service

router = APIRouter(prefix="/lab", tags=["实验室管理"])


@router.get("/list")
def get_lab_list(
    page: int = 1,
    page_size: int = 10,
    keywords: str | None = None,
    status: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """分页模糊查询列表"""
    res = lab_service.get_lab_page_list(db, page, page_size, keywords, status)
    return Response.success(data=res)


@router.get("/{lab_id}")
def get_lab(
    lab_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """按 id 查询实验室详情"""
    res = lab_service.get_lab(db, lab_id)
    return Response.success(data=res)


@router.post("")
def create_lab(
    data: LabCreateRequest,
    current_user: Lab = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """创建实验室"""
    res = lab_service.create_lab(db, data)
    return Response.success(data=res)


@router.put("/{lab_id}")
def update_lab(
    lab_id: int,
    data: LabUpdateRequest,
    current_user: Lab = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """更新实验室"""
    res = lab_service.update_lab(db, lab_id, data)
    return Response.success(data=res)


@router.delete("/{lab_id}")
def delete_lab(
    lab_id: int,
    current_user: Lab = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """删除实验室"""
    lab_service.delete_lab(db, lab_id)
    return Response.success(message="删除成功")
