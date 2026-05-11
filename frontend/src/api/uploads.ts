import { apiJson } from './client'
import type {
  Annotation,
  AnnotationListResponse,
  AnnotationPatchRequest,
  AnnotationPutRequest,
  Assignment,
  AssignmentSummary,
  MyAssignmentItem,
  UploadImage,
  UploadJob,
} from '../types/uploads'

/** owner 프로젝트 탭(?mode=annotate|review) 참여 시 백엔드 필터 */
export type ParticipantScopeParam = false | 'annotate' | 'review'

function appendParticipantQuery(url: string, scope: ParticipantScopeParam): string {
  if (scope === false) return url
  const q = `for_participant=true&participant_scope=${encodeURIComponent(scope)}`
  return url.includes('?') ? `${url}&${q}` : `${url}?${q}`
}

// ------------------------------------------------------------------
// Upload jobs
// ------------------------------------------------------------------

export function fetchUploadJobs(
  projectId: number,
  scope?: 'all' | 'annotate' | 'review',
): Promise<UploadJob[]> {
  const q = scope != null ? `?scope=${encodeURIComponent(scope)}` : ''
  return apiJson<UploadJob[]>(`/api/projects/${projectId}/upload-jobs${q}`)
}

export async function createUploadJob(
  projectId: number,
  file: File,
  options?: { modelId?: number | undefined },
): Promise<UploadJob> {
  const formData = new FormData()
  formData.append('zip_file', file)
  if (options?.modelId != null) {
    formData.append('model_id', String(options.modelId))
  }
  return apiJson<UploadJob>(`/api/projects/${projectId}/upload-jobs`, {
    method: 'POST',
    body: formData,
  })
}

export function deleteUploadJob(projectId: number, jobId: number): Promise<void> {
  return apiJson<void>(`/api/projects/${projectId}/upload-jobs/${jobId}`, {
    method: 'DELETE',
  })
}

export function fetchUploadJob(
  jobId: number,
  participantScope: ParticipantScopeParam = false,
): Promise<UploadJob> {
  return apiJson<UploadJob>(
    appendParticipantQuery(`/api/upload-jobs/${jobId}`, participantScope),
  )
}

export function fetchUploadJobImages(
  jobId: number,
  participantScope: ParticipantScopeParam = false,
): Promise<UploadImage[]> {
  return apiJson<UploadImage[]>(
    appendParticipantQuery(`/api/upload-jobs/${jobId}/images`, participantScope),
  )
}

// ------------------------------------------------------------------
// Image content
// ------------------------------------------------------------------

export function getImageContentUrl(
  imageId: number,
  participantScope: ParticipantScopeParam = false,
): string {
  return appendParticipantQuery(`/api/images/${imageId}/content`, participantScope)
}

// ------------------------------------------------------------------
// Annotations — GET
// ------------------------------------------------------------------

export async function fetchImageAnnotations(
  imageId: number,
  participantScope: ParticipantScopeParam = false,
): Promise<Annotation[]> {
  const res = await apiJson<AnnotationListResponse | Annotation[]>(
    appendParticipantQuery(`/api/images/${imageId}/annotations`, participantScope),
  )
  if (Array.isArray(res)) return res
  return res.annotations ?? []
}

// ------------------------------------------------------------------
// Annotations — PUT (전체 교체, CVAT PUT /annotations 패턴)
// ------------------------------------------------------------------

export async function putAnnotations(
  imageId: number,
  body: AnnotationPutRequest,
  participantScope: ParticipantScopeParam = false,
): Promise<Annotation[]> {
  const res = await apiJson<AnnotationListResponse>(
    appendParticipantQuery(`/api/images/${imageId}/annotations`, participantScope),
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  )
  return res.annotations
}

// ------------------------------------------------------------------
// Annotations — PATCH (증분 저장, CVAT PATCH ?action= 패턴)
// ------------------------------------------------------------------

export async function patchAnnotations(
  imageId: number,
  action: 'create' | 'update' | 'delete',
  body: AnnotationPatchRequest,
  participantScope: ParticipantScopeParam = false,
): Promise<Annotation[]> {
  const base = `/api/images/${imageId}/annotations?action=${action}`
  const res = await apiJson<AnnotationListResponse>(
    appendParticipantQuery(base, participantScope),
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  )
  return res.annotations
}

// ------------------------------------------------------------------
// Assignments
// ------------------------------------------------------------------

export function fetchMyAssignments(): Promise<MyAssignmentItem[]> {
  return apiJson<MyAssignmentItem[]>('/api/assignments/me')
}

export function fetchAssignment(assignmentId: number): Promise<Assignment> {
  return apiJson<Assignment>(`/api/assignments/${assignmentId}`)
}

export function fetchImageAssignment(
  imageId: number,
  participantScope: ParticipantScopeParam = false,
): Promise<Assignment> {
  return apiJson<Assignment>(
    appendParticipantQuery(`/api/images/${imageId}/assignment`, participantScope),
  )
}

export function transitionAssignmentStatus(
  assignmentId: number,
  status: 'in_progress' | 'done' | 'approved' | 'reverted',
  reason?: string,
  participantScope: ParticipantScopeParam = false,
): Promise<Assignment> {
  return apiJson<Assignment>(
    appendParticipantQuery(`/api/assignments/${assignmentId}/status`, participantScope),
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status, reason }),
    },
  )
}

export function requestReview(jobId: number): Promise<{ transitioned: number }> {
  return apiJson<{ transitioned: number }>(`/api/upload-jobs/${jobId}/request-review`, {
    method: 'POST',
  })
}

// ------------------------------------------------------------------
// Owner: Assignment management
// ------------------------------------------------------------------

export function fetchAssignmentSummary(jobId: number): Promise<AssignmentSummary> {
  return apiJson<AssignmentSummary>(`/api/upload-jobs/${jobId}/assignment-summary`)
}

export function assignAnnotator(
  jobId: number,
  userId: number,
  count: number,
): Promise<{ assigned: number }> {
  return apiJson<{ assigned: number }>(`/api/upload-jobs/${jobId}/assignments/annotate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, count }),
  })
}

export function recallAnnotator(
  jobId: number,
  userId: number,
  count: number,
): Promise<{ recalled: number }> {
  return apiJson<{ recalled: number }>(`/api/upload-jobs/${jobId}/assignments/recall-annotate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, count }),
  })
}

export function assignReviewer(
  jobId: number,
  reviewerId: number,
  count: number,
): Promise<{ assigned: number }> {
  return apiJson<{ assigned: number }>(`/api/upload-jobs/${jobId}/assignments/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reviewer_id: reviewerId, count }),
  })
}

export function recallReviewer(
  jobId: number,
  reviewerId: number,
  count: number,
): Promise<{ recalled: number }> {
  return apiJson<{ recalled: number }>(`/api/upload-jobs/${jobId}/assignments/recall-review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reviewer_id: reviewerId, count }),
  })
}

export type BulkApproveReviewScope = 'submitted_unassigned' | 'include_review_assigned'

export function bulkApproveReviewQueue(
  jobId: number,
  scope: BulkApproveReviewScope,
): Promise<{ approved: number }> {
  return apiJson<{ approved: number }>(
    `/api/upload-jobs/${jobId}/assignments/bulk-approve-review-queue`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scope }),
    },
  )
}
