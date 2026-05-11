"""로그인 사용자용 ML 모델 업로드·목록."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.storage import StorageClient, get_storage_client
from app.core.yolo_parser import InvalidYoloModelError
from app.db.session import get_db
from app.domains.ml_models.schemas.dtos import MlModelRecordResponse
from app.domains.ml_models.services.ml_model_upload_service import MlModelUploadService
from app.domains.oAuth.deps import get_current_user
from app.models import User

router = APIRouter(prefix="/ml-models", tags=["ml-models"])


def get_ml_model_upload_service(
    db: Session = Depends(get_db),
    storage: StorageClient = Depends(get_storage_client),
) -> MlModelUploadService:
    return MlModelUploadService(db, storage)


@router.post("", response_model=MlModelRecordResponse, status_code=status.HTTP_201_CREATED)
def upload_my_model(
    model_file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    svc: MlModelUploadService = Depends(get_ml_model_upload_service),
) -> MlModelRecordResponse:
    file_bytes = model_file.file.read()
    filename = model_file.filename or "model.pt"
    model_name = filename.rsplit(".", 1)[0] or filename
    try:
        result = svc.upload_model(
            owner_user_id=user.id,
            filename=filename,
            file_bytes=file_bytes,
            model_name=model_name,
        )
    except InvalidYoloModelError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return MlModelRecordResponse(
        id=result.id,
        name=result.name,
        version=result.version,
        framework=result.framework,
        file_path=result.file_path,
        created_at=result.created_at,
    )


@router.get("", response_model=list[MlModelRecordResponse])
def list_my_models(
    user: User = Depends(get_current_user),
    svc: MlModelUploadService = Depends(get_ml_model_upload_service),
) -> list[MlModelRecordResponse]:
    rows = svc.list_my_models(owner_user_id=user.id)
    return [
        MlModelRecordResponse(
            id=r.id,
            name=r.name,
            version=r.version,
            framework=r.framework,
            file_path=r.file_path,
            created_at=r.created_at,
        )
        for r in rows
    ]
