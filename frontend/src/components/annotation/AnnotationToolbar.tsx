/**
 * 상단 툴바: 이전/다음 네비게이션, 저장, 제출, 상태 표시
 */
import type { AssignmentStatus } from '../../types/uploads'

interface Props {
  assignmentStatus: AssignmentStatus | null
  canEdit: boolean
  reviewMode: boolean // reviewer_id 일치 + review_assigned (검토 편집·승인·반려)
  isDirty: boolean
  isSaving: boolean
  autoSaveStatus: 'idle' | 'pending' | 'saving' | 'saved'
  onSubmit: () => void
  onRevert: () => void
  onApprove: () => void   // reviewer: 승인
  onRejectReview: () => void  // reviewer: 반려
  onBack: () => void
  imageName: string
  navLabel: string | null
  canGoPrev: boolean
  canGoNext: boolean
  onPrev: () => void
  onNext: () => void
}

const STATUS_LABELS: Record<string, string> = {
  assigned: '할당됨',
  in_progress: '작업 중',
  done: '완료 표시',
  review_assigned: '리뷰 중',
  submitted: '검토 요청됨',
  approved: '승인됨',
  reverted: '반려됨',
  rejected: '거절됨',
}

/** 검토 표시 또는 반려 상태에서 수정 재개(done·review_assigned·approved·reverted → in_progress 등) */
const RESUME_EDIT_STATUSES: ReadonlySet<string> = new Set([
  'done',
  'review_assigned',
  'approved',
  'reverted',
])

export default function AnnotationToolbar({
  assignmentStatus,
  canEdit,
  reviewMode,
  isDirty,
  isSaving,
  autoSaveStatus,
  onSubmit,
  onRevert,
  onApprove,
  onRejectReview,
  onBack,
  imageName,
  navLabel,
  canGoPrev,
  canGoNext,
  onPrev,
  onNext,
}: Props) {
  const autoSaveLabel =
    autoSaveStatus === 'pending' ? '자동저장 대기…'
    : autoSaveStatus === 'saving' ? '자동저장 중…'
    : autoSaveStatus === 'saved'  ? '✓ 저장됨'
    : null

  return (
    <header className="annotation-toolbar">
      {/* 왼쪽: 뒤로 + 이전/다음 + 이미지 정보 */}
      <div className="toolbar-left">
        <button
          className="btn btn-secondary-dark btn-sm toolbar-back-btn"
          onClick={onBack}
          title="업로드 목록으로"
        >
          ←
        </button>
        <div className="toolbar-nav">
          <button
            className="btn btn-secondary-dark btn-sm toolbar-nav-btn"
            onClick={onPrev}
            disabled={!canGoPrev || isSaving}
            title="이전 이미지 (← 키)"
          >
            ‹
          </button>
          {navLabel && <span className="toolbar-nav-label">{navLabel}</span>}
          <button
            className="btn btn-secondary-dark btn-sm toolbar-nav-btn"
            onClick={onNext}
            disabled={!canGoNext || isSaving}
            title="다음 이미지 (→ 키)"
          >
            ›
          </button>
        </div>

        <span className="toolbar-image-name" title={imageName}>
          {imageName}
        </span>

        {assignmentStatus && (
          <span className={`assignment-badge assignment-badge--${assignmentStatus}`}>
            {STATUS_LABELS[assignmentStatus] ?? assignmentStatus}
          </span>
        )}

        {autoSaveLabel && (
          <span className={`toolbar-autosave toolbar-autosave--${autoSaveStatus}`}>
            {autoSaveLabel}
          </span>
        )}
      </div>

      {/* 오른쪽: 버튼 영역 */}
      <div className="toolbar-right">
        {canEdit && isDirty && (
          <span className="toolbar-dirty-notice">저장 중…</span>
        )}

        {/* 리뷰어 전용: 승인 / 반려 */}
        {reviewMode && (
          <>
            <button
              className="btn btn-success btn-sm toolbar-toggle-btn"
              onClick={onApprove}
              disabled={isSaving || isDirty}
              title="이 이미지를 승인합니다"
            >
              승인
            </button>
            <button
              className="btn btn-danger btn-sm toolbar-toggle-btn"
              onClick={onRejectReview}
              disabled={isSaving || isDirty}
              title={isDirty ? '변경 저장 후 반려할 수 있습니다' : '이 이미지를 반려합니다'}
            >
              반려
            </button>
          </>
        )}

        {/* 어노테이터: 완료/검토단계 또는 반려(reverted) 이후 수정 재개 / 작업 완료 */}
        {!reviewMode && assignmentStatus && (
          RESUME_EDIT_STATUSES.has(assignmentStatus) ? (
            <button
              className="btn btn-secondary-dark btn-sm toolbar-toggle-btn toolbar-toggle-btn--revert"
              onClick={onRevert}
              disabled={isSaving}
              title={
                assignmentStatus === 'reverted'
                  ? '검토 반려 후 작업을 이어합니다 (작업 중으로 전환)'
                  : '수정 상태로 되돌리기'
              }
            >
              {assignmentStatus === 'reverted' ? '다시 작업하기' : '수정하기'}
            </button>
          ) : assignmentStatus === 'in_progress' || assignmentStatus === 'assigned' ? (
            <button
              className="btn btn-success btn-sm toolbar-toggle-btn toolbar-toggle-btn--submit"
              onClick={onSubmit}
              disabled={isSaving || isDirty}
              title={isDirty ? '저장 후 완료할 수 있습니다' : '완료로 표시'}
            >
              완료
            </button>
          ) : null
        )}

        {!canEdit && !reviewMode && !assignmentStatus && (
          <span className="toolbar-readonly-notice">편집 불가</span>
        )}
      </div>
    </header>
  )
}
