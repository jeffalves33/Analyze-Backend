# routers/chat_router.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.chat_service import ChatService

router = APIRouter()

class ChatRequest(BaseModel):
    client_id: int
    prompt: str
    history: list[dict] = []

chat_service = ChatService()

@router.post("/chat/")
async def chat_endpoint(request: ChatRequest):
    try:
        response = chat_service.generate_chat_response(
            client_id=request.client_id,
            prompt=request.prompt,
            history=request.history
        )
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))