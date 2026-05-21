/**
 * 라벨링 에디터 페이지
 *
 * 라우트: /images/:imageId/label?project_id=&upload_job_id=
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { fetchClasses } from '../api/projects'
import {
  fetchImageAnnotations,
  fetchImageAssignment,
  fetchUploadJobImages,
  getImageContentUrl,
  patchAnnotations,
  transitionAssignmentStatus,
  type ParticipantScopeParam,
} from '../api/uploads'
import AnnotationCanvas from '../components/annotation/AnnotationCanvas'
import ClassSidebar from '../components/annotation/ClassSidebar'
import AnnotationToolbar from '../components/annotation/AnnotationToolbar'
import ImageListPanel from '../components/annotation/ImageListPanel'
import { useAnnotationState } from '../components/annotation/useAnnotationState'
import type { Assignment, AssignmentStatus, UploadImage } from '../types/uploads'
import type { ProjectClass } from '../types/projects'

const CANVAS_MAX_W = 900
const CANVAS_MAX_H = 640
const AUTO_SAVE_DELAY_MS = 2000

/** 검토 반려 시 서버 `revert_reason` — 추후 사용자 입력 UX로 교체 예정 */
const REVIEW_REJECT_REASON_DEFAULT = '반려합니다'

export function AnnotationPage() {
  const { imageId } = useParams<{ imageId: string }>()
  const location = useLocation()   // React Router — URL 변경에 반응
  const navigate = useNavigate()
  const imgId = Number(imageId)

  // useLocation 기반 쿼리 파라미터 파싱 (client-side nav 후에도 최신값)
  const searchParams = useMemo(
    () => new URLSearchParams(location.search),
    [location.search],
  )
  const projectId = Number(searchParams.get('project_id')) || 0
  const uploadJobId = Number(searchParams.get('upload_job_id')) || 0
  const modeParam = searchParams.get('mode')
  /** 프로젝트 어노테이션/리뷰 탭에서 온 owner — API에 participant_scope 전달 */
  const participantScope: ParticipantScopeParam =
    modeParam === 'annotate' ? 'annotate' : modeParam === 'review' ? 'review' : false

  const uploadDetailReturnUrl = useMemo(() => {
    const base = `/projects/${projectId}/uploads/${uploadJobId}`
    if (participantScope === 'annotate') return `${base}?mode=annotate`
    if (participantScope === 'review') return `${base}?mode=review`
    return base
  }, [projectId, uploadJobId, participantScope])

  // 업로드 단위 이미지 목록
  const [jobImages, setJobImages] = useState<UploadImage[]>([])
  const [jobImagesLoading, setJobImagesLoading] = useState(false)
  const currentIndex = jobImages.findIndex((i) => i.id === imgId)

  // 캔버스 크기
  const [stageSize, setStageSize] = useState({ w: CANVAS_MAX_W, h: CANVAS_MAX_H })

  // 클래스 목록
  const [classes, setClasses] = useState<ProjectClass[]>([])
  const [activeClassId, setActiveClassId] = useState<number | null>(null)

  // assignment
  const [assignment, setAssignment] = useState<Assignment | null>(null)

  // 상태
  const [loading, setLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [autoSaveStatus, setAutoSaveStatus] = useState<'idle' | 'pending' | 'saving' | 'saved'>('idle')
  const [error, setError] = useState<string | null>(null)

  const autoSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const {
    bboxes, selectedLocalId, setSelectedLocalId,
    load, add, update, remove,
    isDirty, computeDiff, syncFromServer,
  } = useAnnotationState()

  // ------------------------------------------------------------------
  // 이미지 목록 로드
  // ------------------------------------------------------------------

  useEffect(() => {
    if (!uploadJobId) return
    setJobImagesLoading(true)
    fetchUploadJobImages(uploadJobId, participantScope)
      .then(setJobImages)
      .catch(() => {})
      .finally(() => setJobImagesLoading(false))
  }, [uploadJobId, participantScope])

  // ------------------------------------------------------------------
  // 이미지별 annotation + assignment 로드
  // ------------------------------------------------------------------

  useEffect(() => {
    if (!imgId) return
    setLoading(true)
    setAssignment(null)
    setAutoSaveStatus('idle')
    if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current)

    // assignment를 먼저 가져온 뒤 어노테이션 로드
    fetchImageAssignment(imgId, participantScope)
      .then(async (a) => {
        let current = a
        // 어노테이션(참여) 모드에서만 assigned → in_progress 자동 전환 (리뷰 큐에서는 하지 않음)
        if (
          participantScope !== 'review' &&
          a.status === 'assigned' &&
          a.assigned_to != null
        ) {
          try {
            current = await transitionAssignmentStatus(a.id, 'in_progress', undefined, participantScope)
          } catch {
            current = a
          }
        }
        setAssignment(current)
        const anns = await fetchImageAnnotations(imgId, participantScope)
        load(anns)
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }, [imgId, participantScope])

  // 이미지 크기 → 캔버스 크기
  useEffect(() => {
    if (!imgId) return
    const img = new window.Image()
    img.src = getImageContentUrl(imgId, participantScope)
    img.onload = () => {
      const ratio = img.naturalWidth / img.naturalHeight
      let w = Math.min(CANVAS_MAX_W, img.naturalWidth)
      let h = w / ratio
      if (h > CANVAS_MAX_H) { h = CANVAS_MAX_H; w = h * ratio }
      setStageSize({ w: Math.round(w), h: Math.round(h) })
    }
  }, [imgId, participantScope])

  // 클래스 목록 로드
  useEffect(() => {
    if (!projectId) return
    fetchClasses(projectId)
      .then((cls) => {
        setClasses(cls)
        const first = cls.find((c) => c.is_active)
        if (first) setActiveClassId((prev) => prev ?? first.id)
      })
      .catch(() => {})
  }, [projectId])

  // 프로젝트 상세에서 색·클래스를 고친 뒤 탭 복귀 시 목록 갱신
  useEffect(() => {
    if (!projectId) return
    const onVis = () => {
      if (document.visibilityState !== 'visible') return
      fetchClasses(projectId)
        .then(setClasses)
        .catch(() => {})
    }
    document.addEventListener('visibilitychange', onVis)
    return () => document.removeEventListener('visibilitychange', onVis)
  }, [projectId])

  const handleSelectBbox = useCallback(
    (localId: string | null) => {
      setSelectedLocalId(localId)
      if (localId != null) {
        const b = bboxes.find((x) => x.localId === localId && !x.isDeleted)
        if (b) setActiveClassId(b.class_id)
      }
    },
    [bboxes, setSelectedLocalId],
  )

  // ------------------------------------------------------------------
  // 저장 핵심 로직 (PATCH 증분)
  // ------------------------------------------------------------------

  const savePatch = useCallback(async (): Promise<boolean> => {
    const { created, updated, deleted } = computeDiff()
    if (!created.length && !updated.length && !deleted.length) return true
    try {
      if (created.length > 0) {
        await patchAnnotations(imgId, 'create', {
          items: created.map((b) => ({
            class_id: b.class_id, x: b.x, y: b.y, width: b.width, height: b.height,
          })),
        }, participantScope)
      }
      if (updated.length > 0) {
        await patchAnnotations(imgId, 'update', {
          items: updated.map((b) => ({
            id: b.serverId!,
            class_id: b.class_id, x: b.x, y: b.y, width: b.width, height: b.height,
          })),
        }, participantScope)
      }
      if (deleted.length > 0) {
        await patchAnnotations(imgId, 'delete', {
          items: deleted.map((b) => ({ id: b.serverId! })),
        }, participantScope)
      }
      const latest = await fetchImageAnnotations(imgId, participantScope)
      syncFromServer(latest)
      return true
    } catch {
      return false
    }
  }, [imgId, computeDiff, syncFromServer, participantScope])

  // ------------------------------------------------------------------
  // 자동 저장 (변경 후 2초)
  // ------------------------------------------------------------------

  useEffect(() => {
    if (!isDirty || !assignment?.can_edit) return
    setAutoSaveStatus('pending')
    if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current)
    autoSaveTimer.current = setTimeout(async () => {
      setAutoSaveStatus('saving')
      const ok = await savePatch()
      setAutoSaveStatus(ok ? 'saved' : 'idle')
      // 2초 후 'saved' 표시 제거
      setTimeout(() => setAutoSaveStatus('idle'), 2000)
    }, AUTO_SAVE_DELAY_MS)
    return () => {
      if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current)
    }
  }, [bboxes, isDirty, assignment?.can_edit, savePatch])

  const handleSubmit = useCallback(async () => {
    if (!assignment) return
    setIsSaving(true)
    try {
      const updated = await transitionAssignmentStatus(assignment.id, 'done', undefined, participantScope)
      setAssignment(updated)
      setJobImages((prev) =>
        prev.map((img) =>
          img.id === imgId ? { ...img, assignment_status: 'done' as const } : img,
        ),
      )
    } catch (e) {
      alert('완료 처리 실패: ' + String(e))
    } finally {
      setIsSaving(false)
    }
  }, [assignment, imgId, participantScope])

  const handleRevert = useCallback(async () => {
    if (!assignment) return
    setIsSaving(true)
    try {
      const updated = await transitionAssignmentStatus(assignment.id, 'in_progress', undefined, participantScope)
      setAssignment(updated)
      setJobImages((prev) =>
        prev.map((img) =>
          img.id === imgId ? { ...img, assignment_status: 'in_progress' as const } : img,
        ),
      )
    } catch (e) {
      alert('수정 전환 실패: ' + String(e))
    } finally {
      setIsSaving(false)
    }
  }, [assignment, imgId, participantScope])

  const handleApprove = useCallback(async () => {
    if (!assignment) return
    setIsSaving(true)
    try {
      const updated = await transitionAssignmentStatus(assignment.id, 'approved', undefined, participantScope)
      setAssignment(updated)
      setJobImages((prev) =>
        prev.map((img) =>
          img.id === imgId ? { ...img, assignment_status: 'approved' as const } : img,
        ),
      )
    } catch (e) {
      alert('승인 실패: ' + String(e))
    } finally {
      setIsSaving(false)
    }
  }, [assignment, imgId, participantScope])

  const handleRejectReview = useCallback(async () => {
    if (!assignment) return
    setIsSaving(true)
    try {
      const updated = await transitionAssignmentStatus(
        assignment.id,
        'reverted',
        REVIEW_REJECT_REASON_DEFAULT,
        participantScope,
      )
      setAssignment(updated)
      setJobImages((prev) =>
        prev.map((img) =>
          img.id === imgId
            ? { ...img, assignment_status: updated.status as AssignmentStatus }
            : img,
        ),
      )
      /** 리뷰 큐에서 빠져 더 이상 review 스코프로 이 이미지에 접근할 수 없음 → 목록으로 복귀 */
      if (participantScope === 'review') {
        navigate(uploadDetailReturnUrl, { replace: true })
      }
    } catch (e) {
      alert('반려 실패: ' + String(e))
    } finally {
      setIsSaving(false)
    }
  }, [assignment, imgId, participantScope, navigate, uploadDetailReturnUrl])

  // ------------------------------------------------------------------
  // 네비게이션
  // ------------------------------------------------------------------

  const goToImage = useCallback(
    (targetId: number) => {
      navigate(`/images/${targetId}/label?${searchParams.toString()}`)
    },
    [navigate, searchParams],
  )

  const canGoPrev = currentIndex > 0
  const canGoNext = currentIndex >= 0 && currentIndex < jobImages.length - 1

  const handlePrev = useCallback(async () => {
    if (!canGoPrev) return
    if (isDirty) await savePatch()
    goToImage(jobImages[currentIndex - 1].id)
  }, [canGoPrev, isDirty, savePatch, goToImage, jobImages, currentIndex])

  const handleNext = useCallback(async () => {
    if (!canGoNext) return
    if (isDirty) await savePatch()
    goToImage(jobImages[currentIndex + 1].id)
  }, [canGoNext, isDirty, savePatch, goToImage, jobImages, currentIndex])

  // ------------------------------------------------------------------
  // 키보드 단축키
  // ------------------------------------------------------------------

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // 입력 필드에 포커스가 있으면 무시
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return
      if (e.key === 'ArrowLeft') handlePrev()
      if (e.key === 'ArrowRight') handleNext()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [handlePrev, handleNext])

  // ------------------------------------------------------------------
  // 선택된 bbox
  // ------------------------------------------------------------------

  const selectedBbox = bboxes.find((b) => b.localId === selectedLocalId && !b.isDeleted) ?? null

  const handleChangeClass = useCallback(
    (classId: number) => {
      if (!selectedLocalId) return
      update(selectedLocalId, { class_id: classId } as any)
    },
    [selectedLocalId, update],
  )

  const canEdit = Boolean(assignment?.can_edit || assignment?.review_mode)
  const reviewMode = assignment?.review_mode ?? false

  const currentImageName =
    jobImages.find((i) => i.id === imgId)?.file_name ?? `image-${imgId}`

  const navLabel = !jobImagesLoading && jobImages.length > 0 && currentIndex >= 0
    ? `${currentIndex + 1} / ${jobImages.length}`
    : jobImagesLoading ? '…' : null

  // ------------------------------------------------------------------
  // 렌더
  // ------------------------------------------------------------------

  if (loading) {
    return (
      <div className="page-shell page-shell--center">
        <p className="muted">로딩 중…</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="page-shell page-shell--center">
        <p className="error">{error}</p>
        <button className="btn btn-secondary-dark" onClick={() => navigate(-1)}>뒤로</button>
      </div>
    )
  }

  return (
    <div className="annotation-page">
      <AnnotationToolbar
        assignmentStatus={assignment?.status ?? null}
        canEdit={canEdit}
        reviewMode={reviewMode}
        isDirty={isDirty}
        isSaving={isSaving}
        autoSaveStatus={autoSaveStatus}
        onSubmit={handleSubmit}
        onRevert={handleRevert}
        onApprove={handleApprove}
        onRejectReview={handleRejectReview}
        onBack={() => navigate(uploadDetailReturnUrl)}
        imageName={currentImageName}
        navLabel={navLabel}
        canGoPrev={canGoPrev}
        canGoNext={canGoNext}
        onPrev={handlePrev}
        onNext={handleNext}
      />

      <div className="annotation-body">
        {/* 좌측 이미지 목록 패널 */}
        <ImageListPanel
          images={jobImages}
          currentImageId={imgId}
          projectId={projectId}
          jobId={uploadJobId}
          loading={jobImagesLoading}
          labelQueryExtras={
            participantScope === 'annotate'
              ? '&mode=annotate'
              : participantScope === 'review'
                ? '&mode=review'
                : ''
          }
          participantScope={participantScope}
        />

        <main className="annotation-canvas-wrap">
          <AnnotationCanvas
            imageUrl={getImageContentUrl(imgId, participantScope)}
            bboxes={bboxes}
            classes={classes}
            selectedLocalId={selectedLocalId}
            canEdit={canEdit}
            onSelect={handleSelectBbox}
            onAdd={add}
            onUpdate={update}
            onDelete={remove}
            activeClassId={activeClassId}
            stageWidth={stageSize.w}
            stageHeight={stageSize.h}
          />
        </main>

        <ClassSidebar
          classes={classes}
          activeClassId={activeClassId}
          onSelectClass={setActiveClassId}
          selectedBbox={selectedBbox}
          onChangeClass={handleChangeClass}
          onDelete={() => selectedLocalId && remove(selectedLocalId)}
          canEdit={canEdit}
          bboxes={bboxes}
          onSelectBbox={handleSelectBbox}
        />
      </div>
    </div>
  )
}
