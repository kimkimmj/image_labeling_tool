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

## 9) 프로덕션 스택 (단일 호스트, 선택)

한 PC에서 API·Celery·프론트·인프라를 모두 띄울 때는 프로젝트 루트의 `docker-compose.prod.yml`을 사용한다.

1. `cp .env.compose.sample .env` 후 DB/MinIO 비밀번호 등 수정  
2. `cp backend/.env.example backend/.env` 후 `CORS_ORIGINS`, OAuth, `PUBLIC_APP_URL`을 **실제 접속 URL**(예: `http://172.16.100.57:8080`)로 맞춘다. (`backend/.env.example` 하단 주석 참고)  
3. `docker compose -f docker-compose.prod.yml up -d --build`  
4. 브라우저: `http://<호스트>:8080` — nginx가 UI를 서빙하고 `/api`는 FastAPI로 프록시한다.

`minio-init` 완료 후에만 API가 기동한다(Docker Compose `service_completed_successfully`).