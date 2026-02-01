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

# CORS Configuration
from app.core.config import get_settings

settings = get_settings()

# Parse CORS origins from environment variable
cors_origins_raw = getattr(settings, "CORS_ORIGINS", "")
if cors_origins_raw:
    cors_origins = [origin.strip() for origin in cors_origins_raw.split(",") if origin.strip()]
else:
    # Default to production frontend if not specified
    cors_origins = ["https://agri-analyst.netlify.app"]

# Add localhost for development if DEBUG is True
if getattr(settings, "DEBUG", False):
    cors_origins.extend(["http://localhost:5173", "http://localhost:3000", "http://localhost:8000"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str

@app.post("/ask")
async def ask(req: AskRequest):
    """Process agricultural query using ai workflow."""
    result = await get_workflow().ainvoke({
        "question": req.question,
        "intent": None,
        "raw_data": {},
        "analysis": None,
        "answer": None,
        "metadata": {},
        "context_docs": []  # Initialize for vector store results
    })
    
    # Build citations with friendly names
    sources = result["metadata"].get("sources", [])
    raw_data = result.get("raw_data", {})
    
    citations = []
    source_map = {
        "daily_prices": {"name": "Daily Market Prices", "icon": "💰"},
        "variety_prices": {"name": "Variety-wise Prices", "icon": "🏷️"},
        "crop_production": {"name": "Crop Production Statistics", "icon": "🌾"},
        "temperature_series": {"name": "Temperature Data", "icon": "🌡️"},
        "rainfall_subdivisions": {"name": "Rainfall Data", "icon": "🌧️"}
    }
    
    for source in sources:
        if source in source_map:
            record_count = len(raw_data.get(source, []))
            citations.append({
                "id": source,
                "name": source_map[source]["name"],
                "icon": source_map[source]["icon"],
                "records": record_count
            })
    
    response = {
        "answer": result.get("answer", "No answer generated"),
        "context": None,
        "usedEndpoints": sources,
        "usedParams": None,
        "citations": citations
    }
    
    analysis = result.get("analysis", {})
    if analysis and (analysis.get('insights') or analysis.get('structured_data')):
        response["query_type"] = analysis.get('query_type', 'general')
        response["analysis"] = analysis
        response["total_records"] = result["metadata"].get("records_fetched", 0)
    
    return response


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app)
