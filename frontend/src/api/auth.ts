import type { Me } from '../types/api'

const jsonAccept = { Accept: 'application/json' } as const

/** 세션 쿠키 기준 현재 사용자. 미로그인이면 `null`. */
export async function fetchMe(): Promise<Me | null> {
  const res = await fetch('/api/me', {
    credentials: 'include',
    headers: jsonAccept,
  })
  if (res.status === 401) return null
  if (!res.ok) throw new Error(`로그인 정보를 불러오지 못했습니다 (${res.status})`)
  return res.json() as Promise<Me>
}

/** Redis 세션 삭제 + 세션 쿠키 제거. */
export async function logoutSession(): Promise<void> {
  const res = await fetch('/api/auth/logout', {
    method: 'POST',
    credentials: 'include',
    headers: jsonAccept,
  })
  if (!res.ok) throw new Error(`로그아웃에 실패했습니다 (${res.status})`)
}

/** 같은 출처 `/api` 프록시로 IdP 로그인 시작 (전체 페이지 이동). */
export function startOAuthLogin(provider: 'google' | 'naver' | 'kakao'): void {
  window.location.assign(`/api/auth/oauth/${provider}/login`)
}
