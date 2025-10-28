"""Simplified FastAPI application using LangGraph."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager

from app.graph.workflow import get_workflow
from app.core.api_client import get_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    print("[STARTUP] Initializing workflow...")
    get_workflow()
    yield
    # Shutdown
    print("[SHUTDOWN] Closing connections...")
    client = get_client()
    await client.close()


app = FastAPI(title="Agri Analyst API", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/ask")
async def ask(req: AskRequest):
    """Process agricultural query using LangGraph workflow."""
    result = await get_workflow().ainvoke({
        "question": req.question,
        "intent": None,
        "raw_data": {},
        "analysis": None,
        "answer": None,
        "metadata": {}
    })
    
    return {
        "answer": result["answer"],
        "metadata": result["metadata"],
        "analysis": result.get("analysis"),
        "query_type": result["intent"].query_type if result.get("intent") else "general"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
