from fastapi import APIRouter

from app.domains.oAuth.router.router import router as oauth_router

api_router = APIRouter()
api_router.include_router(oauth_router)
