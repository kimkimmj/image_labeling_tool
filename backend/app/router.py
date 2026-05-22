from fastapi import APIRouter

from app.domains.annotations.router import assignments_router, images_anno_router, upload_jobs_anno_router
from app.domains.ml_models.router import router as ml_models_router
from app.domains.dataset_splits.router import router as dataset_splits_router
from app.domains.dataset_versions.router import router as dataset_versions_router
from app.domains.export.router import export_router
from app.domains.oAuth.router.router import router as oauth_router
from app.domains.projects.router import classes_router, invitations_router, router as projects_router
from app.domains.uploads.router import images_router, project_uploads_router, upload_jobs_router

api_router = APIRouter()
api_router.include_router(oauth_router)
api_router.include_router(ml_models_router)
api_router.include_router(projects_router)
api_router.include_router(invitations_router)
api_router.include_router(classes_router)
api_router.include_router(project_uploads_router)
api_router.include_router(upload_jobs_router)
api_router.include_router(images_router)
# annotation write & assignment routes (CVAT-inspired)
api_router.include_router(images_anno_router)
api_router.include_router(assignments_router)
api_router.include_router(upload_jobs_anno_router)
api_router.include_router(dataset_versions_router)
api_router.include_router(dataset_splits_router)
api_router.include_router(export_router)
