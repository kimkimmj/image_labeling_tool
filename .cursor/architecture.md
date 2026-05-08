# 아키텍처 개요

## 백엔드
FastAPI (모듈형 구조)
- api/
- services/
- repositories/

## 워커
Celery 워커
- 업로드 처리
- ffmpeg 추출
- YOLO 추론
- 내보내기 생성

## DB
PostgreSQL
- 관계형 코어
- 데이터셋 버전 참조 모델

## 스토리지
MinIO
- 원본 업로드
- 이미지
- 내보내기 산출물

## 큐
Redis
- 작업 큐 시스템
