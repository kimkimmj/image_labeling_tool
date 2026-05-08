# 로컬 개발 요구사항 (Hybrid Runtime)

백엔드/프론트엔드는 로컬에서 실행하고, 인프라(PostgreSQL/Redis/MinIO)는 Docker 컨테이너로 실행한다.

## 필수 설치

- Docker Engine + Docker Compose v2
- Python 3.11+
- Node.js 20+ / npm 10+

## 인프라 포트

- PostgreSQL: `5432`
- Redis: `6379`
- MinIO API: `9000`
- MinIO Console: `9001`
- Backend (로컬): `8000`
- Frontend (로컬): `3000` (프레임워크 기본값 사용)

## 인프라 서비스

- PostgreSQL 16
- Redis 7
- MinIO latest (S3 호환 오브젝트 스토리지)

## 환경 변수 기준

백엔드에서 아래 변수들을 사용한다.

- DB: `DATABASE_URL` 또는 `DB_*`
- Redis/Celery: `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`
- MinIO: `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`, `MINIO_SECURE`

샘플 값은 루트의 `.env.backend.example`을 사용한다.