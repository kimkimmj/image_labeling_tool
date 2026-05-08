You are building a production-grade AI image/video labeling SaaS system.

Follow strictly:
- Backend: FastAPI (Python)
- DB: PostgreSQL
- Async jobs: Celery + Redis
- Storage: MinIO
- Architecture: service / repository separation
- No business logic in controller
- Use SQLAlchemy ORM
- Use Pydantic schemas

Business rules:
- Dataset version is reference-based (no data duplication)
- Approved annotations are immutable
- 1 image = 1 annotator
- YOLO class index (export_index) must never change or be reused