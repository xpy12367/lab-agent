from sqlalchemy.orm import Session
from datetime import datetime
from app.database import SessionLocal
import asyncio
from app.common.exceptions import BusinessException
from app.common.response import PageResponse
from app.models.equipment import Equipment
from app.models.lab import Lab
from app.models.reservation import Reservation
from app.models.user import User
from app.schemas.reservation import ReservationCreateRequest, ReservationResponse


def create_reservation(db: Session, current_user: User, data: ReservationCreateRequest):
    """创建预约记录"""
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")
    if data.date < current_date:
        raise BusinessException(message="预约日期不能小于当前的日期")
    if data.end_time < data.start_time:
        raise BusinessException(message="预约的结束时间不能小于开始时间")
    if data.date == current_date and data.start_time < current_time:
        raise BusinessException(message="预约开始时间不能小于当前的时间")
    lab = db.query(Lab).filter(Lab.id == data.lab_id).first()
    if not lab:
        raise BusinessException(message="实验室不存在")
    if lab.status != 1:
        raise BusinessException(message="实验室已关闭")
    if lab.open_time and data.start_time < lab.open_time:
        raise BusinessException(message="预约时间不能早于实验室的开放时间")
    if lab.close_time and data.end_time > lab.close_time:
        raise BusinessException(message="预约时间不能晚于实验室的关闭时间")
    # equipment_id 不为空 则表示这次是预约的实验室设备
    if data.equipment_id:
        equipment = (
            db.query(Equipment).filter(Equipment.id == data.equipment_id).first()
        )
        if not equipment:
            raise BusinessException(message="实验室设备不存在")
        if equipment.status != 1:
            raise BusinessException(message="实验室设备正在维修")
    # 实验室或者设备是否是可预约的状态
    query = db.query(Reservation).filter(
        Reservation.lab_id == data.lab_id,
        Reservation.date == data.date,
        Reservation.status.in_([0, 1]),  # 0表示待审核  1已通过
        Reservation.start_time < data.end_time,
        Reservation.end_time > data.start_time,
    )
    if data.equipment_id:
        query = query.filter(
            Reservation.equipment_id == data.equipment_id
        )  # 预约实验室设备
    else:
        query = query.filter(Reservation.equipment_id.is_(None))  # 只预约实验室
    res = query.first()
    if res:
        raise BusinessException(message="该时段已预约")
    resvervation_model = Reservation(
        user_id=current_user.id,
        lab_id=data.lab_id,
        equipment_id=data.equipment_id,
        date=data.date,
        start_time=data.start_time,
        end_time=data.end_time,
        remark=data.remark,
        status=0,
    )
    db.add(resvervation_model)
    db.commit()


def get_reservation_page_list(
    db: Session,
    current_user: User,
    page: int,
    page_size: int,
    status: int | None = None,
):
    """查询预约的记录"""
    query = db.query(Reservation)
    if current_user.role != "admin":
        query = query.filter(Reservation.user_id == current_user.id)
    if status is not None:
        query = query.filter(Reservation.status == status)
    total = query.count()
    items = (
        query.order_by(Reservation.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    result = []
    for item in items:
        res = ReservationResponse.model_validate(item)
        res.user_name = item.user.name if item.user else None
        res.lab_name = item.lab.name if item.lab else None
        res.equipment_name = item.equipment.name if item.equipment else None
        res.type = "设备" if item.equipment_id else "实验室"
        result.append(res)

    return PageResponse(list=result, total=total)


def cancel_reservation(db: Session, current_user: User, reservation_id: int):
    """学生取消预约"""
    item = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not item:
        raise BusinessException(message="预约记录不存在")
    if item.user_id != current_user.id:
        raise BusinessException(message="无权限", code=403)
    if item.status != 0:
        raise BusinessException(message="当前状态无法取消")
    item.status = 3
    db.commit()


def audit_reservation(db: Session, reservation_id: int, status: int):
    """管理员审核预约"""
    if status not in [1, 2]:
        raise BusinessException(message="审核状态错误")
    item = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not item:
        raise BusinessException(message="预约记录不存在")
    if item.status != 0:
        raise BusinessException(message="当前状态不支持审核")
    item.status = status
    db.commit()


def expire_pending_reservations():
    """批量取消过期的预约单"""
    # 创建数据库会话，用于查询待处理预约并更新过期状态
    db = SessionLocal()
    try:
        # 获取当前时间，用于判断预约是否已过期
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        now_time = now.strftime("%H:%M")

        # 查询所有状态为待处理的预约（status == 0）
        items = db.query(Reservation).filter(Reservation.status == 0).all()

        # 标记是否有预约状态被更新
        changed = False

        # 遍历预约，判定是否已经超过有效时间
        for item in items:
            # 如果预约日期早于今天，或者当天已到结束时间，则视为已过期
            if item.date < today or (item.date == today and item.end_time <= now_time):
                item.status = 3  # 将状态更新为已过期（按业务约定 status=3 表示过期）
                changed = True

        # 只在确实有更新时提交事务，避免无意义的数据库写入
        if changed:
            db.commit()
    finally:
        # 确保数据库连接在函数结束前关闭，避免连接泄漏
        db.close()


async def run_expire_scan():
    """一分钟扫描一次取消预约业务"""
    # 后台常驻任务：不断循环扫描并处理已过期的预约
    while True:
        try:
            # 执行一次过期扫描，把超时的待处理预约标记为已过期
            expire_pending_reservations()
        except Exception as e:
            print(f"过期扫描失败: {e}")

        # 异步休眠 60 秒，让出事件循环，避免阻塞其他请求
        await asyncio.sleep(60)  # await 表示「在这里等待，但等待期间不影响别人」。
