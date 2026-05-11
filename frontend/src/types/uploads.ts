export type UploadJob = {
  id: number
  project_id: number
  uploaded_by: number
  upload_type: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  original_file_name: string
  total_count: number | null
  processed_count: number | null
  skipped_count: number | null
  error_message: string | null
  created_at: string
  completed_at: string | null
  // Phase 4 - auto label status fields
  auto_label_status?: 'skipped' | 'pending' | 'running' | 'completed' | 'failed' | null
  auto_label_error?: string | null
  cover_image_id?: number | null
  image_count?: number
  done_count?: number
  in_progress_count?: number
  /** annotate 스코프 목록 전용 — 업로드 상세 「전체」탭 범위(assigned|in_progress|done|reverted) 장수 합 */
  annotate_tab_total_count?: number
  /** annotate 스코프 — 내게 배정된 어노 슬롯 총(승인 포함) */
  annotate_assignment_total_count?: number
  /** annotate 스코프 — 최종 승인(approved) 할당 장수 */
  annotate_approved_count?: number
  /** owner · scope=review 전용 */
  review_pending_count?: number | null
  review_approved_count?: number | null
  done_without_reviewer_count?: number | null
  /** reviewer · scope=review 또는 상세 ?mode=review(fetchUploadJob 일치) 시 내 검토 큐 분해 */
  review_queue_total?: number
  review_queue_first_round?: number
  review_queue_after_reject?: number
}

export type UploadImage = {
  id: number
  project_id: number
  upload_job_id: number
  file_name: string
  width: number
  height: number
  created_at: string
  assignment_id?: number
  assignment_status?: AssignmentStatus
  /** 반려를 기록한 유저 id; null이면 아직 반려 이력 없음(최초 검토 배정 분류) */
  assignment_reverted_by?: number | null
  annotation_count?: number
}

/** 서버 저장된 어노테이션 (GET 응답) */
export type Annotation = {
  id: number
  image_id: number
  assignment_id: number
  class_id: number
  x: number
  y: number
  width: number
  height: number
  confidence: number | null
  source: 'auto' | 'manual'
  created_at: string
  updated_at: string
}

/** PUT 요청 바디 한 항목 (id 없음) */
export type BboxItem = {
  class_id: number
  x: number
  y: number
  width: number
  height: number
}

/** PATCH create 항목 */
export type PatchCreateItem = BboxItem

/** PATCH update 항목 (id 필수) */
export type PatchUpdateItem = BboxItem & { id: number }

/** PATCH delete 항목 */
export type PatchDeleteItem = { id: number }

/** PUT 전체 교체 요청 바디 */
export type AnnotationPutRequest = {
  annotations: BboxItem[]
}

/** PATCH 증분 저장 요청 바디 */
export type AnnotationPatchRequest = {
  items: Array<PatchCreateItem | PatchUpdateItem | PatchDeleteItem>
}

/** 서버 응답 - annotation list */
export type AnnotationListResponse = {
  annotations: Annotation[]
}

/** assignment 상태 (CVAT Job 개념 대응) */
export type AssignmentStatus =
  | 'unassigned'
  | 'assigned'
  | 'in_progress'
  | 'done'
  | 'submitted'
  | 'review_assigned'
  | 'approved'
  | 'reverted'
  | 'rejected'

export type Assignment = {
  id: number
  image_id: number
  assigned_to: number | null
  reviewer_id: number | null
  status: AssignmentStatus
  can_edit: boolean
  review_mode: boolean
  submitted_at: string | null
  created_at: string
}

export type UserStatItem = {
  user_id: number
  assigned: number
  /** 승인 요청 전 '완료(Done)' 표시만 한 장수 */
  annotate_done_only: number
  /** 검토 단계 장수 — submitted 또는 review_assigned(리뷰어 배정 후 검토 중) */
  review_requested: number
  approved: number
  reverted: number
  /** 리뷰어 행: 승인 대기(review_assigned) */
  review_pending: number
  /** 어노 행: assigned + in_progress + done + reverted (승인 요청 전) */
  annotate_wip?: number
  /** 어노 행: owner 회수 대상(assigned + in_progress); 리뷰어 행은 0 */
  annotate_recallable?: number
}

export type AssignmentSummary = {
  pool_stats: {
    total: number
    unassigned: number
    in_progress: number
    submitted: number
    review_assigned: number
    review_unassigned_done?: number
    approved?: number
  }
  annotator_stats: UserStatItem[]
  reviewer_stats: UserStatItem[]
}

export type MyAssignmentItem = {
  assignment_id: number
  image_id: number
  project_id: number
  file_name: string
  width: number
  height: number
  status: AssignmentStatus
  can_edit: boolean
}

/** 에디터 화면에서 사용하는 로컬 bbox 상태 (id = undefined: 신규) */
export type LocalBbox = {
  localId: string            // 클라이언트 임시 UUID
  serverId?: number          // 서버에서 받은 id (기존 annotation)
  class_id: number
  x: number
  y: number
  width: number
  height: number
  source: 'auto' | 'manual'
  isDirty: boolean           // 서버와 다른 상태
  isNew: boolean             // 미저장 신규
  isDeleted: boolean         // soft delete 표시
}
