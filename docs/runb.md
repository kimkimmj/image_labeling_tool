# 로컬 개발 실행 절차 (백엔드/프론트 로컬 + 인프라 Docker)

## 1) 인프라 컨테이너 실행

프로젝트 루트에서 아래를 실행:

```bash
docker compose -f docker-compose.dev.yml up -d
```

실행 대상:
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
- MinIO API: `localhost:9000`
- MinIO Console: `localhost:9001`

## 2) 백엔드 환경변수 준비

루트의 `.env.backend.example`를 백엔드 실행 위치의 `.env`로 복사해 사용:

```bash
cp .env.backend.example .env
```

필요 시 최소 항목 수정:
- `DATABASE_URL`
- `CELERY_BROKER_URL`
- `MINIO_*`

## 3) DB 마이그레이션 적용

백엔드 프로젝트 경로에서 마이그레이션 실행(도구에 맞게 택1):

```bash
# alembic 예시
alembic upgrade head
```

## 4) 백엔드 로컬 실행

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## 5) Celery 워커 로컬 실행

```bash
celery -A app.worker.celery_app worker -l info
```

무거운 작업(업로드 처리, 추론, export)은 반드시 워커에서 처리한다.

## 6) 프론트엔드 로컬 실행

프론트엔드 프로젝트 경로에서:

```bash
npm install
npm run dev
```

## 7) MinIO 확인

- Console 접속: `http://localhost:9001`
- 계정: `minio` / `minio123`
- 기본 버킷: `ilt-media` (`minio-init` 컨테이너가 자동 생성)

## 8) 종료/초기화

종료:

```bash
docker compose -f docker-compose.dev.yml down
```

볼륨까지 삭제(주의):

```bash
docker compose -f docker-compose.dev.yml down -v
```