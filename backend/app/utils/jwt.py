from datetime import datetime, timedelta
import jwt
from app.config import settings


def create_access_token(user_id: int) -> str:
    """创建JWT token"""
    expire = datetime.now() + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    # 生成token的过期时间，是当前时间加上配置的过期时间
    payload = {"user_id": user_id, "exp": expire}  # exp是固定key，不能写成别的
    # 生成token的payload，包含用户ID和过期时间
    return jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )  # 三个参数 = 内容 + 密钥 + 算法


def decode_access_token(token: str) -> dict:
    """解析jwt token"""
    return jwt.decode(
        token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
    )  # 三个参数 = 内容 + 密钥 + 算法
