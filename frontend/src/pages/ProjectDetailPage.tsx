import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import {
  addClass,
  createInvitation,
  deleteClass,
  deleteProject,
  fetchAvailableModels,
  fetchClasses,
  fetchProject,
  fetchProjectMembers,
  fetchSelectedModel,
  patchClass,
  purgeClass,
} from '../api/projects'
import { uploadMlModel } from '../api/mlModels'
import { createUploadJob, deleteUploadJob, fetchUploadJobs } from '../api/uploads'
import type { MlModel, ProjectClass, ProjectDetail, ProjectMember } from '../types/projects'
import type { UploadJob } from '../types/uploads'
import { DatasetExportPanel } from '../components/project/DatasetExportPanel'

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    pending: '대기 중',
    processing: '처리 중',
    completed: '완료',
    failed: '실패',
  }
  return map[status] ?? status
}

/** <input type="color"> 용: 비어 있거나 잘못된 값이면 중간 회색 */
function normalizeHexForPicker(hex: string): string {
  const t = hex.trim()
  const m6 = /^#?([0-9a-f]{6})$/i.exec(t)
  if (m6) return `#${m6[1].toLowerCase()}`
  const m3 = /^#?([0-9a-f]{3})$/i.exec(t)
  if (m3) {
    const s = m3[1].toLowerCase()
    return `#${s[0]}${s[0]}${s[1]}${s[1]}${s[2]}${s[2]}`
  }
  return '#808080'
}

function statusColor(status: string): string {
  const map: Record<string, string> = {
    pending: '#888',
    processing: '#e8a000',
    completed: '#2a9d2a',
    failed: '#c0392b',
  }
  return map[status] ?? '#888'
}

type JobStatsMode = 'owner_standard' | 'owner_review' | 'participant_annotate' | 'participant_review'

function UploadJobRowStats({ job, mode }: { job: UploadJob; mode: JobStatsMode }) {
  if (mode === 'participant_annotate') {
    const tabTot = job.annotate_tab_total_count ?? 0
    const queueExcApproved = job.image_count
    const totalAssigned =
      job.annotate_assignment_total_count ?? queueExcApproved ?? 0
    const approved =
      typeof job.annotate_approved_count === 'number'
        ? job.annotate_approved_count
        : Math.max(
            0,
            (job.annotate_assignment_total_count ?? totalAssigned) -
              (queueExcApproved ?? 0),
          )
    return (
      <>
        <span className="upload-job-row__stat">
          배정 총 <strong>{totalAssigned}</strong>장
        </span>
        <span className="upload-job-row__stat upload-job-row__stat--done">
          승인 <strong>{approved}</strong>장
        </span>
        <span className="upload-job-row__stat upload-job-row__stat--wip">
          작업중·완료·반려 <strong>{tabTot}</strong>
        </span>
        {typeof queueExcApproved === 'number' && queueExcApproved > tabTot ? (
          <span className="upload-job-row__stat">
            검토 처리 중 <strong>{queueExcApproved - tabTot}</strong>
          </span>
        ) : null}
      </>
    )
  }
  if (mode === 'owner_review') {
    const rp = job.review_pending_count ?? 0
    const ap = job.review_approved_count ?? 0
    return (
      <>
        <span className="upload-job-row__stat upload-job-row__stat--wip">
          검토 중 <strong>{rp}</strong>
        </span>
        <span className="upload-job-row__stat upload-job-row__stat--done">
          승인 <strong>{ap}</strong>
        </span>
      </>
    )
  }
  if (mode === 'participant_review') {
    return (
      <>
        <span className="upload-job-row__stat">
          검토 배정 <strong>{job.image_count ?? '?'}</strong>장
        </span>
        <span className="upload-job-row__stat upload-job-row__stat--done">
          승인 <strong>{job.done_count ?? 0}</strong>
        </span>
        <span className="upload-job-row__stat upload-job-row__stat--wip">
          승인 요청 대기 <strong>{job.review_queue_total ?? 0}</strong>
        </span>
      </>
    )
  }
  return (
    <>
      <span className="upload-job-row__stat">
        총 <strong>{job.image_count ?? job.processed_count ?? '?'}</strong>장
      </span>
      {(job.done_count ?? 0) > 0 && (
        <span className="upload-job-row__stat upload-job-row__stat--done">
          완료 <strong>{job.done_count}</strong>
        </span>
      )}
      {(job.in_progress_count ?? 0) > 0 && (
        <span className="upload-job-row__stat upload-job-row__stat--wip">
          진행 중 <strong>{job.in_progress_count}</strong>
        </span>
      )}
    </>
  )
}

type ManageAccordionKey = 'upload' | 'export' | 'members' | 'classes' | 'invite' | 'delete'

function ManageAccordionPanel({
  panelId,
  title,
  open,
  onToggle,
  children,
}: {
  panelId: ManageAccordionKey
  title: string
  open: boolean
  onToggle: (id: ManageAccordionKey) => void
  children: ReactNode
}) {
  return (
    <section className="panel panel--spaced project-manage-accordion">
      <h2 className="project-manage-accordion__heading">
        <button
          type="button"
          className="project-manage-accordion__trigger"
          aria-expanded={open}
          id={`manage-acc-${panelId}`}
          onClick={() => onToggle(panelId)}
        >
          <span className="project-manage-accordion__chevron" aria-hidden>
            {open ? '▼' : '▶'}
          </span>
          {title}
        </button>
      </h2>
      {open ? (
        <div className="project-manage-accordion__content" role="region" aria-labelledby={`manage-acc-${panelId}`}>
          {children}
        </div>
      ) : null}
    </section>
  )
}

