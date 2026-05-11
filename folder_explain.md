# image_labeling_tool 폴더 구조

이 문서는 `backend`와 `frontend` 디렉터리 구조와 각 폴더에 있는 코드의 성격을 요약한다.

## Backend (`backend/`)

Python **FastAPI** 기반 API 서버. 도메인별로 라우터·서비스·리포지토리·스키마가 나뉘고, SQLAlchemy 모델·DB·마이그레이션·백그라운드 작업이 함께 있다.

| 경로 | 역할 |
|------|------|
| `app/main.py` | 앱 진입점, 미들웨어/CORS 등 애플리케이션 부트스트랩 |
| `app/router.py` | 하위 도메인 라우터를 묶는 최상위 `api_router` |
| `app/core/` | `config.py`(설정), `storage.py`(파일/S3 등 저장), `session_store.py`, `yolo_parser.py` 등 공통 인프라 |
| `app/db/` | `session.py`, `base.py` — DB 세션·Base 선언 |
| `app/middleware/` | 예: `csrf.py` |
| `app/models/` | SQLAlchemy 엔티티: User, OAuthIdentity, Project, ProjectUser, Invitation, UploadJob, Image, ImageAssignment, Annotation, MlModel, ProjectClass 등; `enums.py`에 역할·업로드·할당 상태 등 Enum |
| `app/domains/` | 비즈니스 영역별 코드 |
| → `oAuth/` | 로그인·세션·PKCE·쿠키·OAuth 리다이렉트, `router/`, `services/`, `repositories/` |
| → `projects/` | 프로젝트·초대·클래스(`class_service`, class repo) — `router.py`, `services/`, `repositories/`, `schemas/` |
| → `uploads/` | 업로드 작업·이미지 메타·스토리지 연동 — `router.py`, `services/upload_service.py`, `repositories/`, `schemas/`, 예외 |
| → `annotations/` | 어노테이션·할당(CVAT 스타일 흐름) — `router.py`, `annotation_service.py`, `annotation_repository.py`, `schemas/dtos.py`, 예외 |
| → `export/` | 내보내기 API — `router.py`, `schemas.py` |
| → `admin/` | 관리자·모델 관리 등 — `router.py`, `admin_model_service.py`, `schemas/`, `deps.py` |
| `app/tasks/` | 비동기 작업: `upload_tasks.py`, `export_tasks.py` |
| `app/worker.py` | 워커 프로세스 진입점 |
| `alembic/` | DB 마이그레이션 스크립트(`versions/*.py`) |
| `tests/` | 단위 테스트 예: `test_upload_tasks.py`, `test_class_service.py` |
| `requirements.txt` | Python 의존성 |

**요약:** REST API, OAuth 세션, 프로젝트/업로드/어노테이션 도메인, ML 모델·클래스 연동, 관리자, 내보내기·백그라운드 작업.

## Frontend (`frontend/`)

**React + TypeScript + Vite** 스타일 SPA. `src` 기준으로 페이지·API·인증·어노테이션 UI가 구분된다.

| 경로 | 역할 |
|------|------|
| `src/main.tsx` | React 루트 마운트 |
| `src/App.tsx`, `App.css` | 라우팅(`react-router-dom`), `ProtectedRoute`, 로그인 후 `return_to` 리다이렉트 등 앱 셸 |
| `src/index.css` | 전역 스타일 |
| `src/pages/` | 화면: `HomePage`, `LoginPage`, `JoinPage`, `ProjectsPage`, `ProjectDetailPage`, `UploadDetailPage`, `AnnotationPage`, `AdminPage` |
| `src/api/` | 백엔드 호출: `client.ts`, `auth.ts`, `projects.ts`, `uploads.ts`, `admin.ts` |
| `src/auth/AuthContext.tsx` | 로그인 상태·세션 컨텍스트 |
| `src/types/` | `api.ts`, `projects.ts`, `uploads.ts` 등 타입 정의 |
| `src/components/annotation/` | 라벨링 UI: `AnnotationCanvas.tsx`, `AnnotationToolbar`, `ClassSidebar`, `ImageListPanel`, `useAnnotationState`, `coordUtils` |

**요약:** 로그인/회원, 프로젝트, 업로드 상세, 어노테이션 캔버스, 관리자 페이지가 한 React 앱에 있으며 `src/api`가 FastAPI 백엔드와 통신한다.

## Backend와 Frontend의 관계

- **Backend:** 데이터·권한·파일 저장·비동기 작업을 담당하는 API.
- **Frontend:** 브라우저 UI와 `src/api/*` HTTP 호출로 위 API를 사용.

`node_modules`, `.venv`는 의존성 설치 결과물이며 애플리케이션 소스와는 별도로 관리한다.
