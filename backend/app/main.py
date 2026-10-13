import traceback
from fastapi import FastAPI, HTTPException
import asyncio
from fastapi.concurrency import asynccontextmanager
from app.services import kb_service, reservation_service
from fastapi.exceptions import RequestValidationError
from app.models.user import User
from app.models.lab import Lab
from app.models.equipment import Equipment
from app.models.reservation import Reservation
from app.database import Base, engine
from app.api import api
from fastapi.staticfiles import StaticFiles
from app.config import UPLOAD_DIR
from starlette.middleware.cors import CORSMiddleware
from app.common.exceptions import (
    BusinessException,
    bussiness_excpetion_hadler,
    http_excpetion_hadler,
    validation_excpetion_hadler,
    global_excpetion_hadler,
)

Base.metadata.create_all(bind=engine)  # 自动帮我们创建数据库和数据库表
# Base.metadata：保存继承自 Base 的模型所描述的表结构。
# create_all(...)：创建这些表；如果表已经存在，通常不会重复创建，也不会自动修改已有表结构。
# bind=engine：指定要连接哪个数据库。


# lifespan 是 FastAPI 的“生命周期”函数，用来管理整个应用的启动和关闭
# @asynccontextmanager 把它包装成异步上下文管理器，让它可以用 yield 分成前后两段
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 预热向量库：模型加载（约 15s）挪到启动阶段，避免首个请求超过前端 30s 超时
    try:
        await asyncio.to_thread(kb_service.warmup)  # to_thread：别阻塞事件循环
    except Exception:
        traceback.print_exc()

    # yield 之前：应用启动时执行
    # 创建一个后台任务运行过期扫描（不 await，所以不会阻塞启动流程）
    task = asyncio.create_task(
        reservation_service.run_expire_scan()
    )  # 启动项目开启异步的扫描任务
    try:
        # yield 处：应用正式开始对外提供服务，程序会一直停在这里
        yield

    finally:
        # 关闭项目时：取消后台任务
        task.cancel()  # 关闭项目同时取消异步任务
        await asyncio.gather(
            task, return_exceptions=True
        )  # 取消任务,不再把CanceledError抛给lifespan


# 全局唯一的 FastAPI 实例（只能创建一次，重复创建会丢掉已注册的路由）
app = FastAPI(lifespan=lifespan)

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # 允许的前端源，不要直接写 ["*"]
    allow_credentials=True,  # ✅ 关键：允许前端携带 Authorization token
    allow_methods=["*"],  # 允许所有请求方法 GET POST PUT DELETE OPTIONS
    allow_headers=["*"],  # 允许所有请求头（包含Authorization）
)

# 注册路由：把 api 这个 APIRouter 里定义的所有接口挂到 app 上
# include_router 相当于“把子路由表合并进主应用”，之后 /xxx 才能被访问到
app.include_router(api)

# 注册异常处理器：为不同类型的异常绑定对应的处理函数
# 当代码抛出这些异常时，FastAPI 会调用对应的 handler 统一返回 JSON 格式的错误信息

# 业务异常：我们自己主动抛出的可预期错误（如“预约记录不存在”），返回业务提示
app.add_exception_handler(BusinessException, bussiness_excpetion_hadler)
# HTTP 异常：如 404、401 等标准的 HTTPException
app.add_exception_handler(HTTPException, http_excpetion_hadler)
# 参数校验异常：请求参数不符合 Pydantic 模型要求时触发（FastAPI 内部抛出）
app.add_exception_handler(RequestValidationError, validation_excpetion_hadler)
# 全局的异常兜底：捕获上面都没匹配到的其他所有异常，必须放在最后注册！！
# 原因：异常处理器按“具体→宽泛”的顺序匹配，Exception 是最宽泛的，放前面会拦截掉其他处理器
app.add_exception_handler(Exception, global_excpetion_hadler)

# 挂载静态资源：/uploads/xxx.jpg → uploads/xxx.jpg
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get("/")
def root():
    return {"message": "Hello FastAPI"}
