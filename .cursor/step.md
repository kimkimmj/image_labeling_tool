## Plan 저장 경로 (나중에 다시 보기)

- 디렉터리: **`.cursor/plans/`** (작업디렉토리에서의 경로임 커밋해 두면 단계별 플랜 이력으로 유지)
- 파일명 예시:
  - Cursor가 만든 플랜을 파일로 내보낼 때: **`step-01-auth-project.plan`** 처럼 번호·요약을 접두어로 붙인다.
  - 마크다운으로 정리할 때: **`step-01-auth-project.plan.md`**
- 한 STEP을 시작하기 전·직후에 저장해 두면 `step.md` 의 STEP 목록과 1:1로 대응하기 쉽다.
- 플랜 작성·실행 중 Cursor가 한 **추가 질문·심문**은 **`docs/questions/`** 에 플랜과 **동일한 파일명**의 `.md` 로 정리한다. 자세한 규칙은 **`.cursor/rules/plan-storage.md`** 를 따른다.

---

STEP 1 — AUTH + PROJECT 생성
🔥 Cursor 프롬프트
Create authentication and project base system.

Requirements:

1. Create users table
- id, email, password_hash, created_at

2. Implement JWT authentication
- login
- register
- get current user

3. Create projects system
- project has: id, name, created_by

4. Create project_users table
- user_id, project_id, role (owner / annotator / reviewer)

5. API endpoints:
- POST /auth/register
- POST /auth/login
- GET /me
- POST /projects
- GET /projects

Rules:
- Only authenticated users can access projects
- Project list must return only user-related projects
- Owner is creator of project

Return:
- FastAPI code
- SQLAlchemy models
- service + repository structure


2️⃣ STEP 2 — PROJECT ROLE & MEMBER SYSTEM
Extend project system with role management.

Requirements:

1. project_users role system:
- owner
- annotator
- reviewer

2. API:
- invite user to project
- change role
- remove user

3. Business rule:
- Only owner can manage members

4. Ensure project isolation:
- user can only access assigned projects

Return full implementation.
3️⃣ STEP 3 — CLASS SYSTEM (YOLO mapping)
Implement project class system for YOLO labeling.

Requirements:

1. model_classes table
- from uploaded YOLO model (class_index, name)

2. project_classes table
- mapped from model_classes
- export_index must be assigned and NEVER changed

3. Features:
- owner can add class
- owner can rename class
- soft delete class (is_active=false)

4. API:
- POST /projects/{id}/classes
- PATCH /classes/{id}
- DELETE /classes/{id}

Rule:
- export_index must remain stable forever

Return full backend implementation.
4️⃣ STEP 4 — UPLOAD SYSTEM (IMAGE + VIDEO)
Build upload pipeline system.

Requirements:

1. upload_jobs table
- status: pending / processing / completed / failed
- options: json (resize, fps, auto_label_model_id)

2. Support:
- image zip upload
- video upload (mp4)

3. Processing:
- zip → images table
- video → ffmpeg → source_videos + images

4. API:
- POST /upload
- GET /upload_jobs/{id}

5. Must use Celery worker for processing

Return:
- FastAPI + Celery worker implementation
5️⃣ STEP 5 — AUTO LABELING (YOLO)
Implement YOLO auto labeling system.

Requirements:

1. On upload completion:
- run YOLO inference

2. Generate annotations:
- bbox (x, y, width, height)
- class mapping using project_classes

3. annotation source:
- auto or manual

4. Rules:
- auto labeling runs only once at upload time
- cannot be re-run after completion

Return:
- inference worker code
- annotation creation logic
6️⃣ STEP 6 — IMAGE ASSIGNMENT SYSTEM
Implement annotation assignment system.

Requirements:

1. image_assignments table
- image_id
- assigned_to
- status

2. Rules:
- 1 image = 1 annotator only

3. API:
- bulk assign images to annotator
- get assigned tasks
- update status

4. Status flow:
- assigned → in_progress → submitted

Return full backend implementation.
7️⃣ STEP 7 — ANNOTATION SYSTEM
Implement annotation CRUD system.

Requirements:

1. annotations table:
- bbox (x,y,width,height)
- class_id
- image_id
- assignment_id

2. Features:
- create bbox
- update bbox
- delete bbox
- change class

3. Rules:
- only assigned annotator can modify
- only project_classes allowed

Return backend API only.
8️⃣ STEP 8 — REVIEW SYSTEM
Implement reviewer workflow system.

Requirements:

1. Status flow:
- submitted → approved
- submitted → reverted

2. Reviewer features:
- view submitted tasks
- approve annotation
- reject and send back to annotator

3. Rules:
- reviewer can modify annotations before approval
- approved state is immutable

Return full API + service logic.
9️⃣ STEP 9 — DATASET VERSION (FREEZE SYSTEM)
Implement dataset version system.

Requirements:

1. dataset_versions table
2. dataset_items table (reference only)

3. Logic:
- only approved assignments included
- NO data duplication

4. API:
- create dataset version
- list dataset versions

Rule:
- dataset version is snapshot reference only

Return full implementation.
🔟 STEP 10 — DATASET SPLIT
Implement dataset splitting system.

Requirements:

1. dataset_splits table
2. split_items table

3. Features:
- train/val/test ratio input
- deterministic split (random_seed)

4. Rule:
- reference-based only (no duplication)

Return backend logic.
1️⃣1️⃣ STEP 11 — EXPORT SYSTEM (YOLO ZIP)
Implement dataset export system.

Requirements:

1. export_jobs table

2. Flow:
- dataset_version + split 선택
- async export job 실행

3. Output:
- YOLO format:
  /images/train
  /labels/train
  data.yaml

4. Must use:
- project_classes.export_index

5. Storage:
- MinIO upload

Return:
- Celery export worker
- zip generator
1️⃣2️⃣ STEP 12 — QUEUE SYSTEM
Implement unified queue system.

Requirements:

1. Redis + Celery
2. Jobs:
- upload
- ffmpeg
- auto labeling
- export

3. Must include:
- retry mechanism
- status tracking

Return worker architecture only.
🚀 최종 사용 방식

Cursor에서 이렇게 쓴다:

[STEP 4 프롬프트 붙여넣기]
→ 코드 생성
→ 검증
→ 다음 STEP
🔥 핵심 전략
1. 절대 한 번에 다 만들지 않는다
2. STEP 단위로만 진행
3. DB → API → Worker → UI 순서 유지
💡 한 줄 결론
이 프로젝트는 “코드 작성”이 아니라
“워크플로우 시스템을 단계적으로 조립”하는 작업이다