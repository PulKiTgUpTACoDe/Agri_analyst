from fastapi import APIRouter
from app.models.chat_models import ChatRequest, ChatResponse

router = APIRouter()

@router.post("/")
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    # Temporary response (we’ll integrate LangChain later)
    answer = f"You asked: '{request.query}'. I'll connect data.gov.in soon!"
    return ChatResponse(answer=answer, citations=[])
