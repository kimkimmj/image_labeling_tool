import { apiJson } from './client'
import type {
  CreateInvitationResponse,
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
