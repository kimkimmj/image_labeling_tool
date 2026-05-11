import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { createPortal } from 'react-dom'
import { Link, useParams, useSearchParams } from 'react-router-dom'

import {
  fetchUploadJob,
  fetchUploadJobImages,
  fetchAssignmentSummary,
  getImageContentUrl,
  assignAnnotator,
  recallAnnotator,
  assignReviewer,
  recallReviewer,
  bulkApproveReviewQueue,
  requestReview,
  type BulkApproveReviewScope,
  type ParticipantScopeParam,
} from '../api/uploads'
import { fetchProject, fetchProjectMembers } from '../api/projects'
import type { AssignmentStatus, AssignmentSummary, UploadImage, UploadJob } from '../types/uploads'
import type { ProjectDetail, ProjectMember } from '../types/projects'

// ---------------------------------------------------------------------------
// 상수
// ---------------------------------------------------------------------------

const POLL_INTERVAL_MS = 3000
const PAGE_SIZE = 20

type FilterKey = 'all' | 'in_progress' | 'done' | 'reverted'

const FILTER_LABELS: Record<FilterKey, string> = {
  all: '전체',
  in_progress: '작업 중',
  done: '완료',
  reverted: '반려',
}

const IN_PROGRESS_STATUSES: AssignmentStatus[] = ['assigned', 'in_progress']
/** 목록 카드 테두리: 검토 단계 포함해 “파이프라인 이후” 느낌 */
const CARD_DONE_BORDER_STATUSES: AssignmentStatus[] = ['done', 'submitted', 'review_assigned', 'approved']

function uploadStatusLabel(status: string) {
  return { pending: '대기 중', processing: '처리 중', completed: '완료', failed: '실패' }[status] ?? status
}
function uploadStatusColor(status: string) {
  return { pending: '#888', processing: '#e8a000', completed: '#2a9d2a', failed: '#c0392b' }[status] ?? '#888'
}

function isAnnotateAllTabStatus(s: AssignmentStatus | null | undefined): boolean {
  if (!s) return false
  if (IN_PROGRESS_STATUSES.includes(s)) return true
  if (s === 'done') return true
  return s === 'reverted'
}

/** ?mode=review — 나에게 검토가 연결된 submitted·review_assigned (API와 동일 범위) */
function isReviewAllTabStatus(s: AssignmentStatus | null | undefined): boolean {
  return s === 'review_assigned' || s === 'submitted'
}

/** 리뷰 상단 칩 — 승인 요청 큐 기준 분해 (백엔드 분해 로직과 동일: reverted_by 유무) */
type ReviewQueueTabKey = 'total' | 'first_round' | 'after_reject'

function filterReviewQueueImages(images: UploadImage[], tab: ReviewQueueTabKey): UploadImage[] {
  const base = images.filter((i) => isReviewAllTabStatus(i.assignment_status))
  if (tab === 'total') return base
  if (tab === 'first_round') return base.filter((i) => i.assignment_reverted_by == null)
  return base.filter((i) => i.assignment_reverted_by != null)
}
function filterImages(
  images: UploadImage[],
  filter: FilterKey,
  listScope: ParticipantScopeParam,
): UploadImage[] {
  if (listScope === 'review') {
    if (filter === 'all') return images.filter((i) => isReviewAllTabStatus(i.assignment_status))
    if (filter === 'in_progress')
      return images.filter((i) => i.assignment_status === 'review_assigned')
    if (filter === 'done') return images.filter((i) => i.assignment_status === 'approved')
    return images.filter((i) => i.assignment_status === 'reverted')
  }
  if (filter === 'all') return images.filter((i) => isAnnotateAllTabStatus(i.assignment_status))
  if (filter === 'in_progress')
    return images.filter((i) => i.assignment_status && IN_PROGRESS_STATUSES.includes(i.assignment_status))
  // 완료 탭: 승인 요청 전 “작업 완료(Done)”만 (submitted·review_assigned·approved 등은 전체 탭에도 포함하지 않음)
  if (filter === 'done') return images.filter((i) => i.assignment_status === 'done')
  return images.filter((i) => i.assignment_status === 'reverted')
}

// ---------------------------------------------------------------------------
// 메인 컴포넌트
// ---------------------------------------------------------------------------

