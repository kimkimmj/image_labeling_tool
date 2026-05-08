# Backend (FastAPI)

## Quick Start

1. Install dependencies
   - Preferred: create a virtualenv and install `requirements.txt`
2. Copy env file
   - `cp .env.example .env`
3. Run server
   - `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`

STEP 1 API 예시: 세션 쿠키가 있으면 `GET /api/me`, 프로젝트는 `GET|POST /api/projects`. OAuth는 `GET /api/auth/oauth/{google|naver|kakao}/login` 으로 시작한다.