export function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const id = projectId ? Number.parseInt(projectId, 10) : NaN
  const navigate = useNavigate()

  const [detail, setDetail] = useState<ProjectDetail | null>(null)
  const [members, setMembers] = useState<ProjectMember[] | null>(null)
  const [membersError, setMembersError] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [inviteRole, setInviteRole] = useState<'annotator' | 'reviewer'>('annotator')
  const [inviteBusy, setInviteBusy] = useState(false)
  const [inviteError, setInviteError] = useState<string | null>(null)
  const [lastInvite, setLastInvite] = useState<{ token: string; join_url: string; expires_at: string } | null>(null)

  // models for ZIP auto-label (project owner)
  const [availableModels, setAvailableModels] = useState<MlModel[]>([])
  const [selectedModel, setSelectedModelState] = useState<MlModel | null | undefined>(undefined)
  const [zipModelId, setZipModelId] = useState<number | undefined>(undefined)
  const [inlineModelBusy, setInlineModelBusy] = useState(false)
  const [inlineModelError, setInlineModelError] = useState<string | null>(null)
  const modelFileInputRef = useRef<HTMLInputElement>(null)

  // class management
  const [classes, setClasses] = useState<ProjectClass[] | null>(null)
  const [classError, setClassError] = useState<string | null>(null)
  const [newClassName, setNewClassName] = useState('')
  const [newClassColor, setNewClassColor] = useState('')
  const [addClassBusy, setAddClassBusy] = useState(false)
  const [editingClass, setEditingClass] = useState<{ id: number; name: string; color: string } | null>(null)

  // upload
  const [uploadJobs, setUploadJobs] = useState<UploadJob[] | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploadBusy, setUploadBusy] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  /** 프로젝트에 모델이 없을 때 ZIP 업로드 분기: idle → 업로드 클릭 시 choose → 그냥 업로드 | pick_model */
  const [zipNoModelFlow, setZipNoModelFlow] = useState<'idle' | 'choose' | 'pick_model'>('idle')

  const [deletingUploadJobId, setDeletingUploadJobId] = useState<number | null>(null)

  const [ownerTab, setOwnerTab] = useState<'manage' | 'annotate' | 'review'>('manage')
  const [reviewerTab, setReviewerTab] = useState<'annotate' | 'review'>('annotate')

  const [deleteConfirmName, setDeleteConfirmName] = useState('')
  const [deleteProjectBusy, setDeleteProjectBusy] = useState(false)
  const [deleteProjectError, setDeleteProjectError] = useState<string | null>(null)

  const [openManageAccordion, setOpenManageAccordion] = useState<ManageAccordionKey | null>('upload')

  const toggleManageAccordion = useCallback((key: ManageAccordionKey) => {
    setOpenManageAccordion((cur) => (cur === key ? null : key))
  }, [])

  const isAnnotateWorkUnitSection = useMemo(() => {
    if (!detail) return false
    return (
      detail.my_role === 'annotator' ||
      (detail.my_role === 'reviewer' && reviewerTab === 'annotate') ||
      (detail.my_role === 'owner' && ownerTab === 'annotate')
    )
  }, [detail, ownerTab, reviewerTab])

  const annotateListTotals = useMemo(() => {
    if (!isAnnotateWorkUnitSection || uploadJobs === null) return null
    return uploadJobs.reduce(
      (acc, j) => {
        const totalAll = j.annotate_assignment_total_count ?? j.image_count ?? 0
        const queue = j.image_count ?? 0
        const approved =
          typeof j.annotate_approved_count === 'number'
            ? j.annotate_approved_count
            : Math.max(0, totalAll - queue)
        return {
          assigned: acc.assigned + totalAll,
          approved: acc.approved + approved,
          tabUnion: acc.tabUnion + (j.annotate_tab_total_count ?? 0),
        }
      },
      { assigned: 0, approved: 0, tabUnion: 0 },
    )
  }, [uploadJobs, isAnnotateWorkUnitSection])

  const jobStatsMode: JobStatsMode = useMemo(() => {
    if (!detail) return 'owner_standard'
    const isOwner = detail.my_role === 'owner'
    const isReviewer = detail.my_role === 'reviewer'
    const annSection =
      detail.my_role === 'annotator' ||
      (isReviewer && reviewerTab === 'annotate') ||
      (isOwner && ownerTab === 'annotate')
    if (isOwner && ownerTab === 'review') return 'owner_review'
    if (isReviewer && reviewerTab === 'review') return 'participant_review'
    if (annSection) return 'participant_annotate'
    return 'owner_standard'
  }, [detail, ownerTab, reviewerTab])

  const workUnitSectionTitle = useMemo(() => {
    if (!detail) return '작업 단위'
    const isOwner = detail.my_role === 'owner'
    const isReviewer = detail.my_role === 'reviewer'
    if (isOwner && ownerTab === 'manage') return '데이터 업로드'
    if (isOwner && ownerTab === 'review') return '리뷰 작업 단위'
    if (isReviewer && reviewerTab === 'review') return '내 검토 할당'
    return '어노테이션 작업 단위'
  }, [detail, ownerTab, reviewerTab])

  const loadDetail = useCallback(async () => {
    if (!Number.isFinite(id)) return
    setLoadError(null)
    try {
      const d = await fetchProject(id)
      setDetail(d)
      setMembers(null)
      setMembersError(null)
      setLastInvite(null)

      if (d.my_role === 'owner') {
        try {
          const m = await fetchProjectMembers(id)
          setMembers(m)
        } catch (e) {
          setMembersError(e instanceof Error ? e.message : '멤버 목록 실패')
        }
        try {
          const [avail, sel, pc] = await Promise.all([
            fetchAvailableModels(id),
            fetchSelectedModel(id),
            fetchClasses(id, { includeInactive: true }),
          ])
          setAvailableModels(avail)
          setSelectedModelState(sel)
          setZipModelId(sel?.id ?? avail[0]?.id)
          setClasses(pc)
        } catch (e) {
          setClassError(e instanceof Error ? e.message : '클래스/모델 목록 실패')
        }
      }
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : '불러오기 실패')
      setDetail(null)
    }
  }, [id])

  useEffect(() => {
    if (selectedModel) setZipNoModelFlow('idle')
  }, [selectedModel])

  async function performZipUpload(file: File, modelId?: number) {
    if (!Number.isFinite(id)) return
    setUploadBusy(true)
    setUploadError(null)
    try {
      await createUploadJob(id, file, {
        modelId: modelId !== undefined ? modelId : undefined,
      })
      const jobs = await fetchUploadJobs(id, 'all')
      setUploadJobs(jobs)
      if (modelId != null) {
        try {
          const [nextSel, pc] = await Promise.all([
            fetchSelectedModel(id),
            fetchClasses(id, { includeInactive: true }),
          ])
          setSelectedModelState(nextSel)
          setClasses(pc)
        } catch {
          /* ignore refresh errors */
        }
      }
      if (fileInputRef.current) fileInputRef.current.value = ''
      setZipNoModelFlow('idle')
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : '업로드 실패')
    } finally {
      setUploadBusy(false)
    }
  }

  async function onZipUploadButtonClick() {
    if (detail?.my_role !== 'owner' || uploadModelInfoLoading) return
    const file = fileInputRef.current?.files?.[0]
    if (!file || !Number.isFinite(id)) {
      setUploadError('ZIP 파일을 선택하세요.')
      return
    }
    setUploadError(null)

    if (selectedModel) {
      await performZipUpload(file)
      return
    }

    if (zipNoModelFlow === 'idle') {
      setZipNoModelFlow('choose')
      return
    }

    if (zipNoModelFlow === 'pick_model') {
      if (zipModelId == null) {
        setUploadError('모델을 선택하거나 + 로 .pt 파일을 추가하세요.')
        return
      }
      await performZipUpload(file, zipModelId)
    }
  }

  async function onZipUploadPlainNoModel() {
    if (detail?.my_role !== 'owner' || uploadModelInfoLoading) return
    const file = fileInputRef.current?.files?.[0]
    if (!file || !Number.isFinite(id)) {
      setUploadError('ZIP 파일을 선택하세요.')
      return
    }
    setUploadError(null)
    await performZipUpload(file)
  }

  async function handleDeleteUploadJob(job: UploadJob) {
    if (!Number.isFinite(id) || !detail || detail.my_role !== 'owner') return
    const fname =
      job.original_file_name.length > 80
        ? `${job.original_file_name.slice(0, 77)}…`
        : job.original_file_name
    const ok = window.confirm(
      `「${fname}」업로드 배치와 모든 이미지·어노테이션·저장 파일을 삭제합니다. 복구할 수 없습니다. 계속할까요?`,
    )
    if (!ok) return
    setDeletingUploadJobId(job.id)
    setUploadError(null)
    try {
      await deleteUploadJob(id, job.id)
      let scope: 'all' | 'annotate' | 'review' = 'annotate'
      if (detail.my_role === 'owner') {
        scope = ownerTab === 'review' ? 'review' : ownerTab === 'manage' ? 'all' : 'annotate'
      } else if (detail.my_role === 'reviewer') {
        scope = reviewerTab === 'review' ? 'review' : 'annotate'
      }
      const jobs = await fetchUploadJobs(id, scope)
      setUploadJobs(jobs)
    } catch (err) {
      const raw = err instanceof Error ? err.message : '삭제 실패'
      let msg = raw
      if (raw.includes('upload_job_storage_purge_failed') || raw.startsWith('HTTP 503'))
        msg = '파일 저장소 정리에 실패했습니다. 잠시 후 다시 시도하세요.'
      setUploadError(msg)
    } finally {
      setDeletingUploadJobId(null)
    }
  }

  useEffect(() => {
    void loadDetail()
  }, [loadDetail])

  useEffect(() => {
    if (!Number.isFinite(id) || !detail) return
    const role = detail.my_role
    let scope: 'all' | 'annotate' | 'review'
    if (role === 'owner') {
      scope =
        ownerTab === 'review' ? 'review' : ownerTab === 'manage' ? 'all' : 'annotate'
    } else if (role === 'reviewer') {
      scope = reviewerTab === 'review' ? 'review' : 'annotate'
    } else {
      scope = 'annotate'
    }
    fetchUploadJobs(id, scope)
      .then(setUploadJobs)
      .catch(() => setUploadJobs([]))
  }, [id, detail, ownerTab, reviewerTab])

  async function uploadPickedModelFile() {
    if (!Number.isFinite(id)) return
    const file = modelFileInputRef.current?.files?.[0]
    if (!file) return
    setInlineModelBusy(true)
    setInlineModelError(null)
    try {
      const model = await uploadMlModel(file)
      const avail = await fetchAvailableModels(id)
      setAvailableModels(avail)
      setZipModelId(model.id)
      if (modelFileInputRef.current) modelFileInputRef.current.value = ''
    } catch (err) {
      setInlineModelError(err instanceof Error ? err.message : '모델 업로드 실패')
    } finally {
      setInlineModelBusy(false)
    }
  }

  async function handleAddClass(e: React.FormEvent) {
    e.preventDefault()
    if (!newClassName.trim() || !Number.isFinite(id)) return
    setAddClassBusy(true)
    setClassError(null)
    try {
      const cls = await addClass(id, { name: newClassName.trim(), color: newClassColor || null })
      setClasses((prev) => [...(prev ?? []), cls])
      setNewClassName('')
      setNewClassColor('')
    } catch (err) {
      setClassError(err instanceof Error ? err.message : '클래스 추가 실패')
    } finally {
      setAddClassBusy(false)
    }
  }

  async function handlePatchClass(classId: number, name: string, color: string) {
    setClassError(null)
    try {
      const updated = await patchClass(classId, { name, color: color || null })
      setClasses((prev) => prev?.map((c) => (c.id === updated.id ? updated : c)) ?? null)
      setEditingClass(null)
    } catch (err) {
      setClassError(err instanceof Error ? err.message : '클래스 수정 실패')
    }
  }

  async function handleDeleteClass(classId: number) {
    setClassError(null)
    try {
      const updated = await deleteClass(classId)
      setClasses((prev) => prev?.map((c) => (c.id === updated.id ? updated : c)) ?? null)
    } catch (err) {
      setClassError(err instanceof Error ? err.message : '클래스 비활성화 실패')
    }
  }

  async function handleReactivateClass(classId: number) {
    setClassError(null)
    try {
      const updated = await patchClass(classId, { is_active: true })
      setClasses((prev) => prev?.map((c) => (c.id === updated.id ? updated : c)) ?? null)
    } catch (err) {
      setClassError(err instanceof Error ? err.message : '클래스 복구 실패')
    }
  }

  async function handlePurgeClass(classId: number) {
    const ok = window.confirm(
      '이 클래스를 DB에서 완전히 삭제합니다. 이 클래스를 쓰는 라벨(박스)이 있으면 삭제할 수 없습니다. 계속할까요?',
    )
    if (!ok) return
    setClassError(null)
    try {
      await purgeClass(classId)
      setClasses((prev) => prev?.filter((c) => c.id !== classId) ?? null)
    } catch (err) {
      const raw = err instanceof Error ? err.message : '클래스 삭제 실패'
      let msg = raw
      if (raw.includes('class_has_annotations'))
        msg = '이 클래스를 사용 중인 어노테이션이 있어 삭제할 수 없습니다. 먼저 해당 박스를 제거하세요.'
      else if (raw.includes('class_hard_delete_only_for_custom_classes'))
        msg = '모델에서 가져온 클래스는 비활성화만 할 수 있습니다.'
      setClassError(msg)
    }
  }

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault()
    if (!Number.isFinite(id)) return
    setInviteBusy(true)
    setLastInvite(null)
    setInviteError(null)
    try {
      const res = await createInvitation(id, inviteRole)
      setLastInvite({ token: res.token, join_url: res.join_url, expires_at: res.expires_at })
    } catch (err) {
      setLastInvite(null)
      setInviteError(err instanceof Error ? err.message : '초대 생성 실패')
    } finally {
      setInviteBusy(false)
    }
  }

  async function handleDeleteProject(e: React.FormEvent) {
    e.preventDefault()
    if (!Number.isFinite(id) || !detail || deleteConfirmName !== detail.name) return
    setDeleteProjectBusy(true)
    setDeleteProjectError(null)
    try {
      await deleteProject(id, deleteConfirmName)
      navigate('/projects')
    } catch (err) {
      const raw = err instanceof Error ? err.message : '삭제 실패'
      let msg = raw
      if (raw.includes('project_delete_name_mismatch')) msg = '프로젝트 이름이 일치하지 않습니다.'
      else if (raw.includes('project_has_active_uploads')) msg = '처리 중인 ZIP 업로드가 있을 때는 삭제할 수 없습니다. 완료·실패 후 다시 시도하세요.'
      else if (raw.includes('project_storage_purge_failed') || raw.startsWith('HTTP 503'))
        msg = '파일 저장소 정리에 실패했습니다. 잠시 후 다시 시도하세요. 프로젝트 데이터는 그대로입니다.'
      setDeleteProjectError(msg)
    } finally {
      setDeleteProjectBusy(false)
    }
  }

  if (!Number.isFinite(id)) {
    return (
      <div className="page-projects">
        <p className="banner banner--error">잘못된 프로젝트 ID</p>
        <Link to="/projects" className="inline-link">
          목록으로
        </Link>
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="page-projects">
        <p className="banner banner--error">{loadError}</p>
        <Link to="/projects" className="inline-link">
          목록으로
        </Link>
      </div>
    )
  }

  if (!detail) {
    return (
      <div className="page-projects">
        <p className="muted">불러오는 중…</p>
      </div>
    )
  }

  const isOwner = detail.my_role === 'owner'
  const isReviewer = detail.my_role === 'reviewer'
  const uploadModelInfoLoading = isOwner && ownerTab === 'manage' && selectedModel === undefined

  const uploadJobsBlock = (
    <>
      {uploadJobs && uploadJobs.length > 0 ? (
        <div className="upload-job-list" style={{ marginTop: 16 }}>
          {uploadJobs.map((job) => (
            <div key={job.id} className="upload-job-list__item">
              <button
                type="button"
                className="upload-job-row"
                onClick={() => {
                  let qs = ''
                  if (isOwner && ownerTab === 'annotate') qs = '?mode=annotate'
                  else if (isOwner && ownerTab === 'review') qs = '?mode=review'
                  else if (isReviewer && reviewerTab === 'annotate') qs = '?mode=annotate'
                  else if (isReviewer && reviewerTab === 'review') qs = '?mode=review'
                  navigate(`/projects/${job.project_id}/uploads/${job.id}${qs}`)
                }}
              >
                <div className="upload-job-row__thumb">
                  {job.cover_image_id ? (
                    <img
                      src={`/api/images/${job.cover_image_id}/content`}
                      alt={job.original_file_name}
                      loading="lazy"
                      crossOrigin="use-credentials"
                    />
                  ) : (
                    <div className="upload-job-row__placeholder">
                      <span style={{ color: statusColor(job.status), fontSize: '0.72rem' }}>
                        {statusLabel(job.status)}
                      </span>
                    </div>
                  )}
                  <span
                    className="upload-job-row__dot"
                    style={{ background: statusColor(job.status) }}
                  />
                </div>

                <div className="upload-job-row__info">
                  <UploadJobRowStats job={job} mode={jobStatsMode} />
                </div>
              </button>
              {isOwner && ownerTab === 'manage' ? (
                <button
                  type="button"
                  className="btn btn-danger btn-sm upload-job-list__delete"
                  title="이 업로드 배치 삭제"
                  disabled={deletingUploadJobId === job.id}
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    void handleDeleteUploadJob(job)
                  }}
                >
                  {deletingUploadJobId === job.id ? '삭제 중…' : '삭제'}
                </button>
              ) : null}
            </div>
          ))}
        </div>
      ) : uploadJobs !== null ? (
        <p className="muted" style={{ marginTop: 12 }}>
          표시할 업로드 단위가 없습니다.
        </p>
      ) : (
        <p className="muted" style={{ marginTop: 12 }}>
          불러오는 중…
        </p>
      )}
    </>
  )

  return (
    <div className="page-projects">
      <header className="page-home__header">
        <div>
          <p className="eyebrow">프로젝트 #{detail.id}</p>
          <h1>{detail.name}</h1>
          <p className="muted home-lead">
            내 역할: <strong>{detail.my_role}</strong>
          </p>
          {detail.description ? <p className="muted">{detail.description}</p> : null}
        </div>
        <Link to="/projects" className="btn-secondary">
          목록으로
        </Link>
      </header>

      <section className="panel panel--spaced">
        <h2>정보</h2>
        <dl className="account-dl">
          <dt>생성 시각</dt>
          <dd>{new Date(detail.created_at).toLocaleString()}</dd>
        </dl>
      </section>

      {isOwner ? (
        <div className="upload-detail-tabs project-detail-tabs">
          <button
            type="button"
            className={`upload-detail-tab${ownerTab === 'manage' ? ' upload-detail-tab--active' : ''}`}
            onClick={() => setOwnerTab('manage')}
          >
            데이터 관리
          </button>
          <button
            type="button"
            className={`upload-detail-tab${ownerTab === 'annotate' ? ' upload-detail-tab--active' : ''}`}
            onClick={() => setOwnerTab('annotate')}
          >
            어노테이션
          </button>
          <button
            type="button"
            className={`upload-detail-tab${ownerTab === 'review' ? ' upload-detail-tab--active' : ''}`}
            onClick={() => setOwnerTab('review')}
          >
            리뷰
          </button>
        </div>
      ) : null}

      {isReviewer ? (
        <div className="upload-detail-tabs project-detail-tabs">
          <button
            type="button"
            className={`upload-detail-tab${reviewerTab === 'annotate' ? ' upload-detail-tab--active' : ''}`}
            onClick={() => setReviewerTab('annotate')}
          >
            어노테이션
          </button>
          <button
            type="button"
            className={`upload-detail-tab${reviewerTab === 'review' ? ' upload-detail-tab--active' : ''}`}
            onClick={() => setReviewerTab('review')}
          >
            리뷰
          </button>
        </div>
      ) : null}

      {isOwner && ownerTab === 'manage' ? (
        <>
          <ManageAccordionPanel
            panelId="upload"
            title="데이터 업로드"
            open={openManageAccordion === 'upload'}
            onToggle={toggleManageAccordion}
          >
            <>
              {uploadModelInfoLoading ? (
                <p className="muted fine-muted">모델·클래스 정보를 불러오는 중…</p>
              ) : selectedModel ? (
                <>
                  <p className="muted fine-muted">
                    이 프로젝트에는 이미 자동 라벨용 YOLO 모델이 지정되어 있습니다. 별도 옵션 없이 ZIP만 업로드하면 지정된 모델(
                    <strong>{selectedModel.name}</strong>
                    {selectedModel.version ? ` · v${selectedModel.version}` : ''})로 이 배치에 자동 라벨링이 적용됩니다.
                  </p>
                  <div className="form-stack form-inline">
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".zip"
                      className="input-text"
                      disabled={uploadModelInfoLoading}
                    />
                    <button
                      type="button"
                      className="btn-primary"
                      disabled={uploadBusy || uploadModelInfoLoading}
                      onClick={() => void onZipUploadButtonClick()}
                    >
                      {uploadBusy ? '업로드 중…' : 'ZIP 업로드'}
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <div className="form-stack form-inline" style={{ marginBottom: 12 }}>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".zip"
                      className="input-text"
                      disabled={uploadModelInfoLoading}
                    />
                    {zipNoModelFlow === 'idle' ? (
                      <button
                        type="button"
                        className="btn-primary"
                        disabled={uploadBusy || uploadModelInfoLoading}
                        onClick={() => void onZipUploadButtonClick()}
                      >
                        {uploadBusy ? '업로드 중…' : 'ZIP 업로드'}
                      </button>
                    ) : null}
                  </div>
                  {zipNoModelFlow === 'idle' ? (
                    <p className="muted fine-muted">
                      프로젝트에 자동 라벨용 모델이 <strong>지정되어 있지 않습니다</strong>. ZIP을 선택한 뒤 «ZIP 업로드»를 누르면,
                      모델 없이 올릴지·업로드와 함께 모델을 지정할지 선택할 수 있습니다. 모델이 프로젝트에 지정된 뒤에는 같은 화면에서
                      ZIP만 올리면 자동 라벨이 적용됩니다. 모델 파일은{' '}
                      <Link to="/models" className="inline-link">
                        모델 관리
                      </Link>
                      에서 미리 등록할 수 있습니다.
                    </p>
                  ) : null}
                  {zipNoModelFlow === 'choose' ? (
                    <div
                      className="panel"
                      style={{
                        marginBottom: 16,
                        padding: '12px 14px',
                        border: '1px solid var(--border)',
                        borderRadius: 10,
                        background: 'var(--social-bg)',
                      }}
                    >
                      <p className="fine-muted" style={{ margin: '0 0 10px' }}>
                        설정된 모델이 없습니다. 자동 라벨링을 하시려면 모델을 등록하세요.
                      </p>
                      <div className="form-inline" style={{ flexWrap: 'wrap', gap: 8 }}>
                        <button
                          type="button"
                          className="btn-secondary"
                          disabled={uploadBusy || uploadModelInfoLoading}
                          onClick={() => void onZipUploadPlainNoModel()}
                        >
                          그냥 업로드
                        </button>
                        <button
                          type="button"
                          className="btn-primary"
                          disabled={uploadBusy || uploadModelInfoLoading}
                          onClick={() => {
                            setZipNoModelFlow('pick_model')
                            setUploadError(null)
                          }}
                        >
                          모델 설정 후 업로드
                        </button>
                        <button
                          type="button"
                          className="btn-secondary"
                          disabled={uploadBusy}
                          onClick={() => {
                            setZipNoModelFlow('idle')
                            setUploadError(null)
                          }}
                        >
                          닫기
                        </button>
                      </div>
                    </div>
                  ) : null}
                  {zipNoModelFlow === 'pick_model' ? (
                    <>
                      <p className="muted fine-muted" style={{ marginBottom: 8 }}>
                        아래에서 모델을 고르거나 «+»로 .pt를 추가한 뒤 «선택한 모델로 업로드»를 누르세요. 업로드가 끝나면 이 화면은 다시
                        ZIP 파일만 선택하는 형태로 돌아갑니다.
                      </p>
                      {inlineModelError ? (
                        <p className="banner banner--error" role="alert">
                          {inlineModelError}
                        </p>
                      ) : null}
                      <div
                        style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12, alignItems: 'center' }}
                      >
                        <select
                          className="input-text"
                          aria-label="ZIP 업로드 시 자동 라벨에 쓸 모델"
                          style={{ flex: '1 1 220px', minWidth: '180px', maxWidth: '100%' }}
                          value={zipModelId === undefined ? '' : String(zipModelId)}
                          onChange={(e) => {
                            const v = e.target.value
                            setZipModelId(v === '' ? undefined : Number.parseInt(v, 10))
                          }}
                        >
                          <option value="">모델을 선택하세요…</option>
                          {availableModels.map((m) => (
                            <option key={m.id} value={String(m.id)}>
                              {m.name}
                              {m.version ? ` (v${m.version})` : ''}
                            </option>
                          ))}
                        </select>
                        <button
                          type="button"
                          className="btn-secondary"
                          title="모델 추가 (.pt)"
                          disabled={inlineModelBusy}
                          style={{ minWidth: 40, paddingLeft: 12, paddingRight: 12 }}
                          aria-label="모델 파일 추가"
                          onClick={() => modelFileInputRef.current?.click()}
                        >
                          {inlineModelBusy ? '…' : '+'}
                        </button>
                        <input
                          ref={modelFileInputRef}
                          type="file"
                          accept=".pt"
                          style={{ display: 'none' }}
                          onChange={() => void uploadPickedModelFile()}
                        />
                      </div>
                      <div className="form-inline" style={{ flexWrap: 'wrap', gap: 8 }}>
                        <button
                          type="button"
                          className="btn-primary"
                          disabled={uploadBusy || uploadModelInfoLoading}
                          onClick={() => void onZipUploadButtonClick()}
                        >
                          {uploadBusy ? '업로드 중…' : '선택한 모델로 업로드'}
                        </button>
                        <button
                          type="button"
                          className="btn-secondary"
                          disabled={uploadBusy}
                          onClick={() => {
                            setZipNoModelFlow('idle')
                            setUploadError(null)
                          }}
                        >
                          취소
                        </button>
                      </div>
                    </>
                  ) : null}
                </>
              )}
              {uploadError ? (
                <p className="banner banner--error" role="alert">
                  {uploadError}
                </p>
              ) : null}
              {uploadJobsBlock}
            </>
          </ManageAccordionPanel>

          <ManageAccordionPanel
            panelId="export"
            title="데이터셋 버전 · 분할 ·보내기"
            open={openManageAccordion === 'export'}
            onToggle={toggleManageAccordion}
          >
            <DatasetExportPanel projectId={id} />
          </ManageAccordionPanel>

          <ManageAccordionPanel
            panelId="members"
            title="멤버"
            open={openManageAccordion === 'members'}
            onToggle={toggleManageAccordion}
          >
            {membersError ? <p className="banner banner--error">{membersError}</p> : null}
            {!members ? (
              <p className="muted">불러오는 중…</p>
            ) : (
              <ul className="member-list">
                {members.map((m) => (
                  <li key={m.user_id}>
                    <code>{m.email}</code>
                    <span className="muted"> · {m.role}</span>
                  </li>
                ))}
              </ul>
            )}
          </ManageAccordionPanel>

          <ManageAccordionPanel
            panelId="classes"
            title="클래스 관리"
            open={openManageAccordion === 'classes'}
            onToggle={toggleManageAccordion}
          >
            {classError ? <p className="banner banner--error">{classError}</p> : null}
            <p className="muted fine-muted" style={{ marginBottom: 8 }}>
              <span className="source-badge source-badge--auto" style={{ marginRight: 6 }}>AUTO</span>
              는 모델에서 가져온 클래스(비활성화만 가능).
              <span className="source-badge source-badge--manual" style={{ marginLeft: 8, marginRight: 6 }}>MANUAL</span>
              은 직접 추가(비활성화 또는 라벨이 없을 때 영구 삭제).
            </p>
            {classes && classes.length > 0 ? (
              <ul className="member-list">
                {classes.map((c) => (
                  <li key={c.id}>
                    {editingClass?.id === c.id ? (
                      <span className="form-inline">
                        <input
                          className="input-text"
                          value={editingClass.name}
                          onChange={(e) => setEditingClass({ ...editingClass, name: e.target.value })}
                        />
                        <input
                          type="color"
                          value={normalizeHexForPicker(editingClass.color)}
                          onChange={(e) => setEditingClass({ ...editingClass, color: e.target.value })}
                          title="색"
                          style={{ width: 36, height: 28, padding: 0, border: '1px solid var(--border, #ccc)' }}
                        />
                        <input
                          className="input-text"
                          placeholder="#색상코드"
                          value={editingClass.color}
                          onChange={(e) => setEditingClass({ ...editingClass, color: e.target.value })}
                          style={{ width: '120px' }}
                        />
                        <button
                          className="btn-primary"
                          onClick={() => void handlePatchClass(c.id, editingClass.name, editingClass.color)}
                        >
                          저장
                        </button>
                        <button className="btn-secondary" onClick={() => setEditingClass(null)}>
                          취소
                        </button>
                      </span>
                    ) : (
                      <span>
                        <code>[{c.export_index}]</code>{' '}
                        {c.color ? (
                          <span
                            style={{
                              display: 'inline-block',
                              width: 12,
                              height: 12,
                              background: c.color,
                              borderRadius: 2,
                              verticalAlign: 'middle',
                              marginRight: 4,
                            }}
                          />
                        ) : null}
                        {c.name}
                        <span
                          className={
                            c.model_class_id != null
                              ? 'source-badge source-badge--auto'
                              : 'source-badge source-badge--manual'
                          }
                          style={{ marginLeft: 6, verticalAlign: 'middle' }}
                          title={
                            c.model_class_id != null
                              ? '모델에서 가져온 클래스 (AUTO)'
                              : '직접 추가한 클래스 (MANUAL)'
                          }
                        >
                          {c.model_class_id != null ? 'AUTO' : 'MANUAL'}
                        </span>
                        {!c.is_active ? <span className="muted"> (비활성)</span> : null}
                        {c.is_active ? (
                          <>
                            <button
                              className="btn-secondary"
                              style={{ marginLeft: 8 }}
                              onClick={() => setEditingClass({ id: c.id, name: c.name, color: c.color ?? '' })}
                            >
                              수정
                            </button>
                            <button
                              className="btn-secondary"
                              style={{ marginLeft: 4 }}
                              title="라벨링 목록에서 숨깁니다. 데이터는 유지됩니다."
                              onClick={() => void handleDeleteClass(c.id)}
                            >
                              비활성화
                            </button>
                            {c.model_class_id == null ? (
                              <button
                                type="button"
                                className="btn-secondary"
                                style={{ marginLeft: 4 }}
                                title="DB에서 클래스 정의를 제거합니다. 해당 클래스 박스가 없을 때만 가능합니다."
                                onClick={() => void handlePurgeClass(c.id)}
                              >
                                삭제
                              </button>
                            ) : null}
                          </>
                        ) : (
                          <>
                            <button
                              className="btn-secondary"
                              style={{ marginLeft: 8 }}
                              onClick={() => void handleReactivateClass(c.id)}
                            >
                              다시 사용
                            </button>
                            {c.model_class_id == null ? (
                              <button
                                type="button"
                                className="btn-secondary"
                                style={{ marginLeft: 4 }}
                                title="비활성 클래스 행을 DB에서 제거합니다. 해당 클래스 박스가 없을 때만 가능합니다."
                                onClick={() => void handlePurgeClass(c.id)}
                              >
                                삭제
                              </button>
                            ) : null}
                          </>
                        )}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">클래스가 없습니다. 모델을 선택하거나 직접 추가하세요.</p>
            )}

            <form onSubmit={(e) => void handleAddClass(e)} className="form-stack form-inline" style={{ marginTop: 12 }}>
              <input
                className="input-text"
                placeholder="클래스 이름"
                value={newClassName}
                onChange={(e) => setNewClassName(e.target.value)}
              />
              <input
                type="color"
                value={normalizeHexForPicker(newClassColor)}
                onChange={(e) => setNewClassColor(e.target.value)}
                title="색"
                style={{ width: 36, height: 28, padding: 0, border: '1px solid var(--border, #ccc)' }}
              />
              <input
                className="input-text"
                placeholder="#색상코드 (선택)"
                value={newClassColor}
                onChange={(e) => setNewClassColor(e.target.value)}
                style={{ width: '140px' }}
              />
              <button type="submit" className="btn-primary" disabled={addClassBusy || !newClassName.trim()}>
                {addClassBusy ? '추가 중…' : '클래스 추가'}
              </button>
            </form>
          </ManageAccordionPanel>

          <ManageAccordionPanel
            panelId="invite"
            title="초대 링크 만들기"
            open={openManageAccordion === 'invite'}
            onToggle={toggleManageAccordion}
          >
            <p className="muted fine-muted">역할을 고르고 생성하면 토큰·URL이 한 번만 표시됩니다. (수동 공유)</p>
            <form onSubmit={(e) => void handleInvite(e)} className="form-stack form-inline">
              <label className="form-field form-field--inline">
                <span className="form-label">역할</span>
                <select
                  className="input-text"
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value as 'annotator' | 'reviewer')}
                >
                  <option value="annotator">annotator</option>
                  <option value="reviewer">reviewer</option>
                </select>
              </label>
              <button type="submit" className="btn-primary" disabled={inviteBusy}>
                {inviteBusy ? '생성 중…' : '링크 생성'}
              </button>
            </form>
            {inviteError ? (
              <p className="banner banner--error" role="alert">
                {inviteError}
              </p>
            ) : null}
            {lastInvite ? (
              <div className="invite-result">
                <p className="fine-muted">만료: {new Date(lastInvite.expires_at).toLocaleString()} · 10분 후 자동 만료</p>
                <label className="form-label">참여 URL — 이 링크를 복사해서 전달하세요</label>
                <pre className="code-block">{lastInvite.join_url}</pre>
              </div>
            ) : null}
          </ManageAccordionPanel>

          <ManageAccordionPanel
            panelId="delete"
            title="프로젝트 삭제"
            open={openManageAccordion === 'delete'}
            onToggle={toggleManageAccordion}
          >
            <p className="muted fine-muted">
              되돌릴 수 없습니다. 데이터베이스의 이미지·어노테이션과 객체 스토리지의 업로드 파일이 함께 삭제됩니다.
            </p>
            <form onSubmit={(e) => void handleDeleteProject(e)} className="form-stack">
              <label className="form-field">
                <span className="form-label">확인을 위해 프로젝트 이름을 정확히 입력하세요</span>
                <input
                  className="input-text"
                  value={deleteConfirmName}
                  onChange={(e) => setDeleteConfirmName(e.target.value)}
                  placeholder={detail.name}
                  autoComplete="off"
                />
              </label>
              <button
                type="submit"
                className="btn-danger"
                disabled={deleteProjectBusy || deleteConfirmName !== detail.name}
              >
                {deleteProjectBusy ? '삭제 중…' : '프로젝트 영구 삭제'}
              </button>
            </form>
            {deleteProjectError ? (
              <p className="banner banner--error" role="alert">
                {deleteProjectError}
              </p>
            ) : null}
          </ManageAccordionPanel>
        </>
      ) : (
        <section className="panel panel--spaced">
          <h2>{workUnitSectionTitle}</h2>
          <p className="muted fine-muted">
            {isReviewer && reviewerTab === 'review'
              ? '나에게 검토가 배정된 이미지가 있는 업로드 단위만 표시됩니다.'
              : isAnnotateWorkUnitSection ? (
                  <>
                    나에게 어노테이션이 할당된 업로드 단위만 표시됩니다. 썸네일은 내 할당 이미지 중 첫 장입니다.
                    {annotateListTotals != null ? (
                      <span className="annotator-upload-totals">
                        표시된 업로드 합계 —{' '}
                        <strong>총 할당 {annotateListTotals.assigned}장</strong>
                        {', '}
                        <strong>승인 {annotateListTotals.approved}장</strong>
                        {', '}
                        <strong>
                          작업 중·완료(Done)·반려 합 {annotateListTotals.tabUnion}장
                        </strong>
                        （검토 요청 이후·리뷰 배정 대기 장수는 제외）
                      </span>
                    ) : null}
                  </>
                )
              : isOwner && ownerTab === 'review'
                ? '업로드 단위별 검토 파이프라인(검토 중·승인·검토 요청·미배정) 요약입니다.'
                : '업로드 단위를 선택하면 상세·라벨링 화면으로 이동합니다.'}
          </p>
          {uploadJobsBlock}
        </section>
      )}

      <p className="fine-print muted">
        {isOwner
          ? '데이터 관리 탭에서는 아래 아코디언을 펼쳐 ZIP·버전/보내기·멤버·클래스·초대·삭제를 설정할 수 있습니다.'
          : '멤버·초대·모델 설정은 프로젝트 owner만 변경할 수 있습니다.'}
      </p>
    </div>
  )
}
