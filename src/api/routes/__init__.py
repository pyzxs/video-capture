from fastapi import APIRouter

from src.api.routes.videos import router as videos_router
from src.api.routes.materials import router as materials_router
from src.api.routes.generated import router as generated_router
from src.api.routes.agents import router as agents_router
from src.api.routes.folders import router as folders_router
from src.api.routes.settings import router as settings_router
from src.api.routes.notes import router as notes_router
from src.api.routes.profile import router as profile_router
from src.api.routes.editor import router as editor_router
from src.api.routes.export import router as export_router
from src.api.routes.resources import router as resources_router

api_router = APIRouter(prefix="/api")
api_router.include_router(resources_router)
api_router.include_router(videos_router)
api_router.include_router(materials_router)
api_router.include_router(generated_router)
api_router.include_router(folders_router)
api_router.include_router(settings_router)
api_router.include_router(agents_router)
api_router.include_router(notes_router)
api_router.include_router(profile_router)
api_router.include_router(editor_router)
api_router.include_router(export_router)
