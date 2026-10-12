from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer
from app.database import Base


class Lab(Base):
    __tablename__ = "labs"
    __table_args__ = {"comment": "实验室信息表"}

    name: Mapped[str] = mapped_column(String(50), comment="实验室名称")
    # Mapped[str]：类型注解，表示这个字段在 Python 中是字符串，并由 SQLAlchemy 映射到数据库。
    # mapped_column(...)：定义对应的数据库列。
    # nullable=False：数据库中这一列不允许为空，也就是必须有值。
    location: Mapped[str | None] = mapped_column(
        String(100), comment="位置", nullable=True
    )# nullable=True：数据库中这一列允许为空，也就是可以没有值。
    capacity: Mapped[int] = mapped_column(Integer, comment="容纳人数", default=0)
    # 是 SQLAlchemy 提供的整数类型，用于表示数据库中的整数字段。
    open_time: Mapped[str | None] = mapped_column(
        String(20), comment="开放开始时间", nullable=True
    )
    close_time: Mapped[str | None] = mapped_column(
        String(20), comment="开放结束时间", nullable=True
    )
    description: Mapped[str | None] = mapped_column(String(500), comment="简介", nullable=True)
    img: Mapped[str | None] = mapped_column(String(200), comment="封面图", nullable=True)
    status: Mapped[int] = mapped_column(default=1, comment="状态：0-关闭，1-开放")
