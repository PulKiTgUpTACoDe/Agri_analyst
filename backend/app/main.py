"""FastAPI application – Agri Analyst API."""
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.core.api_client import get_client
from app.core.open_meteo import get_meteo_client
from app.core.cache import get_cache
from app.core.data_sources import get_registry
from app.graph.workflow import get_workflow

logger = logging.getLogger("agri.main")


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)
    logger.info("Starting Agri Analyst API v2.0")

    # Pre-initialize
    get_workflow()
    get_cache()
    get_registry()
    logger.info("Workflow, cache, and registry initialized")
    yield

    # Shutdown
    logger.info("Shutting down...")
    client = get_client()
    meteo = get_meteo_client()
    await client.close()
    await meteo.close()
    logger.info("All connections closed")


# ── App setup ─────────────────────────────────────────────────────────────────

settings = get_settings()
app = FastAPI(title="Agri Analyst API", version="2.0.0", lifespan=lifespan)

# CORS
cors_origins_raw = getattr(settings, "CORS_ORIGINS", "")
cors_origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()] if cors_origins_raw else []
for origin in ["https://agri-analyst.netlify.app", "https://agri-analyst-zc9g.vercel.app",
                "http://localhost:5173", "http://localhost:3000", "http://localhost:8000",
                "http://127.0.0.1:5173", "http://127.0.0.1:3000", "http://127.0.0.1:8000"]:
    if origin not in cors_origins:
        cors_origins.append(origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Middleware ─────────────────────────────────────────────────────────────────

@app.middleware("http")
async def request_middleware(request: Request, call_next):
    """Add request ID, timing, and error handling."""
    request_id = str(uuid.uuid4())[:8]
    start = time.monotonic()

    try:
        response = await call_next(request)
        elapsed = (time.monotonic() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{elapsed:.0f}ms"
        logger.info("%s %s -> %d (%.0fms) [%s]",
                     request.method, request.url.path, response.status_code, elapsed, request_id)
        return response
    except Exception as exc:
        elapsed = (time.monotonic() - start) * 1000
        logger.error("Unhandled error [%s]: %s", request_id, exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "request_id": request_id},
            headers={"X-Request-ID": request_id, "X-Response-Time": f"{elapsed:.0f}ms"},
        )


# ── Endpoints ─────────────────────────────────────────────────────────────────

class AskRequest(BaseModel):
    question: str


@app.post("/ask")
async def ask(req: AskRequest):
    """Process agricultural query using AI workflow."""
    result = await get_workflow().ainvoke({
        "question": req.question,
        "intent": None,
        "sources_selected": [],
        "raw_data": {},
        "data_quality": {},
        "analysis": None,
        "answer": None,
        "metadata": {},
        "errors": [],
        "timing": {},
    })

    # Build citations from registry
    registry = get_registry()
    source_map = registry.get_source_map()
    sources = result["metadata"].get("sources", [])
    raw_data = result.get("raw_data", {})

    citations = []
    for source_id in sources:
        if source_id in source_map:
            record_count = len(raw_data.get(source_id, []))
            info = source_map[source_id]
            citations.append({
                "id": source_id,
                "name": info["name"],
                "icon": info["icon"],
                "records": record_count,
                "description": info["description"],
            })

    response = {
        "answer": result.get("answer", "No answer generated"),
        "usedEndpoints": sources,
        "citations": citations,
        "timing": result.get("timing", {}),
        "data_freshness": result["metadata"].get("fetch_date"),
    }

    analysis = result.get("analysis", {})
    if analysis and (analysis.get("insights") or analysis.get("structured_data")):
        response["query_type"] = analysis.get("query_type", "general")
        response["analysis"] = analysis
        response["total_records"] = result["metadata"].get("records_fetched", 0)

    # Include weather location if used
    weather_loc = result["metadata"].get("weather_location")
    if weather_loc:
        response["weather_location"] = weather_loc

    return response


@app.get("/health")
async def health():
    """Health check with system status."""
    cache = get_cache()
    registry = get_registry()
    return {
        "status": "ok",
        "version": "2.0.0",
        "cache": cache.stats.to_dict(),
        "data_sources": len(registry.list_all()),
    }


@app.get("/api/v1/sources")
async def list_sources():
    """List all available data sources."""
    registry = get_registry()
    sources = []
    for ds in registry.list_all():
        sources.append({
            "id": ds.id,
            "name": ds.name,
            "icon": ds.icon,
            "source_type": ds.source_type,
            "description": ds.description,
            "update_frequency": ds.update_frequency,
            "available_filters": ds.available_filters,
        })
    return {"sources": sources, "total": len(sources)}


@app.post("/api/v1/cache/invalidate")
async def invalidate_cache(category: str = None):
    """Invalidate cache entries."""
    cache = get_cache()
    count = cache.invalidate(category)
    return {"invalidated": count, "category": category or "all"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app)
