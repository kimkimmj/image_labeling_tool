import { apiJson } from './client'
import type {
  CreateInvitationResponse,
  MlModel,
  ProjectClass,
  ProjectDetail,
  ProjectMember,
  ProjectSummary,
} from '../types/projects'

export function fetchOwnedProjects(): Promise<ProjectSummary[]> {
  return apiJson<ProjectSummary[]>('/api/projects/owned')
}

export function fetchMemberProjects(): Promise<ProjectSummary[]> {
  return apiJson<ProjectSummary[]>('/api/projects/member')
}

export function createProject(body: { name: string; description?: string | null }): Promise<ProjectSummary> {
  return apiJson<ProjectSummary>('/api/projects/', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function fetchProject(projectId: number): Promise<ProjectDetail> {
  return apiJson<ProjectDetail>(`/api/projects/${projectId}`)
}

export function deleteProject(projectId: number, confirmName: string): Promise<void> {
  return apiJson<void>(`/api/projects/${projectId}`, {
    method: 'DELETE',
    body: JSON.stringify({ confirm_name: confirmName }),
  })
}

export function fetchProjectMembers(projectId: number): Promise<ProjectMember[]> {
  return apiJson<ProjectMember[]>(`/api/projects/${projectId}/members`)
}

export function createInvitation(
  projectId: number,
  role: 'annotator' | 'reviewer',
): Promise<CreateInvitationResponse> {
  return apiJson<CreateInvitationResponse>(`/api/projects/${projectId}/invitations`, {
    method: 'POST',
    body: JSON.stringify({ role }),
  })
}

export function acceptInvitation(token: string): Promise<ProjectDetail> {
  return apiJson<ProjectDetail>('/api/project-invitations/accept', {
    method: 'POST',
    body: JSON.stringify({ token }),
  })
}

export function fetchAvailableModels(projectId: number): Promise<MlModel[]> {
  return apiJson<MlModel[]>(`/api/projects/${projectId}/models`)
}

export function fetchSelectedModel(projectId: number): Promise<MlModel | null> {
  return apiJson<MlModel | null>(`/api/projects/${projectId}/model`)
}

export function selectModel(projectId: number, modelId: number): Promise<MlModel> {
  return apiJson<MlModel>(`/api/projects/${projectId}/model`, {
    method: 'PUT',
    body: JSON.stringify({ model_id: modelId }),
  })
}

export function fetchClasses(
  projectId: number,
  options?: { includeInactive?: boolean },
): Promise<ProjectClass[]> {
  const q =
    options?.includeInactive === true ? '?include_inactive=true' : ''
  return apiJson<ProjectClass[]>(`/api/projects/${projectId}/classes${q}`)
}

export function addClass(projectId: number, body: { name: string; color?: string | null }): Promise<ProjectClass> {
  return apiJson<ProjectClass>(`/api/projects/${projectId}/classes`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function patchClass(
  classId: number,
  body: { name?: string | null; color?: string | null; is_active?: boolean | null },
): Promise<ProjectClass> {
  return apiJson<ProjectClass>(`/api/classes/${classId}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

export function deleteClass(classId: number): Promise<ProjectClass> {
  return apiJson<ProjectClass>(`/api/classes/${classId}`, {
    method: 'DELETE',
  })
}

/** 수동 추가 클래스만(project_classes.model_class_id 없음). 어노테이션이 있으면 409. */
export function purgeClass(classId: number): Promise<void> {
  return apiJson<void>(`/api/classes/${classId}/permanent`, {
    method: 'DELETE',
  })
}
