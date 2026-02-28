from fastapi import APIRouter
from app.api.api_v1.endpoints import rth_synapse, rth_metamorph, jarvis, models, plugins, secrets

api_router = APIRouter()

api_router.include_router(
    rth_synapse.router,
    prefix="/synapse",
    tags=["RTH Synapse - Governance"]
)
api_router.include_router(
    rth_metamorph.router,
    prefix="/rth-metamorph",
    tags=["RTH Metamorph - Custode"]
)

@api_router.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "version": "0.1.0",
        "service": "RTH Core"
    }

api_router.include_router(jarvis.router, tags=["Jarvis"])
api_router.include_router(models.router, prefix="/models", tags=["Models"])
api_router.include_router(plugins.router, prefix="/plugins", tags=["Plugins"])
api_router.include_router(secrets.router, prefix="/secrets", tags=["Secrets"])
