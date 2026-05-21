# Backend API + Celery worker base image (docker-compose.prod.yml)
FROM python:3.12-slim-bookworm

WORKDIR /app/backend

# curl: healthcheck — ffmpeg/libgl: upload/ffmpeg, ultralytics/OpenCV 경로
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini alembic.ini
COPY alembic/ alembic/
COPY app/ app/

ENV PYTHONPATH=/app/backend
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
