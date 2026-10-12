# Mapped  —— 用来给字段标注 Python 类型（例如 str、int）
# mapped_column —— 用来描述字段在数据库里的具体规则（长度、是否可为空等）
from sqlalchemy.orm import Mapped, mapped_column

# String —— 对应数据库里的字符串类型（可以指定最大长度）
from sqlalchemy import String

# 导入所有数据表模型类的基类，继承它就能自动拥有 id、create_time、update_time 三个公共字段
from app.database import Base


# User 类对应数据库中的一张“用户信息表”
# 在 SQLAlchemy 里，一个类 = 一张表，类的一个属性 = 表的一个字段
class User(Base):
    # __tablename__ 指定这张表在数据库中的真实表名
    __tablename__ = "users"
    # __table_args__ 放置表的额外配置，这里给表本身加一条注释（方便查看数据库结构时理解）
    __table_args__ = {"comment": "用户信息表"}

    # 下面每个字段都是同样的写法：
    # Mapped[类型] 表示这个字段在 Python 中的类型，mapped_column(...) 描述它在数据库中的规则
    # nullable=False 表示这个字段不能为空（必填），不写则默认可以为空

    # 账号：最长 50 个字符，必填
    username: Mapped[str] = mapped_column(String(50), comment="账号", nullable=False)
    # 密码：最长 50 个字符，必填（真实项目中一般存加密后的密码，不存明文）
    password: Mapped[str] = mapped_column(String(255), comment="密码", nullable=False)
    # 名称：用户的显示名字，最长 50 个字符，必填
    name: Mapped[str] = mapped_column(String(50), comment="名称", nullable=False)
    # 角色：用来区分用户身份，目前有 student（学生）和 admin（管理员）两种，必填
    role: Mapped[str] = mapped_column(
        String(50), comment="角色：student-学生，admin-管理员", nullable=False
    )
    # 邮箱：类型写成 str | None，表示“字符串或者空值”，也就是这个字段可以为空（选填）
    email: Mapped[str | None] = mapped_column(String(50), comment="邮箱")
    # 手机号：同上，选填
    phone: Mapped[str | None] = mapped_column(String(50), comment="手机号")
    # 头像：一般存头像图片的地址（URL），选填
    avatar: Mapped[str | None] = mapped_column(String(50), comment="头像")
    # 状态：用数字表示账号是否可用，0-禁用、1-正常
    # default=1 表示新增用户时如果没传这个值，就默认为 1（正常状态）
    status: Mapped[int] = mapped_column(default=1, comment="状态：0-禁用，1-正常")