export function UploadDetailPage() {
  const { projectId, uploadJobId } = useParams<{ projectId: string; uploadJobId: string }>()
  const [searchParams] = useSearchParams()
  const projectIdNum = projectId ? Number.parseInt(projectId, 10) : NaN
  const jobId = uploadJobId ? Number.parseInt(uploadJobId, 10) : NaN

  const [job, setJob] = useState<UploadJob | null>(null)
  const [images, setImages] = useState<UploadImage[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [myRole, setMyRole] = useState<string>('annotator')
  const [members, setMembers] = useState<ProjectMember[]>([])
  const [imagesLoadError, setImagesLoadError] = useState<string | null>(null)

  // 필터 & 페이지
  const [filter, setFilter] = useState<FilterKey>('all')
  const [reviewQueueTab, setReviewQueueTab] = useState<ReviewQueueTabKey>('total')
  const [page, setPage] = useState(1)
  const [submitReviewBusy, setSubmitReviewBusy] = useState(false)

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const uploadDetailMode = searchParams.get('mode')
  /** 업로드 상세·라벨링 API participant_scope (?mode=annotate|review). 리뷰어 탭과 오너 참여 모드에 공통 사용 */
  const listParticipantScope: ParticipantScopeParam = useMemo(() => {
    if (uploadDetailMode === 'annotate') return 'annotate'
    if (uploadDetailMode === 'review') return 'review'
    return false
  }, [uploadDetailMode])

  // ------------------------------------------------------------------
  // 데이터 로드
  // ------------------------------------------------------------------

  const loadImages = useCallback(async (participantScope: ParticipantScopeParam) => {
    if (!Number.isFinite(jobId)) return
    try {
      const imgs = await fetchUploadJobImages(jobId, participantScope)
      setImages(imgs)
      setImagesLoadError(null)
    } catch {
      setImages([])
      setImagesLoadError('이미지 목록을 불러오지 못했습니다. 새로고침하거나 다시 시도해 주세요.')
    }
  }, [jobId])

  const loadJob = useCallback(async () => {
    if (!Number.isFinite(jobId)) return
    try {
      const scopeArg = listParticipantScope === false ? false : listParticipantScope
      const j = await fetchUploadJob(jobId, scopeArg)
      setJob(j)
      if (j.status === 'completed' || j.status === 'failed') {
        if (pollRef.current) {
          clearInterval(pollRef.current)
          pollRef.current = null
        }
      }
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : '불러오기 실패')
    }
  }, [jobId, listParticipantScope])

  useEffect(() => {
    void loadJob()
    pollRef.current = setInterval(() => void loadJob(), POLL_INTERVAL_MS)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [loadJob])

  useEffect(() => {
    if (!Number.isFinite(projectIdNum)) return
    fetchProject(projectIdNum)
      .then((d: ProjectDetail) => {
        setMyRole(d.my_role)
        if (d.my_role === 'owner') {
          fetchProjectMembers(projectIdNum).then(setMembers).catch(() => {})
        }
      })
      .catch(() => {})
  }, [projectIdNum])

  // Owner 데이터 관리 경로(?mode 없음)에서는 이미지 목록 미사용. 리뷰어·어노테이터는 scope 미지정 시 전체 기본 필터
  useEffect(() => {
    if (myRole === 'owner' && listParticipantScope === false) {
      setImages([])
      return
    }
    if (!job || (job.status !== 'completed' && job.status !== 'failed')) return
    void loadImages(listParticipantScope)
  }, [job, myRole, listParticipantScope, loadImages])

  const handleSubmitForReview = useCallback(async () => {
    if (!Number.isFinite(jobId)) return
    setSubmitReviewBusy(true)
    try {
      const res = await requestReview(jobId)
      alert(
        `검토 요청 완료: ${res.transitioned}장. ` +
          `이전 반려 이력이 있는 이미지는 동일 검토자에게 바로 배정됩니다. ` +
          `그 외는 오너가 리뷰어를 배정하면 검토가 시작됩니다.`,
      )
      await loadImages(listParticipantScope)
    } catch (e) {
      alert('검토 요청 실패: ' + String(e))
    } finally {
      setSubmitReviewBusy(false)
    }
  }, [jobId, listParticipantScope, loadImages])

  useEffect(() => {
    setPage(1)
    if (listParticipantScope === 'review') setReviewQueueTab('total')
  }, [listParticipantScope])

  // ------------------------------------------------------------------
  // 파생 상태
  // ------------------------------------------------------------------

  const isReviewUploadList = listParticipantScope === 'review'
  const filtered = useMemo(() => {
    if (isReviewUploadList) return filterReviewQueueImages(images, reviewQueueTab)
    return filterImages(images, filter, listParticipantScope)
  }, [isReviewUploadList, images, reviewQueueTab, filter, listParticipantScope])
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const safePage = Math.min(page, totalPages)
  const pageImages = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE)

  const filterCounts: Record<FilterKey, number> = {
    all: filterImages(images, 'all', listParticipantScope).length,
    in_progress: filterImages(images, 'in_progress', listParticipantScope).length,
    done: filterImages(images, 'done', listParticipantScope).length,
    reverted: filterImages(images, 'reverted', listParticipantScope).length,
  }

  const handleFilterChange = (f: FilterKey) => {
    setFilter(f)
    setPage(1)
  }

  const handleReviewQueueTab = useCallback((tab: ReviewQueueTabKey) => {
    setReviewQueueTab(tab)
    setPage(1)
  }, [])

  // ------------------------------------------------------------------
  // 에러 / 로딩
  // ------------------------------------------------------------------

  if (!Number.isFinite(jobId) || !Number.isFinite(projectIdNum)) {
    return (
      <div className="page-projects">
        <p className="banner banner--error">잘못된 경로</p>
        <Link to="/projects" className="inline-link">프로젝트 목록</Link>
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="page-projects">
        <p className="banner banner--error">{loadError}</p>
        <Link to={`/projects/${projectIdNum}`} className="inline-link">프로젝트로 돌아가기</Link>
      </div>
    )
  }

  if (!job) {
    return <div className="page-projects"><p className="muted">불러오는 중…</p></div>
  }

  const isOwner = myRole === 'owner'
  const participantWorkUi = !isOwner || listParticipantScope !== false

  // ------------------------------------------------------------------
  // 렌더
  // ------------------------------------------------------------------

  const labelQueryExtras =
    listParticipantScope === 'annotate'
      ? '&mode=annotate'
      : listParticipantScope === 'review'
        ? '&mode=review'
        : ''

  const doneForReviewCount = images.filter((i) => i.assignment_status === 'done').length
  const jobListingReady = job.status === 'completed' || job.status === 'failed'
  /** 리뷰어는 검토 요청 API 사용 불가(백엔드 검증). 어노테이터·오너(어노테이션 모드)만 버튼 표시 */
  const canShowReviewRequestBtn =
    participantWorkUi &&
    jobListingReady &&
    (myRole === 'annotator' || (isOwner && listParticipantScope === 'annotate'))
  const reviewRequestDisabled = submitReviewBusy || doneForReviewCount === 0
  const reviewRequestTitle =
    doneForReviewCount === 0
      ? '라벨 에디터에서 작업을 완료(Done)한 이미지만 검토 요청 대상입니다. 완료 탭에 보이더라도 이미 검토를 요청한 장은 여기 포함되지 않습니다.'
      : `완료(Done) 상태 ${doneForReviewCount}장이 검토 단계로 넘어갑니다. 반려 이력이 있으면 동일 검토자에게 바로 갑니다.`

  return (
    <div className="page-projects">
      {/* 헤더 */}
      <header className="page-home__header">
        <div>
          <p className="eyebrow">업로드 #{job.id}</p>
          <h1 style={{ wordBreak: 'break-all' }}>{job.original_file_name}</h1>
          <p className="muted">
            상태:{' '}
            <strong style={{ color: uploadStatusColor(job.status) }}>
              {uploadStatusLabel(job.status)}
            </strong>
            {job.processed_count !== null && (
              <span style={{ marginLeft: 12 }}>
                저장 <strong>{job.processed_count}</strong>장 / 전체{' '}
                <strong>{job.total_count ?? '?'}</strong>장
                {job.skipped_count != null && job.skipped_count > 0
                  ? ` (제외 ${job.skipped_count})`
                  : null}
              </span>
            )}
            {job.auto_label_status && job.auto_label_status !== 'skipped' && (
              <span style={{ marginLeft: 12 }}>
                자동라벨:{' '}
                <strong>{
                  { pending: '대기', running: '실행 중', completed: '완료', failed: '실패' }[job.auto_label_status] ?? job.auto_label_status
                }</strong>
              </span>
            )}
          </p>
          {job.error_message && (
            <p className="banner banner--error" style={{ marginTop: 8 }}>{job.error_message}</p>
          )}
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center' }}>
          <Link to={`/projects/${projectIdNum}`} className="btn-secondary">
            프로젝트로 돌아가기
          </Link>
        </div>
      </header>

      {/* 처리 중 안내 */}
      {(job.status === 'processing' || job.status === 'pending') && (
        <section className="panel panel--spaced">
          <p className="muted">이미지를 처리하고 있습니다. 잠시 후 자동으로 업데이트됩니다…</p>
        </section>
      )}

      {/* 이미지 목록 — 참여자 또는 owner가 어노테이션/리뷰 탭에서 진입한 경우 */}
      {participantWorkUi && jobListingReady ? (
        <section className="panel panel--spaced">
          {imagesLoadError ? (
            <p className="banner banner--error" style={{ marginBottom: 12 }} role="alert">
              {imagesLoadError}
            </p>
          ) : null}
          {isReviewUploadList ? (
            <div className="img-list-header">
              <div className="img-list-header__start">
                <div className="img-filter-tabs" role="tablist" aria-label="검토 큐 요약">
                  <button
                    type="button"
                    role="tab"
                    aria-selected={reviewQueueTab === 'total'}
                    className={`img-filter-tab${reviewQueueTab === 'total' ? ' img-filter-tab--active' : ''}`}
                    onClick={() => handleReviewQueueTab('total')}
                  >
                    승인 요청(할당 합계)
                    <span className="img-filter-count">{job.review_queue_total ?? 0}</span>
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={reviewQueueTab === 'first_round'}
                    className={`img-filter-tab${reviewQueueTab === 'first_round' ? ' img-filter-tab--active' : ''}`}
                    onClick={() => handleReviewQueueTab('first_round')}
                  >
                    최초 배정
                    <span className="img-filter-count">{job.review_queue_first_round ?? 0}</span>
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={reviewQueueTab === 'after_reject'}
                    className={`img-filter-tab${reviewQueueTab === 'after_reject' ? ' img-filter-tab--active' : ''}`}
                    onClick={() => handleReviewQueueTab('after_reject')}
                  >
                    반려 후 재요청
                    <span className="img-filter-count">{job.review_queue_after_reject ?? 0}</span>
                  </button>
                </div>
              </div>
              <span className="img-list-header__filtered-count muted">{filtered.length}장</span>
            </div>
          ) : (
            <div className="img-list-header">
              <div className="img-list-header__start">
                <div className="img-filter-tabs">
                  {(Object.keys(FILTER_LABELS) as FilterKey[]).map((key) => (
                    <button
                      key={key}
                      type="button"
                      className={`img-filter-tab${filter === key ? ' img-filter-tab--active' : ''}`}
                      onClick={() => handleFilterChange(key)}
                    >
                      {FILTER_LABELS[key]}
                      <span className="img-filter-count">{filterCounts[key]}</span>
                    </button>
                  ))}
                </div>
                {canShowReviewRequestBtn ? (
                  <button
                    type="button"
                    className="btn-primary img-list-header__request-btn"
                    disabled={reviewRequestDisabled}
                    title={reviewRequestTitle}
                    onClick={() => void handleSubmitForReview()}
                  >
                    {submitReviewBusy
                      ? '처리 중…'
                      : doneForReviewCount > 0
                        ? `승인 요청 (${doneForReviewCount})`
                        : '승인 요청'}
                  </button>
                ) : null}
              </div>
              <span className="img-list-header__filtered-count muted">{filtered.length}장</span>
            </div>
          )}

          {images.length > 0 ? (
            <>
              {pageImages.length > 0 ? (
                <div className="img-grid">
                  {pageImages.map((img) => (
                    <ImageCard
                      key={img.id}
                      image={img}
                      projectId={projectIdNum}
                      jobId={jobId}
                      labelQueryExtras={labelQueryExtras}
                      participantScope={listParticipantScope}
                    />
                  ))}
                </div>
              ) : (
                <p className="muted" style={{ padding: '24px 0', textAlign: 'center' }}>
                  해당 조건의 이미지가 없습니다.
                </p>
              )}

              {totalPages > 1 && (
                <Pagination page={safePage} totalPages={totalPages} onChange={setPage} />
              )}
            </>
          ) : (
            <p className="muted" style={{ padding: '12px 0 0' }}>
              {imagesLoadError
                ? '위 오류를 해결하면 목록이 표시됩니다.'
                : listParticipantScope === 'review'
                  ? '나에게 검토 요청되어 배정된 이미지가 없습니다.'
                  : '저장된 이미지가 없거나, 아직 이 업로드에 배정된 이미지가 없습니다.'}
            </p>
          )}
        </section>
      ) : null}

      {/* 데이터 관리 — owner가 데이터 관리 경로로 들어온 경우만 (?mode 없음) */}
      {isOwner && listParticipantScope === false ? <ManageTab jobId={jobId} members={members} /> : null}
    </div>
  )
}

