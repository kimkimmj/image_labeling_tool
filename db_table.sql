-- =========================================================
-- ENUMS
-- =========================================================

CREATE TYPE project_role AS ENUM (
  'owner',
  'reviewer',
  'annotator'
);

CREATE TYPE project_invitation_role AS ENUM (
  'annotator',
  'reviewer'
);

CREATE TYPE invitation_status AS ENUM (
  'pending',
  'accepted',
  'expired',
  'cancelled'
);

CREATE TYPE upload_type AS ENUM (
  'image_zip',
  'video'
);

CREATE TYPE upload_status AS ENUM (
  'pending',
  'processing',
  'completed',
  'failed'
);

CREATE TYPE assignment_status AS ENUM (
  'assigned',
  'in_progress',
  'submitted',
  'review_assigned',
  'approved',
  'reverted',
  'rejected'
);

CREATE TYPE annotation_source AS ENUM (
  'auto',
  'manual'
);

CREATE TYPE export_status AS ENUM (
  'pending',
  'processing',
  'completed',
  'failed'
);

CREATE TYPE oauth_provider AS ENUM (
  'google',
  'naver',
  'kakao'
);

-- =========================================================
-- USERS
-- =========================================================

CREATE TABLE users (
  id BIGSERIAL PRIMARY KEY,

  email TEXT NOT NULL UNIQUE,

  password_hash TEXT,

  is_admin BOOLEAN NOT NULL DEFAULT FALSE,

  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE oauth_identities (
  id BIGSERIAL PRIMARY KEY,

  user_id BIGINT NOT NULL REFERENCES users(id),

  provider oauth_provider NOT NULL,

  provider_subject TEXT NOT NULL,

  created_at TIMESTAMP NOT NULL DEFAULT NOW(),

  CONSTRAINT uq_oauth_provider_subject
    UNIQUE(provider, provider_subject)
);

CREATE INDEX idx_oauth_identities_user_id
ON oauth_identities(user_id);

CREATE TABLE ml_models (
  id BIGSERIAL PRIMARY KEY,

  owner_id BIGINT NOT NULL REFERENCES users(id),

  name TEXT NOT NULL,

  version TEXT,

  framework TEXT NOT NULL,

  file_path TEXT NOT NULL,

  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE model_classes (
  id BIGSERIAL PRIMARY KEY,

  model_id BIGINT NOT NULL REFERENCES ml_models(id) ON DELETE CASCADE,

  class_index INT NOT NULL,

  name TEXT NOT NULL,

  created_at TIMESTAMP NOT NULL DEFAULT NOW(),

  CONSTRAINT uq_model_class_index
    UNIQUE(model_id, class_index)
);

-- =========================================================
-- PROJECTS
-- =========================================================

CREATE TABLE projects (
  id BIGSERIAL PRIMARY KEY,

  name TEXT NOT NULL,

  description TEXT,

  created_by BIGINT NOT NULL REFERENCES users(id),

  selected_model_id BIGINT REFERENCES ml_models(id),

  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE project_users (
  id BIGSERIAL PRIMARY KEY,

  project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

  user_id BIGINT NOT NULL REFERENCES users(id),

  role project_role NOT NULL,

  invited_by BIGINT NOT NULL REFERENCES users(id),

  created_at TIMESTAMP NOT NULL DEFAULT NOW(),

  CONSTRAINT uq_project_user
    UNIQUE(project_id, user_id)
);

CREATE TABLE project_invitations (
  id BIGSERIAL PRIMARY KEY,

  project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

  role project_invitation_role NOT NULL,

  token_hash TEXT NOT NULL,

  status invitation_status NOT NULL,

  invited_by BIGINT NOT NULL REFERENCES users(id),

  accepted_by BIGINT REFERENCES users(id) ON DELETE SET NULL,

  accepted_at TIMESTAMP,

  expires_at TIMESTAMP NOT NULL,

  created_at TIMESTAMP NOT NULL DEFAULT NOW(),

  CONSTRAINT uq_project_invitations_token_hash
    UNIQUE(token_hash),

  CONSTRAINT ck_project_invitations_expires_after_created
    CHECK (expires_at > created_at)
);

CREATE INDEX idx_project_invitations_project_status
ON project_invitations(project_id, status);

-- =========================================================
-- PROJECT CLASSES
-- =========================================================

CREATE TABLE project_classes (
  id BIGSERIAL PRIMARY KEY,

  project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

  model_class_id BIGINT REFERENCES model_classes(id) ON DELETE SET NULL,

  export_index INT NOT NULL,

  name TEXT NOT NULL,

  color TEXT,

  is_active BOOLEAN NOT NULL DEFAULT TRUE,

  created_by BIGINT NOT NULL REFERENCES users(id),

  created_at TIMESTAMP NOT NULL DEFAULT NOW(),

  CONSTRAINT uq_project_export_index
    UNIQUE(project_id, export_index),

  CONSTRAINT uq_project_class_name
    UNIQUE(project_id, name)
);

-- =========================================================
-- UPLOAD JOBS
-- =========================================================

CREATE TABLE upload_jobs (
  id BIGSERIAL PRIMARY KEY,

  project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

  uploaded_by BIGINT NOT NULL REFERENCES users(id),

  upload_type upload_type NOT NULL,

  status upload_status NOT NULL,

  original_file_name TEXT NOT NULL,

  original_file_path TEXT NOT NULL,

  options JSONB,

  progress INT,

  processed_count INT,

  total_count INT,

  error_message TEXT,

  created_at TIMESTAMP NOT NULL DEFAULT NOW(),

  completed_at TIMESTAMP
);

-- =========================================================
-- SOURCE VIDEOS
-- =========================================================

CREATE TABLE source_videos (
  id BIGSERIAL PRIMARY KEY,

  project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

  upload_job_id BIGINT NOT NULL REFERENCES upload_jobs(id) ON DELETE CASCADE,

  original_name TEXT NOT NULL,

  file_path TEXT NOT NULL,

  duration_sec FLOAT,

  fps FLOAT,

  width INT,

  height INT,

  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- =========================================================
-- IMAGES
-- =========================================================

CREATE TABLE images (
  id BIGSERIAL PRIMARY KEY,

  project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

  upload_job_id BIGINT NOT NULL REFERENCES upload_jobs(id) ON DELETE CASCADE,

  source_video_id BIGINT REFERENCES source_videos(id),

  file_name TEXT NOT NULL,

  file_path TEXT NOT NULL,

  width INT NOT NULL,

  height INT NOT NULL,

  frame_index INT,

  timestamp_sec FLOAT,

  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- =========================================================
-- IMAGE ASSIGNMENTS
-- =========================================================

CREATE TABLE image_assignments (
  id BIGSERIAL PRIMARY KEY,

  image_id BIGINT NOT NULL REFERENCES images(id) ON DELETE CASCADE,

  assigned_to BIGINT NOT NULL REFERENCES users(id),

  assigned_by BIGINT NOT NULL REFERENCES users(id),

  reviewer_id BIGINT REFERENCES users(id),

  status assignment_status NOT NULL,

  approved_by BIGINT REFERENCES users(id),

  approved_at TIMESTAMP,

  reverted_by BIGINT REFERENCES users(id),

  reverted_at TIMESTAMP,

  revert_reason TEXT,

  submitted_at TIMESTAMP,

  reviewed_at TIMESTAMP,

  created_at TIMESTAMP NOT NULL DEFAULT NOW(),

  CONSTRAINT uq_image_assignment
    UNIQUE(image_id)
);

-- =========================================================
-- ANNOTATIONS
-- =========================================================

CREATE TABLE annotations (
  id BIGSERIAL PRIMARY KEY,

  assignment_id BIGINT NOT NULL REFERENCES image_assignments(id) ON DELETE CASCADE,

  image_id BIGINT NOT NULL REFERENCES images(id) ON DELETE CASCADE,

  class_id BIGINT NOT NULL REFERENCES project_classes(id),

  x FLOAT NOT NULL,

  y FLOAT NOT NULL,

  width FLOAT NOT NULL,

  height FLOAT NOT NULL,

  confidence FLOAT,

  source annotation_source NOT NULL,

  created_by BIGINT NOT NULL REFERENCES users(id),

  updated_by BIGINT REFERENCES users(id),

  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,

  created_at TIMESTAMP NOT NULL DEFAULT NOW(),

  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

  CONSTRAINT chk_bbox_coordinate
    CHECK (
      x >= 0 AND x <= 1
      AND y >= 0 AND y <= 1
      AND width > 0 AND width <= 1
      AND height > 0 AND height <= 1
    )
);

-- =========================================================
-- SUBMISSION COMMENTS
-- =========================================================

CREATE TABLE submission_comments (
  id BIGSERIAL PRIMARY KEY,

  assignment_id BIGINT NOT NULL REFERENCES image_assignments(id) ON DELETE CASCADE,

  reviewer_id BIGINT NOT NULL REFERENCES users(id),

  action TEXT NOT NULL,

  comment TEXT,

  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- =========================================================
-- DATASET VERSIONS
-- =========================================================

CREATE TABLE dataset_versions (
  id BIGSERIAL PRIMARY KEY,

  project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

  name TEXT NOT NULL,

  description TEXT,

  created_by BIGINT NOT NULL REFERENCES users(id),

  created_at TIMESTAMP NOT NULL DEFAULT NOW(),

  CONSTRAINT uq_dataset_version
    UNIQUE(project_id, name)
);

-- =========================================================
-- DATASET ITEMS
-- =========================================================

CREATE TABLE dataset_items (
  id BIGSERIAL PRIMARY KEY,

  dataset_version_id BIGINT NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,

  image_id BIGINT NOT NULL REFERENCES images(id),

  assignment_id BIGINT NOT NULL REFERENCES image_assignments(id),

  created_at TIMESTAMP NOT NULL DEFAULT NOW(),

  CONSTRAINT uq_dataset_item_version_image
    UNIQUE(dataset_version_id, image_id)
);

-- =========================================================
-- DATASET SPLITS
-- =========================================================

CREATE TABLE dataset_splits (
  id BIGSERIAL PRIMARY KEY,

  dataset_version_id BIGINT NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,

  name TEXT NOT NULL,

  train_ratio FLOAT NOT NULL,

  val_ratio FLOAT NOT NULL,

  test_ratio FLOAT NOT NULL,

  random_seed INT NOT NULL DEFAULT 0,

  created_by BIGINT NOT NULL REFERENCES users(id),

  created_at TIMESTAMP NOT NULL DEFAULT NOW(),

  CONSTRAINT chk_split_ratio
    CHECK (
      train_ratio + val_ratio + test_ratio = 100
    )
);

-- =========================================================
-- SPLIT ITEMS
-- =========================================================

CREATE TABLE split_items (
  id BIGSERIAL PRIMARY KEY,

  split_id BIGINT NOT NULL REFERENCES dataset_splits(id) ON DELETE CASCADE,

  dataset_item_id BIGINT NOT NULL REFERENCES dataset_items(id),

  split_type TEXT NOT NULL,

  created_at TIMESTAMP NOT NULL DEFAULT NOW(),

  CONSTRAINT chk_split_type
    CHECK (split_type IN ('train', 'val', 'test')),

  CONSTRAINT uq_split_item_per_dataset_item
    UNIQUE(split_id, dataset_item_id)
);

-- =========================================================
-- EXPORT JOBS
-- =========================================================

CREATE TABLE export_jobs (
  id BIGSERIAL PRIMARY KEY,

  project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

  dataset_version_id BIGINT NOT NULL REFERENCES dataset_versions(id),

  split_id BIGINT NOT NULL REFERENCES dataset_splits(id),

  requested_by BIGINT NOT NULL REFERENCES users(id),

  status export_status NOT NULL,

  export_format TEXT NOT NULL DEFAULT 'yolo',

  export_path TEXT,

  error_message TEXT,

  created_at TIMESTAMP NOT NULL DEFAULT NOW(),

  completed_at TIMESTAMP,

  CONSTRAINT chk_export_format
    CHECK (export_format IN ('yolo', 'coco'))
);

-- =========================================================
-- INDEXES
-- =========================================================

CREATE INDEX idx_project_users_project
ON project_users(project_id);

CREATE INDEX idx_project_users_user
ON project_users(user_id);

CREATE INDEX idx_images_project
ON images(project_id);

CREATE INDEX idx_assignment_status
ON image_assignments(status);

CREATE INDEX idx_annotations_image
ON annotations(image_id);

CREATE INDEX idx_annotations_assignment
ON annotations(assignment_id);

CREATE INDEX idx_annotations_class
ON annotations(class_id);

CREATE INDEX idx_dataset_items_version
ON dataset_items(dataset_version_id);

CREATE INDEX idx_split_items_split
ON split_items(split_id);

CREATE INDEX idx_export_jobs_project
ON export_jobs(project_id);

CREATE INDEX idx_export_jobs_status
ON export_jobs(status);