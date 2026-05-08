/** GET /api/me 응답 형태 (백엔드 Pydantic과 동일). */
export type Me = {
  id: number
  email: string
  created_at: string
}
