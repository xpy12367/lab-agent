from pydantic import BaseModel


class FileResponse(BaseModel):
    """文件响应参数"""
    original_filename: str
    disk_name: str
    size: int
    url: str
