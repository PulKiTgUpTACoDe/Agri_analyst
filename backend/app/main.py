import logging, time, uuid
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)
    logger.info("Starting Agri Analyst API v2.0")
    get_workflow(); get_cache(); get_registry()
    yield
    await get_client().close()
    await get_meteo_client().close()

settings = get_settings()
app = FastAPI(title="Agri Analyst API", version="2.0.0", lifespan=lifespan)

origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()] if settings.CORS_ORIGINS else []
origins.extend(["http://localhost:5173", "http://localhost:3000", "http://localhost:8000",
                 "http://127.0.0.1:5173", "http://127.0.0.1:3000", "http://127.0.0.1:8000"])
app.add_middleware(CORSMiddleware, allow_origins=list(set(origins)), allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    rid = str(uuid.uuid4())[:8]
    t = time.monotonic()
    try:
        resp = await call_next(request)
        ms = (time.monotonic() - t) * 1000
        resp.headers["X-Request-ID"] = rid
        resp.headers["X-Response-Time"] = f"{ms:.0f}ms"
        return resp
    except Exception as e:
        logger.error("[%s] %s", rid, e, exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Internal server error", "request_id": rid})

class AskRequest(BaseModel):
    question: str

@app.post("/ask")
async def ask(req: AskRequest):
    result = await get_workflow().ainvoke({
        "question": req.question, "intent": None, "sources_selected": [], "raw_data": {},
        "data_quality": {}, "analysis": None, "answer": None, "metadata": {}, "errors": [], "timing": {},
    })
    reg = get_registry()
    src_map = reg.get_source_map()
    sources = result["metadata"].get("sources", [])
    raw = result.get("raw_data", {})
    citations = [{"id": s, **src_map[s], "records": len(raw.get(s, []))} for s in sources if s in src_map]

    resp = {"answer": result.get("answer", ""), "usedEndpoints": sources, "citations": citations,
            "timing": result.get("timing", {}), "data_freshness": result["metadata"].get("fetch_date")}
    analysis = result.get("analysis", {})
    if analysis and (analysis.get("insights") or analysis.get("structured_data")):
        resp["query_type"] = analysis.get("query_type", "general")
        resp["analysis"] = analysis
        resp["total_records"] = result["metadata"].get("records_fetched", 0)
    wl = result["metadata"].get("weather_location")
    if wl: resp["weather_location"] = wl
    return resp

@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0", "cache": get_cache().stats.to_dict(),
            "data_sources": len(get_registry().list_all())}

@app.get("/api/v1/sources")
async def list_sources():
    src = [{"id": d.id, "name": d.name, "icon": d.icon, "source_type": d.source_type,
            "description": d.description, "update_frequency": d.update_frequency,
            "available_filters": d.available_filters} for d in get_registry().list_all()]
    return {"sources": src, "total": len(src)}

@app.post("/api/v1/cache/invalidate")
async def invalidate_cache(category: str = None):
    return {"invalidated": get_cache().invalidate(category), "category": category or "all"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app)
