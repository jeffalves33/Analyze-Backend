# routers/chat_router.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.chat_service import ChatService

router = APIRouter()

class ChatRequest(BaseModel):
    customer_id: int
    client_name: str
    client_id: int
    prompt: str
    history: list[dict] = []

chat_service = ChatService()

@router.post("/chat/")
async def chat_endpoint(request: ChatRequest):
    try:
        response = chat_service.generate_chat_response(
            customer_id=request.customer_id,
            client_name=request.client_name,
            client_id=request.client_id,
            prompt=request.prompt,
            history=request.history
        )
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))