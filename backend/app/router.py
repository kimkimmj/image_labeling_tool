from fastapi import APIRouter

from app.domains.oAuth.router.router import router as oauth_router
from app.domains.projects.router import invitations_router, router as projects_router

api_router = APIRouter()
api_router.include_router(oauth_router)
api_router.include_router(projects_router)
api_router.include_router(invitations_router)
