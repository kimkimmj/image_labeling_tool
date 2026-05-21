/** `/api` 프록시 + 세션 쿠키. CSRF 완화용으로 브라우저가 Origin/Referer를 붙입니다. */
function getApiBase(): string {
  const v = import.meta.env.VITE_API_BASE_URL
  if (typeof v !== 'string' || !v.trim()) return ''
  return v.trim().replace(/\/$/, '')
}

/**
 * API 요청 전체 URL.
 * `VITE_API_BASE_URL` 이 비어 있으면 `/api/...` 상대 경로(nginx·Vite 프록시·같은 출처).
 * 원격 API(크로스 오리진)면 `http://host:8000` 처럼 베이스만 지정.
 */
export function apiUrl(path: string): string {
  if (!path.startsWith('/')) {
    throw new Error(`apiUrl: path must start with /, got: ${path}`)
  }
  const base = getApiBase()
  return base ? `${base}${path}` : path
}

export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const hasBody = init?.body !== undefined && init?.body !== null
  const isFormData = init?.body instanceof FormData
  const method = (init?.method ?? 'GET').toUpperCase()
  const headers: HeadersInit = {
    Accept: 'application/json',
    // FormData 전송 시 브라우저가 Content-Type(boundary 포함)을 자동 설정하므로 직접 지정하지 않는다.
    ...(method !== 'GET' && method !== 'HEAD' && hasBody && !isFormData ? { 'Content-Type': 'application/json' } : {}),
    ...((init?.headers as Record<string, string> | undefined) ?? {}),
  }

  const res = await fetch(apiUrl(path), { ...init, credentials: 'include', headers })

  if (res.ok) {
    if (res.status === 204) return undefined as T
    return (await res.json()) as T
  }

  let msg = `HTTP ${res.status}`
  try {
    const body: unknown = await res.json()
    if (body && typeof body === 'object' && 'detail' in body) {
      const d = (body as { detail: unknown }).detail
      if (typeof d === 'string') msg = d
      else if (Array.isArray(d))
        msg = d.map((x) => (typeof x === 'object' && x && 'msg' in x ? String((x as { msg: string }).msg) : String(x))).join(', ')
    }
  } catch {
    /* ignore */
  }
  throw new Error(msg)
}
