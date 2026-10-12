import os
import time
from pathlib import Path
import uuid
import shutil
from fastapi import APIRouter, File, UploadFile

from app.common.exceptions import BusinessException
from app.common.response import Response
from app.config import ALLOWED_EXTENSIONS, MAX_UPLOAD_SIZE, UPLOAD_DIR
from app.schemas.files import FileResponse

router = APIRouter(prefix="/files", tags=["文件管理"])


@router.post("/upload")
def upload(
    file: UploadFile = File(...),
):  # File(...):必填的上传文件   UploadFile 对象:（带 .filename、.size、.file 等属性）
    """文件上传的接口"""
    if not file.filename:
        raise BusinessException(message="文件名不能为空")

    # 原始的文件名  用户头像.jpg
    orignal_name = os.path.basename(file.filename)
    # 文件后缀 .jpg
    ext = Path(orignal_name).suffix.lower()  # .suffix:取「最后一个后缀」  lower():小写
    if ext not in ALLOWED_EXTENSIONS:
        raise BusinessException(message=f"不自持的文件后缀：{ext}")
    # 文件大小校验
    if file.size and file.size > MAX_UPLOAD_SIZE:
        raise BusinessException(
            message=f"文件不能超过 {MAX_UPLOAD_SIZE // 1024 // 1024}MB"
        )
    # 设置唯一的文件名称   199323213213_ddadaqwerq.jpg
    disk_name = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}{ext}"
    # uuid.uuid4(): 生成一个随机 UUID（全球唯一的随机 ID）
    # hex[:8]: 取 uuid 的前 8 位,保证文件名唯一,避免覆盖
    # time.time() * 1000: 取当前时间戳(从 1970 年至今的秒数，带小数)
    # 文件存储的实际路径
    save_path = UPLOAD_DIR / disk_name

    # 流式写文件
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
        # 把上传对象里的字节流，一块块地拷贝到f

    return Response.success(
        data=FileResponse(
            original_filename=orignal_name,
            disk_name=disk_name,
            size=file.size,
            url=f"/uploads/{disk_name}",
        )
    )
