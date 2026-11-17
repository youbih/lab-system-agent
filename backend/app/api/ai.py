from fastapi import APIRouter, Depends
from app.common.response import Response
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.ai import ChatRequest
from app.services import ai_services
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/ai", tags=["AI相关的API"])


@router.post("/chat")
def chat(data: ChatRequest, current_user: User = Depends(get_current_user)):
    messages = ai_services.build_messages(data)
    message = ai_services.chat(messages, session_id=f"user-{current_user.id}")
    return Response.success(data=message)


@router.post("/chat/stream")
async def chat_stream(
    data: ChatRequest, current_user: User = Depends(get_current_user)
):
    messages = ai_services.build_messages(data)
    return StreamingResponse(
        ai_services.stream_chat(messages, session_id=f"user-{current_user.id}"),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
