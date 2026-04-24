from fastapi import APIRouter

from api.routes.videos import router as videos_router
from api.routes.materials import router as materials_router
from api.routes.generated import router as generated_router

api_router = APIRouter(prefix="/api")
api_router.include_router(videos_router)
api_router.include_router(materials_router)
api_router.include_router(generated_router)
