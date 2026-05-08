/** `/api` 프록시 + 세션 쿠키. CSRF 완화용으로 브라우저가 Origin/Referer를 붙입니다. */
export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const hasBody = init?.body !== undefined && init?.body !== null
  const method = (init?.method ?? 'GET').toUpperCase()
  const headers: HeadersInit = {
    Accept: 'application/json',
    ...(method !== 'GET' && method !== 'HEAD' && hasBody ? { 'Content-Type': 'application/json' } : {}),
    ...((init?.headers as Record<string, string> | undefined) ?? {}),
  }

  const res = await fetch(path, { ...init, credentials: 'include', headers })

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
