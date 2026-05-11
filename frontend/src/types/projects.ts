export type ProjectSummary = {
  id: number
  name: string
  description: string | null
  created_at: string
}

export type ProjectDetail = ProjectSummary & {
  my_role: string
}

export type ProjectMember = {
  user_id: number
  email: string
  role: string
  created_at: string
}

export type CreateInvitationResponse = {
  invitation_id: number
  token: string
  join_url: string
  expires_at: string
}

export type MlModel = {
  id: number
  name: string
  version: string | null
  framework: string
  file_path: string
  created_at: string
}

export type ProjectClass = {
  id: number
  project_id: number
  export_index: number
  name: string
  color: string | null
  is_active: boolean
  model_class_id: number | null
  created_at: string
}
