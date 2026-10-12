"""应用配置模块:从 .env 读取环境变量,集中管理后端配置。"""

from mmap import ALLOCATIONGRANULARITY
from tkinter import ALL
from uuid import MAX

from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

# 后端项目根目录(app 的上一级),用于定位 .env 文件
BASE_DIR = Path(__file__).resolve().parent.parent  # 后端项目的根路径


class Setting(BaseSettings):
    """应用配置项,字段名与环境变量名一一对应(大小写不敏感)。"""

    DATABASE_URL: str  # 数据库连接串(DSN),取值来自 .env 中的 DATABASE_URL
    JWT_SECRET_KEY: str
    JWT_EXPIRE_HOURS: int = 24
    JWT_ALGORITHM: str = "HS256"
    LLM_API_KEY: str
    LLM_BASE_URL: str
    LLM_MODEL: str

    # 声明配置文件的位置与编码,BaseSettings 会据此读取 .env
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8"
    )


# 全局配置单例,其他模块直接 from app.config import settings 使用
settings = Setting()

UPLOAD_DIR = BASE_DIR / "uploads"  # 上传文件的存储目录
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)  # 确保目录存在,不存在则创建
MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 上传文件的最大大小,单位:字节,默认100MB

ALLOWED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".txt",
}  # 允许上传的文件类型
