import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { acceptInvitation } from '../api/projects'

export function JoinPage() {
  const [params] = useSearchParams()
  const tokenFromUrl = params.get('token') ?? ''

  const [token, setToken] = useState(tokenFromUrl)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState<{ id: number; name: string; my_role: string } | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setToken(tokenFromUrl)
  }, [tokenFromUrl])

  const submit = useCallback(async () => {
    const t = token.trim()
    if (!t) {
      setError('토큰을 입력하거나 URL에 ?token= 을 넣으세요.')
      return
    }
    setBusy(true)
    setError(null)
    setDone(null)
    try {
      const d = await acceptInvitation(t)
      setDone({ id: d.id, name: d.name, my_role: d.my_role })
    } catch (e) {
      setError(e instanceof Error ? e.message : '수락 실패')
    } finally {
      setBusy(false)
    }
  }, [token])

  return (
    <div className="page-projects">
      <header className="page-home__header">
        <div>
          <p className="eyebrow">초대</p>
          <h1>프로젝트 참여</h1>
          <p className="muted home-lead">
            owner가 준 링크로 들어오면 토큰이 채워집니다. 로그인된 상태에서 수락하세요.
          </p>
        </div>
        <Link to="/projects" className="btn-secondary">
          프로젝트 목록
        </Link>
      </header>

      {done ? (
        <section className="panel panel--spaced banner banner--ok">
          <h2>참여 완료</h2>
          <p>
            <strong>{done.name}</strong> · 내 역할: <code>{done.my_role}</code>
          </p>
          <Link className="inline-link" to={`/projects/${done.id}`}>
            프로젝트 열기 →
          </Link>
        </section>
      ) : (
        <section className="panel panel--spaced">
          <label className="form-field">
            <span className="form-label">초대 토큰</span>
            <textarea
              className="input-text input-text--area"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              rows={3}
              placeholder="URL의 token= 뒤 값 또는 통째로 붙여넣기"
            />
          </label>
          {error ? (
            <p className="banner banner--error" role="alert">
              {error}
            </p>
          ) : null}
          <button type="button" className="btn-primary" disabled={busy} onClick={() => void submit()}>
            {busy ? '처리 중…' : '초대 수락'}
          </button>
        </section>
      )}
    </div>
  )
}
