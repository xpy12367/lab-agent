from fastapi import APIRouter, Depends
from app.common.response import Response
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.ai import ChatMessage, ChatRequest
from app.services import ai_service
from sqlalchemy.orm import Session
from app.database import get_db

router = APIRouter(prefix="/ai", tags=["AI相关的API"])
@router.post("/chat")
def chat(data: ChatRequest, current_user: User = Depends(get_current_user),db:Session = Depends(get_db)):
    content = ai_service.chat(db,data)
    return Response.success(data=ChatMessage(role="assistant", content=content))
