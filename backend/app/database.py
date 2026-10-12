# 从 SQLAlchemy 中导入需要的工具：
# sessionmaker  —— 用来创建“数据库会话”的工厂
# DeclarativeBase —— 所有数据表模型类的基类
# Mapped / mapped_column —— 用一种带类型提示的方式定义表的字段
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Mapped, mapped_column
# create_engine —— 创建数据库引擎（连接数据库的核心对象）
# DateTime —— 对应数据库里的 DATETIME 类型
from sqlalchemy import create_engine, DateTime
# 从项目配置中读取设置（例如数据库地址）
from app.config import settings
# Python 标准库的日期时间类型，用来记录创建/更新时间
from datetime import datetime

# 创建数据库引擎：settings.DATABASE_URL 里保存了数据库的连接地址（如 sqlite/mysql 的连接串）
# 引擎可以理解为“数据库连接池的入口”，后续所有数据库操作都通过它进行
engine = create_engine(settings.DATABASE_URL)

# 数据库session会话的连接工厂
# sessionmaker 是一个“工厂函数”：调用 SessionLocal() 就会得到一个新的数据库会话对象
# autoflush=False 表示查询时不会自动把内存中的改动立刻写入数据库，交给开发者手动控制
SessionLocal = sessionmaker(bind=engine, autoflush=False)


# 获取数据库会话的依赖函数（FastAPI 中通过 Depends(get_db) 使用）
def get_db():
    # 创建一个新的数据库会话
    db = SessionLocal()
    try:
        # yield 把会话交给调用方（接口函数）使用；
        # 用 yield 而不是 return，是为了让接口执行完后再回到这里执行 finally
        yield db
    finally:
        # 无论接口正常结束还是抛异常，都一定要关闭会话，释放数据库连接
        db.close()


# 所有数据表模型类的基类，继承它就能自动获得下面这几个公共字段
class Base(DeclarativeBase):
    # id：主键。primary_key=True 表示主键；autoincrement=True 表示自增
    # comment 是字段注释；sort_order=-1 让它在生成的文档/表结构里排在最前面
    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True, comment="主键ID", sort_order=-1
    )
    # create_time：创建时间。新增一条记录时，自动填入当前时间（default=datetime.now）
    create_time: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, comment="创建时间", sort_order=1
    )
    # update_time：更新时间。新增时同样填当前时间，
    # onupdate=datetime.now 表示每次修改这条记录时，自动刷新为最新时间
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        comment="更新时间",
        sort_order=2,
    )
