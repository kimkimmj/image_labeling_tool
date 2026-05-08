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