// ---------------------------------------------------------------------------
// ManageTab — Owner 전용 할당 관리
// ---------------------------------------------------------------------------

interface ManageTabProps {
  jobId: number
  members: ProjectMember[]
}

type AssignFormKind = 'annotate' | 'review'
type AssignFormOp = 'assign' | 'recall'

/** 전체 현황 박스 클릭 시 할당 폼에 넣는 초기값 */
type ManageStatPreset =
  | 'anno_unassigned_assign'
  | 'anno_wip_recall'
  | 'review_queue_assign'
  | 'review_assigned_recall'

function manageAssignModalTitle(preset: ManageStatPreset | null): string {
  switch (preset) {
    case 'anno_unassigned_assign':
      return '어노테이션 할당 (미할당 이미지)'
    case 'anno_wip_recall':
      return '어노테이션 회수'
    case 'review_queue_assign':
      return '리뷰어 할당 (검토 요청·미배정)'
    case 'review_assigned_recall':
      return '리뷰 회수'
    default:
      return '할당·회수'
  }
}

function ManageTab({ jobId, members }: ManageTabProps) {
  const [summary, setSummary] = useState<AssignmentSummary | null>(null)
  const [summaryError, setSummaryError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  /** 통합 할당·회수 폼 (모달 안에서만 사용) */
  const [formUserId, setFormUserId] = useState<number | ''>('')
  const [formKind, setFormKind] = useState<AssignFormKind>('annotate')
  const [formOp, setFormOp] = useState<AssignFormOp>('assign')
  const [formCount, setFormCount] = useState('')
  const [statPreset, setStatPreset] = useState<ManageStatPreset | null>(null)
  const [assignModalOpen, setAssignModalOpen] = useState(false)
  const [bulkApprovePickerOpen, setBulkApprovePickerOpen] = useState(false)
  const [bulkApproveScopeChoice, setBulkApproveScopeChoice] =
    useState<BulkApproveReviewScope>('submitted_unassigned')

  const loadSummary = useCallback(async () => {
    try {
      const s = await fetchAssignmentSummary(jobId)
      setSummary(s)
      setSummaryError(null)
    } catch (e) {
      setSummaryError(e instanceof Error ? e.message : '집계 로드 실패')
    }
  }, [jobId])

  useEffect(() => { void loadSummary() }, [loadSummary])

  const reviewers = members.filter((m) => m.role === 'reviewer')
  const ownerMember = members.find((m) => m.role === 'owner')

  /** 리뷰 할당·회수 대상: owner + reviewer */
  const reviewTargets = useMemo(() => {
    const rest = reviewers
      .filter((m) => !ownerMember || m.user_id !== ownerMember.user_id)
      .slice()
      .sort((a, b) => a.email.localeCompare(b.email))
    return ownerMember ? [ownerMember, ...rest] : rest
  }, [ownerMember, reviewers])

  /** 어노테이션 할당·회수 멤버 선택: 프로젝트 멤버 전원 */
  const membersSorted = useMemo(
    () => [...members].sort((a, b) => a.email.localeCompare(b.email)),
    [members],
  )

  const canReviewFor = useCallback(
    (uid: number) => reviewTargets.some((m) => m.user_id === uid),
    [reviewTargets],
  )

  const isProjectMember = useCallback(
    (uid: number) => members.some((m) => m.user_id === uid),
    [members],
  )

  /** 모달 멤버 드롭다운 옵션 */
  const memberSelectOptions = useMemo(() => {
    if (
      statPreset === 'anno_unassigned_assign' ||
      statPreset === 'anno_wip_recall'
    ) {
      return membersSorted
    }
    if (
      statPreset === 'review_queue_assign' ||
      statPreset === 'review_assigned_recall'
    ) {
      return reviewTargets
    }
    return formKind === 'annotate' ? membersSorted : reviewTargets
  }, [statPreset, formKind, membersSorted, reviewTargets])

  const annotateRecallableByUser = useMemo(() => {
    const m = new Map<number, number>()
    if (!summary) return m
    for (const s of summary.annotator_stats) {
      m.set(s.user_id, s.annotate_recallable ?? 0)
    }
    return m
  }, [summary])

  const reviewPendingByUser = useMemo(() => {
    const m = new Map<number, number>()
    if (!summary) return m
    for (const s of summary.reviewer_stats) {
      m.set(s.user_id, s.review_pending ?? 0)
    }
    return m
  }, [summary])

  const applyStatPreset = useCallback(
    (preset: ManageStatPreset) => {
      setStatPreset(preset)
      switch (preset) {
        case 'anno_unassigned_assign':
          setFormKind('annotate')
          setFormOp('assign')
          if (summary != null) {
            const n = summary.pool_stats.unassigned
            setFormCount(n > 0 ? String(n) : '')
          } else {
            setFormCount('')
          }
          break
        case 'anno_wip_recall':
          setFormKind('annotate')
          setFormOp('recall')
          setFormCount('')
          break
        case 'review_queue_assign':
          setFormKind('review')
          setFormOp('assign')
          if (summary != null) {
            const n = summary.pool_stats.review_unassigned_done ?? 0
            setFormCount(n > 0 ? String(n) : '')
          } else {
            setFormCount('')
          }
          break
        case 'review_assigned_recall':
          setFormKind('review')
          setFormOp('recall')
          setFormCount('')
          break
      }
    },
    [summary],
  )

  const clearStatPreset = useCallback(() => setStatPreset(null), [])

  const closeAssignModal = useCallback(() => {
    setBulkApprovePickerOpen(false)
    setAssignModalOpen(false)
    setStatPreset(null)
  }, [])

  const openAssignModalWithPreset = useCallback(
    (preset: ManageStatPreset) => {
      setFormUserId('')
      applyStatPreset(preset)
      setAssignModalOpen(true)
    },
    [applyStatPreset],
  )

  useEffect(() => {
    if (!assignModalOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || busy) return
      if (bulkApprovePickerOpen) {
        setBulkApprovePickerOpen(false)
        return
      }
      closeAssignModal()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [assignModalOpen, bulkApprovePickerOpen, busy, closeAssignModal])

  async function runAssignAnnotator(uid: number, email: string, countStr: string) {
    const cnt = Number(countStr)
    if (!uid || !Number.isFinite(cnt) || cnt < 1) {
      alert(`${email}: 할당할 장수(1 이상)를 입력하세요.`)
      return
    }
    setBusy(true)
    try {
      const res = await assignAnnotator(jobId, uid, cnt)
      alert(`${email}: ${res.assigned}장 할당되었습니다.`)
      closeAssignModal()
      await loadSummary()
    } catch (e) { alert('할당 실패: ' + String(e)) }
    finally { setBusy(false) }
  }

  async function runRecallAnnotator(uid: number, email: string, countStr: string) {
    if (!uid) return
    const cnt = Number(countStr)
    if (!Number.isFinite(cnt) || cnt < 1) {
      alert('회수할 장수(1 이상)를 입력하세요.')
      return
    }
    if (
      !confirm(
        `${email}에게 배정된 미완료(할당·작업 중) 이미지 중 최대 ${cnt}장을 회수합니다. 계속하시겠습니까?`,
      )
    )
      return
    setBusy(true)
    try {
      const res = await recallAnnotator(jobId, uid, cnt)
      alert(`${email}: ${res.recalled}장 회수되었습니다.`)
      closeAssignModal()
      await loadSummary()
    } catch (e) { alert('회수 실패: ' + String(e)) }
    finally { setBusy(false) }
  }

  async function runAssignReviewer(uid: number, email: string, countStr: string) {
    const cnt = Number(countStr)
    if (!uid || !Number.isFinite(cnt) || cnt < 1) {
      alert(`${email}: 할당할 장수(1 이상)를 입력하세요.`)
      return
    }
    setBusy(true)
    try {
      const res = await assignReviewer(jobId, uid, cnt)
      alert(`${email}: ${res.assigned}장 리뷰 할당되었습니다.`)
      closeAssignModal()
      await loadSummary()
    } catch (e) { alert('리뷰 할당 실패: ' + String(e)) }
    finally { setBusy(false) }
  }

  async function runRecallReviewer(uid: number, email: string, countStr: string) {
    if (!uid) return
    const cnt = Number(countStr)
    if (!Number.isFinite(cnt) || cnt < 1) {
      alert('회수할 장수(1 이상)를 입력하세요.')
      return
    }
    if (
      !confirm(
        `${email}에게 배정된 검토 중 이미지 중 최대 ${cnt}장을 회수합니다. 계속하시겠습니까?`,
      )
    )
      return
    setBusy(true)
    try {
      const res = await recallReviewer(jobId, uid, cnt)
      alert(`${email}: ${res.recalled}장 회수되었습니다.`)
      closeAssignModal()
      await loadSummary()
    } catch (e) { alert('회수 실패: ' + String(e)) }
    finally { setBusy(false) }
  }

  async function submitBulkApproveFromPicker() {
    setBusy(true)
    try {
      const res = await bulkApproveReviewQueue(jobId, bulkApproveScopeChoice)
      closeAssignModal()
      alert(`${res.approved}장 승인되었습니다.`)
      await loadSummary()
    } catch (e) {
      alert('일괄 승인 실패: ' + String(e))
    } finally {
      setBusy(false)
    }
  }

  async function handleUnifiedAssignSubmit(e: FormEvent) {
    e.preventDefault()
    if (formUserId === '') {
      alert('멤버를 선택하세요.')
      return
    }
    const uid = formUserId
    const mem = members.find((m) => m.user_id === uid)
    const email = mem?.email ?? `#${uid}`
    if (formKind === 'annotate') {
      if (!isProjectMember(uid)) {
        alert('프로젝트 멤버만 선택할 수 있습니다.')
        return
      }
      if (formOp === 'assign') await runAssignAnnotator(uid, email, formCount)
      else await runRecallAnnotator(uid, email, formCount)
    } else {
      if (!canReviewFor(uid)) {
        alert('이 멤버는 리뷰(검토) 할당 대상이 아닙니다.')
        return
      }
      if (formOp === 'assign') await runAssignReviewer(uid, email, formCount)
      else await runRecallReviewer(uid, email, formCount)
    }
  }

  const selectedMemberHasReview = formUserId !== '' && canReviewFor(formUserId)

  const selectedAnnotRecallable =
    formUserId !== '' ? annotateRecallableByUser.get(formUserId) ?? 0 : 0
  const selectedReviewRecallable =
    formUserId !== '' ? reviewPendingByUser.get(formUserId) ?? 0 : 0

  const modalRecallAnnotHint =
    statPreset === 'anno_wip_recall' ||
    (statPreset === null && formKind === 'annotate' && formOp === 'recall')
  const modalRecallReviewHint =
    statPreset === 'review_assigned_recall' ||
    (statPreset === null && formKind === 'review' && formOp === 'recall')

  const memberSummaryByUser = useMemo(() => {
    if (!summary) return []
    const ids = Array.from(
      new Set([
        ...summary.annotator_stats.map((s) => s.user_id),
        ...summary.reviewer_stats.map((s) => s.user_id),
      ]),
    )
    const rowLabel = (uid: number) =>
      members.find((m) => m.user_id === uid)?.email ?? `#${uid}`
    return ids
      .map((uid) => ({
        uid,
        emailLabel: rowLabel(uid),
        roleLabel: members.find((m) => m.user_id === uid)?.role ?? null,
        ann: summary.annotator_stats.find((s) => s.user_id === uid) ?? null,
        rev: summary.reviewer_stats.find((s) => s.user_id === uid) ?? null,
      }))
      .sort((a, b) => a.emailLabel.localeCompare(b.emailLabel))
  }, [summary, members])

  return (
    <div className="manage-tab">
      {summaryError ? <p className="banner banner--error">{summaryError}</p> : null}

      <section className="panel panel--spaced">
        <h3 className="section-title">전체 현황</h3>
        {summary ? (
          <div className="pool-stats-section">
            <div className="pool-stats-row">
              <PoolStatBox label="전체" value={summary.pool_stats.total} color="#555" />
            </div>

            <h4 className="pool-stats-subheading">어노테이션</h4>
            <div className="pool-stats-row">
              <PoolStatBox
                label="미할당"
                hint="작업 미할당"
                value={summary.pool_stats.unassigned}
                color="#888"
                actionTitle="클릭: 어노테이션 할당 창 열기 (미할당 장수를 제안합니다)"
                isActive={assignModalOpen && statPreset === 'anno_unassigned_assign'}
                onAction={() => openAssignModalWithPreset('anno_unassigned_assign')}
              />
              <PoolStatBox
                label="작업 중"
                hint="승인 요청 전"
                value={summary.pool_stats.in_progress}
                color="#e8a000"
                actionTitle="클릭: 어노테이션 회수 창 열기"
                isActive={assignModalOpen && statPreset === 'anno_wip_recall'}
                onAction={() => openAssignModalWithPreset('anno_wip_recall')}
              />
            </div>

            <h4 className="pool-stats-subheading">Review</h4>
            <div className="pool-stats-row">
              <PoolStatBox
                label="검토 요청"
                hint="리뷰 미배정"
                value={summary.pool_stats.review_unassigned_done ?? 0}
                color="#2b8a8a"
                actionTitle="클릭: 리뷰어 할당 창 열기 (검토 요청·미배정 장수를 제안합니다)"
                isActive={assignModalOpen && statPreset === 'review_queue_assign'}
                onAction={() => openAssignModalWithPreset('review_queue_assign')}
              />
              <PoolStatBox
                label="검토 배정"
                value={summary.pool_stats.review_assigned}
                color="#2a7abf"
                actionTitle="클릭: 리뷰 회수 창 열기"
                isActive={assignModalOpen && statPreset === 'review_assigned_recall'}
                onAction={() => openAssignModalWithPreset('review_assigned_recall')}
              />
            </div>

            <h4 className="pool-stats-subheading">최종 제출</h4>
            <div className="pool-stats-row">
              <PoolStatBox label="승인됨" value={summary.pool_stats.approved ?? 0} color="#2a9d2a" />
            </div>
          </div>
        ) : !summaryError ? (
          <p className="muted" style={{ padding: '8px 0' }}>전체 집계를 불러오는 중입니다…</p>
        ) : null}

        <div className="manage-pool-and-assign">
          <h4 className="pool-stats-subheading">할당·회수</h4>
          <p className="muted assign-unified-lead">
            숫자 박스를 누르면 해당 작업(어노테이션 할당·회수 등)이 고정된 <strong>모달</strong>이 열립니다.
          </p>
          {members.length === 0 ? (
            <p className="muted">
              프로젝트에 멤버가 없습니다.
            </p>
          ) : null}
        </div>
      </section>

      {summary ? (
        <section className="panel panel--spaced">
          <h3 className="section-title">멤버별 할당 요약</h3>
          <p className="muted" style={{ fontSize: '0.85rem', margin: '0 0 12px' }}>
            어노테이션은 총 배정·작업(할당만·in_progress·Done·반려)·검토 단계(submitted·검토 배정)·승인(approved) 순으로,
            Review는 검토 배정 총·승인 대기(review_assigned)만 표시합니다. (할당만 받고 미착수·리뷰어 배정
            검토 중 등은 총 배정 안에 포함될 수 있습니다.)
          </p>
          {memberSummaryByUser.length === 0 ? (
            <p className="muted">할당 집계가 있는 멤버가 없습니다.</p>
          ) : (
            <div className="member-summary-by-user">
              {memberSummaryByUser.map(({ uid, emailLabel, roleLabel, ann, rev }) => (
                <article key={uid} className="member-summary-card">
                  <header className="member-summary-card__head">
                    <span className="member-summary-card__email"><code>{emailLabel}</code></span>
                    {roleLabel != null && roleLabel !== '' ? (
                      <span className="member-summary-card__role muted">{roleLabel}</span>
                    ) : null}
                  </header>
                  <div className="member-summary-card__slices">
                    {ann != null ? (
                      <div className="member-summary-slice">
                        <h4 className="member-summary-slice__title">어노테이션</h4>
                        <dl className="member-summary-stats">
                          <div className="member-summary-stats__row">
                            <dt>총 배정</dt>
                            <dd>{ann.assigned}</dd>
                          </div>
                          <div className="member-summary-stats__row">
                            <dt>
                              작업 중{' '}
                              <span className="member-summary-stats__hint">
                                (할당만·작업중·Done·반려 복귀)
                              </span>
                            </dt>
                            <dd>{ann.annotate_wip ?? 0}</dd>
                          </div>
                          <div className="member-summary-stats__row">
                            <dt>
                              검토 요청·검토 중{' '}
                              <span className="member-summary-stats__hint">
                                (submitted·검토 배정)
                              </span>
                            </dt>
                            <dd>{ann.review_requested}</dd>
                          </div>
                          <div className="member-summary-stats__row">
                            <dt>
                              승인됨{' '}
                              <span className="member-summary-stats__hint">(approved)</span>
                            </dt>
                            <dd>{ann.approved}</dd>
                          </div>
                        </dl>
                      </div>
                    ) : null}
                    {rev != null ? (
                      <div className="member-summary-slice">
                        <h4 className="member-summary-slice__title">Review</h4>
                        <dl className="member-summary-stats">
                          <div className="member-summary-stats__row">
                            <dt>
                              검토 배정{' '}
                              <span className="member-summary-stats__hint">(총)</span>
                            </dt>
                            <dd>{rev.assigned}</dd>
                          </div>
                          <div className="member-summary-stats__row">
                            <dt>
                              승인 대기 중{' '}
                              <span className="member-summary-stats__hint">
                                (검토 요청 후 나에게 배정됨)
                              </span>
                            </dt>
                            <dd>{rev.review_pending}</dd>
                          </div>
                        </dl>
                      </div>
                    ) : null}
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      ) : null}

      {assignModalOpen
        ? createPortal(
            <div
              className="assign-modal-backdrop"
              role="presentation"
              onClick={() => {
                if (!busy) closeAssignModal()
              }}
            >
              <div
                className="assign-modal-dialog"
                role="dialog"
                aria-modal="true"
                aria-labelledby="assign-modal-title"
                onClick={(e) => e.stopPropagation()}
              >
                <header className="assign-modal-header">
                  <h4 id="assign-modal-title" className="assign-modal-title">
                    {manageAssignModalTitle(statPreset)}
                  </h4>
                  <button
                    type="button"
                    className="btn-secondary assign-modal-close"
                    disabled={busy}
                    onClick={() => closeAssignModal()}
                  >
                    닫기
                  </button>
                </header>
                {memberSelectOptions.length === 0 ? (
                  <p className="muted">선택 가능한 멤버가 없습니다.</p>
                ) : (
                  <form
                    className="assign-unified-form assign-unified-form--modal"
                    onSubmit={(e) => void handleUnifiedAssignSubmit(e)}
                  >
                    <div className="assign-unified-field">
                      <label className="assign-unified-label" htmlFor="assign-modal-member">
                        멤버
                      </label>
                      <select
                        id="assign-modal-member"
                        className="assign-select assign-select--block"
                        disabled={busy}
                        value={formUserId === '' ? '' : String(formUserId)}
                        onChange={(e) => {
                          const raw = e.target.value
                          const uid = raw === '' ? '' : Number.parseInt(raw, 10)
                          if (statPreset === null) {
                            clearStatPreset()
                            setFormUserId(uid)
                          } else {
                            setFormUserId(uid)
                            if (statPreset === 'anno_wip_recall' && uid !== '') {
                              const max = annotateRecallableByUser.get(uid) ?? 0
                              setFormCount(max > 0 ? String(max) : '')
                            } else if (statPreset === 'review_assigned_recall' && uid !== '') {
                              const max = reviewPendingByUser.get(uid) ?? 0
                              setFormCount(max > 0 ? String(max) : '')
                            }
                          }
                        }}
                      >
                        <option value="">선택…</option>
                        {memberSelectOptions.map((m) => {
                          const bits: string[] = []
                          if (canReviewFor(m.user_id)) bits.push('검토 가능')
                          const cap = bits.length > 0 ? ` · ${bits.join('/')}` : ''
                          return (
                            <option key={m.user_id} value={m.user_id}>
                              {m.email} ({m.role}){cap}
                            </option>
                          )
                        })}
                      </select>
                    </div>

                    {statPreset === null ? (
                      <>
                        <fieldset className="assign-unified-fieldset" disabled={busy || formUserId === ''}>
                          <legend className="assign-unified-legend">역할</legend>
                          <div className="assign-unified-radios">
                            <label className="assign-unified-radio">
                              <input
                                type="radio"
                                name="assign-modal-kind"
                                checked={formKind === 'annotate'}
                                onChange={() => {
                                  clearStatPreset()
                                  setFormKind('annotate')
                                }}
                              />
                              어노테이션 할당·회수
                            </label>
                            <label className="assign-unified-radio">
                              <input
                                type="radio"
                                name="assign-modal-kind"
                                checked={formKind === 'review'}
                                disabled={formUserId !== '' && !selectedMemberHasReview}
                                onChange={() => {
                                  clearStatPreset()
                                  setFormKind('review')
                                  setFormUserId((prev) =>
                                    typeof prev === 'number' && !canReviewFor(prev) ? '' : prev,
                                  )
                                }}
                              />
                              리뷰(검토) 할당·회수
                            </label>
                          </div>
                        </fieldset>

                        <fieldset className="assign-unified-fieldset" disabled={busy || formUserId === ''}>
                          <legend className="assign-unified-legend">작업</legend>
                          <div className="assign-unified-radios">
                            <label className="assign-unified-radio">
                              <input
                                type="radio"
                                name="assign-modal-op"
                                checked={formOp === 'assign'}
                                onChange={() => {
                                  clearStatPreset()
                                  setFormOp('assign')
                                }}
                              />
                              할당
                            </label>
                            <label className="assign-unified-radio">
                              <input
                                type="radio"
                                name="assign-modal-op"
                                checked={formOp === 'recall'}
                                onChange={() => {
                                  clearStatPreset()
                                  setFormOp('recall')
                                }}
                              />
                              회수
                            </label>
                          </div>
                        </fieldset>
                      </>
                    ) : null}

                    {statPreset === 'review_queue_assign' ? (
                      <div className="assign-unified-field">
                        <span className="assign-unified-label">일괄 최종 승인</span>
                        <p className="muted" style={{ margin: '0 0 10px', fontSize: '0.9rem' }}>
                          리뷰어 배정 없이 검토 단계 이미지를 승인합니다. 검토자·승인자 기록은 owner로 남습니다.
                        </p>
                        <button
                          type="button"
                          className="btn-secondary"
                          disabled={busy}
                          onClick={() => {
                            setBulkApproveScopeChoice('submitted_unassigned')
                            setBulkApprovePickerOpen(true)
                          }}
                        >
                          일괄 승인…
                        </button>
                      </div>
                    ) : null}

                    <div className="assign-unified-field">
                      <label className="assign-unified-label" htmlFor="assign-modal-count">
                        장수{' '}
                        <span className="muted">
                          (할당 또는 회수 시 처리할 최대 장수 · 1 이상)
                        </span>
                        {statPreset === 'anno_unassigned_assign' && summary ? (
                          <>
                            {' '}
                            <span className="muted">
                              · 총 미할당 {summary.pool_stats.unassigned}장
                            </span>
                          </>
                        ) : null}
                        {statPreset === 'review_queue_assign' && summary ? (
                          <>
                            {' '}
                            <span className="muted">
                              · 검토 요청·미배정 {summary.pool_stats.review_unassigned_done ?? 0}장
                            </span>
                          </>
                        ) : null}
                      </label>
                      <input
                        id="assign-modal-count"
                        type="number"
                        min={1}
                        className="assign-input-num assign-input-num--block"
                        placeholder="예: 50"
                        disabled={busy}
                        value={formCount}
                        onChange={(e) => {
                          if (statPreset === null) clearStatPreset()
                          setFormCount(e.target.value)
                        }}
                      />
                      {modalRecallAnnotHint && formUserId !== '' ? (
                        <p className="muted assign-unified-hint">
                          선택 멤버 회수 가능(할당만·작업 중) 최대{' '}
                          <strong>{selectedAnnotRecallable}</strong>장 — 실제 회수는 이 값 이하입니다.
                        </p>
                      ) : null}
                      {modalRecallReviewHint && formUserId !== '' ? (
                        <p className="muted assign-unified-hint">
                          선택 리뷰어 검토 배정(회수 대상) 최대{' '}
                          <strong>{selectedReviewRecallable}</strong>장 — 실제 회수는 이 값 이하입니다.
                        </p>
                      ) : null}
                    </div>

                    <div className="assign-unified-actions">
                      <button type="button" className="btn-secondary" disabled={busy} onClick={() => closeAssignModal()}>
                        취소
                      </button>
                      <button type="submit" className="btn-primary" disabled={busy}>
                        실행
                      </button>
                    </div>
                  </form>
                )}
              </div>
            </div>,
            document.body,
          )
        : null}

      {bulkApprovePickerOpen && assignModalOpen
        ? createPortal(
            <div
              className="assign-modal-backdrop assign-modal-backdrop--nested"
              role="presentation"
              onClick={() => {
                if (!busy) setBulkApprovePickerOpen(false)
              }}
            >
              <div
                className="assign-modal-dialog"
                role="dialog"
                aria-modal="true"
                aria-labelledby="bulk-approve-picker-title"
                onClick={(e) => e.stopPropagation()}
              >
                <header className="assign-modal-header">
                  <h4 id="bulk-approve-picker-title" className="assign-modal-title">
                    일괄 최종 승인
                  </h4>
                  <button
                    type="button"
                    className="btn-secondary assign-modal-close"
                    disabled={busy}
                    onClick={() => setBulkApprovePickerOpen(false)}
                  >
                    닫기
                  </button>
                </header>
                <p className="muted" style={{ margin: '0 0 14px', fontSize: '0.9rem' }}>
                  승인 범위를 선택한 뒤 실행하세요. 검토자·승인자 기록은 owner로 남습니다.
                </p>
                <fieldset className="assign-unified-fieldset" disabled={busy} style={{ marginBottom: 16 }}>
                  <legend className="assign-unified-legend">승인 범위</legend>
                  <div className="assign-unified-radios assign-unified-radios--stack">
                    <label className="assign-unified-radio" style={{ alignItems: 'flex-start' }}>
                      <input
                        type="radio"
                        name="bulk-approve-scope"
                        checked={bulkApproveScopeChoice === 'submitted_unassigned'}
                        onChange={() => setBulkApproveScopeChoice('submitted_unassigned')}
                      />
                      <span>
                        미배정 검토 대기만
                        <span className="muted" style={{ display: 'block', fontWeight: 400, marginTop: 4 }}>
                          리뷰어 미배정 검토 요청(submitted)만 승인합니다.
                          {summary != null ? (
                            <>
                              {' '}
                              (현재 약 {summary.pool_stats.review_unassigned_done ?? 0}장)
                            </>
                          ) : null}
                        </span>
                      </span>
                    </label>
                    <label className="assign-unified-radio" style={{ alignItems: 'flex-start' }}>
                      <input
                        type="radio"
                        name="bulk-approve-scope"
                        checked={bulkApproveScopeChoice === 'include_review_assigned'}
                        onChange={() => setBulkApproveScopeChoice('include_review_assigned')}
                      />
                      <span>
                        검토 배정 포함 전체
                        <span className="muted" style={{ display: 'block', fontWeight: 400, marginTop: 4 }}>
                          위 범위에 더해 리뷰어에게 배정된 검토 중(review_assigned)까지 승인합니다.
                          {summary != null ? (
                            <>
                              {' '}
                              (미배정 약 {summary.pool_stats.review_unassigned_done ?? 0}장 + 검토 배정 약{' '}
                              {summary.pool_stats.review_assigned ?? 0}장)
                            </>
                          ) : null}
                        </span>
                      </span>
                    </label>
                  </div>
                </fieldset>
                <div className="assign-unified-actions">
                  <button
                    type="button"
                    className="btn-secondary"
                    disabled={busy}
                    onClick={() => setBulkApprovePickerOpen(false)}
                  >
                    취소
                  </button>
                  <button
                    type="button"
                    className="btn-primary"
                    disabled={busy}
                    onClick={() => void submitBulkApproveFromPicker()}
                  >
                    승인 실행
                  </button>
                </div>
              </div>
            </div>,
            document.body,
          )
        : null}
    </div>
  )
}

function PoolStatBox({
  label,
  value,
  color,
  hint,
  onAction,
  isActive = false,
  actionTitle,
}: {
  label: string
  value: number
  color: string
  hint?: string
  /** 클릭 시 할당 폼과 연동(미할당→어노 할당, 작업중→어노 회수 등) */
  onAction?: () => void
  isActive?: boolean
  actionTitle?: string
}) {
  const body = (
    <>
      <span className="pool-stat-label">{label}</span>
      {hint ? <span className="pool-stat-hint">{hint}</span> : null}
      <span className="pool-stat-value" style={{ color }}>{value}</span>
    </>
  )
  const cls = ['pool-stat-box', isActive ? 'pool-stat-box--active' : ''].filter(Boolean).join(' ')
  if (onAction != null) {
    return (
      <button type="button" className={cls} title={actionTitle} onClick={() => void onAction()}>
        {body}
      </button>
    )
  }
  return <div className={cls}>{body}</div>
}

// ---------------------------------------------------------------------------
// ImageCard
// ---------------------------------------------------------------------------

interface ImageCardProps {
  image: UploadImage
  projectId: number
  jobId: number
  /** 라벨 에디터 URL에 붙일 추가 쿼리 (예: &mode=annotate) */
  labelQueryExtras?: string
  /** owner 참여 어노테이션/리뷰 시 이미지 원본 URL에 participant_scope */
  participantScope?: ParticipantScopeParam
}

function statusBorderClass(status: AssignmentStatus | undefined): string {
  if (!status) return ''
  if (CARD_DONE_BORDER_STATUSES.includes(status)) return 'img-card--done'
  if (IN_PROGRESS_STATUSES.includes(status)) return 'img-card--wip'
  if (status === 'reverted') return 'img-card--reverted'
  if (status === 'unassigned') return 'img-card--unassigned'
  return ''
}

function ImageCard({ image, projectId, jobId, labelQueryExtras = '', participantScope = false }: ImageCardProps) {
  const editorUrl = `/images/${image.id}/label?project_id=${projectId}&upload_job_id=${jobId}${labelQueryExtras}`
  const borderCls = statusBorderClass(image.assignment_status)

  return (
    <Link to={editorUrl} className={`img-card ${borderCls}`}>
      <div className="img-card__thumb">
        <img
          src={getImageContentUrl(image.id, participantScope)}
          alt={image.file_name}
          loading="lazy"
          crossOrigin="use-credentials"
        />
      </div>
    </Link>
  )
}

// ---------------------------------------------------------------------------
// Pagination
// ---------------------------------------------------------------------------

interface PaginationProps {
  page: number
  totalPages: number
  onChange: (p: number) => void
}

function Pagination({ page, totalPages, onChange }: PaginationProps) {
  const range: number[] = []
  for (let i = Math.max(1, page - 2); i <= Math.min(totalPages, page + 2); i++) {
    range.push(i)
  }

  return (
    <div className="pagination">
      <button className="page-btn" onClick={() => onChange(page - 1)} disabled={page === 1}>‹</button>

      {range[0] > 1 && (
        <>
          <button className="page-btn" onClick={() => onChange(1)}>1</button>
          {range[0] > 2 && <span className="page-ellipsis">…</span>}
        </>
      )}

      {range.map((p) => (
        <button
          key={p}
          className={`page-btn${p === page ? ' page-btn--active' : ''}`}
          onClick={() => onChange(p)}
        >
          {p}
        </button>
      ))}

      {range[range.length - 1] < totalPages && (
        <>
          {range[range.length - 1] < totalPages - 1 && <span className="page-ellipsis">…</span>}
          <button className="page-btn" onClick={() => onChange(totalPages)}>{totalPages}</button>
        </>
      )}

      <button className="page-btn" onClick={() => onChange(page + 1)} disabled={page === totalPages}>›</button>
    </div>
  )
}
