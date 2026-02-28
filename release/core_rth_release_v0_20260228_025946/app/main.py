from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import mimetypes
import asyncio
import logging
import time
from pathlib import Path

from app.core.config import settings
from app.api.api_v1.api import api_router

from app.core.rth_chronicle import get_chronicle
from app.core.rth_cortex import get_cortex
from app.core.rth_praxis import get_praxis
from app.core.rth_feedbackloop import get_feedbackloop
from app.core.event_bus import initialize_event_bus

logger = logging.getLogger(__name__)
APP_STARTED_AT = time.time()
APP_READY = False

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

UI_HTML = Path(__file__).resolve().parent / "ui_control_plane.html"
UI_JS = Path(__file__).resolve().parent / "ui_control_plane.js"
UI_CSS = Path(__file__).resolve().parent / "ui_control_plane.css"
UI_ASSETS_DIR = Path(__file__).resolve().parent / "ui_assets"


def _safe_ui_asset_path(asset_name: str) -> Path:
    if not UI_ASSETS_DIR.exists():
        raise HTTPException(status_code=404, detail="UI assets not installed")
    resolved_base = UI_ASSETS_DIR.resolve()
    p = (resolved_base / asset_name).resolve()
    try:
        p.relative_to(resolved_base)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid asset path")
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")
    return p


async def _feedback_cycle():
    feedback = get_feedbackloop()
    while True:
        try:
            await feedback.analyze_feedback()
        except Exception as e:
            logger.error(f"FeedbackLoop cycle error: {e}")
        await asyncio.sleep(settings.FEEDBACK_ANALYSIS_INTERVAL_SECONDS)


@app.on_event("startup")
async def startup_rth_synapse():
    global APP_READY
    await initialize_event_bus()

    # Register core subscribers before sensors start publishing events.
    cortex = get_cortex()
    _ = get_praxis()

    chronicle = get_chronicle()
    asyncio.create_task(chronicle.start_continuous_monitoring())

    asyncio.create_task(cortex.start_continuous_analysis())
    asyncio.create_task(_feedback_cycle())

    APP_READY = True
    print("[RTH Synapse] Core modules started")


@app.get("/")
async def root():
    return {"message": "Welcome to RTH Cortex API", "version": "1.0.0", "ui": "/ui/" if UI_HTML.exists() else None}


@app.get("/ui")
@app.get("/ui/")
async def ui_index():
    if not UI_HTML.exists():
        return JSONResponse(status_code=404, content={"status": "missing", "detail": "UI not installed"})
    return FileResponse(str(UI_HTML), media_type="text/html; charset=utf-8")


@app.get("/ui/app.js")
async def ui_js():
    if not UI_JS.exists():
        return JSONResponse(status_code=404, content={"status": "missing", "detail": "UI JS not installed"})
    return FileResponse(str(UI_JS), media_type="application/javascript; charset=utf-8")


@app.get("/ui/styles.css")
async def ui_css():
    if not UI_CSS.exists():
        return JSONResponse(status_code=404, content={"status": "missing", "detail": "UI CSS not installed"})
    return FileResponse(str(UI_CSS), media_type="text/css; charset=utf-8")


@app.get("/ui/assets/{asset_name:path}")
async def ui_asset(asset_name: str):
    p = _safe_ui_asset_path(asset_name)
    media_type, _ = mimetypes.guess_type(str(p))
    return FileResponse(str(p), media_type=media_type or "application/octet-stream")


@app.get("/favicon.ico")
async def favicon():
    p = _safe_ui_asset_path("favicon.ico")
    return FileResponse(str(p), media_type="image/x-icon")


@app.get("/site.webmanifest")
async def site_webmanifest():
    p = _safe_ui_asset_path("site.webmanifest")
    return FileResponse(str(p), media_type="application/manifest+json; charset=utf-8")


@app.get("/health/live")
async def health_live():
    return {
        "status": "alive",
        "uptime_s": round(time.time() - APP_STARTED_AT, 3),
    }


@app.get("/health/ready")
async def health_ready():
    if not APP_READY:
        return JSONResponse(
            status_code=503,
            content={"status": "starting", "ready": False},
        )
    return {
        "status": "ready",
        "ready": True,
        "uptime_s": round(time.time() - APP_STARTED_AT, 3),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
