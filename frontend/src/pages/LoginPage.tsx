import { Navigate } from 'react-router-dom'

import { startOAuthLogin } from '../api/auth'
import { useAuth } from '../auth/AuthContext'

const providers = [
  { id: 'google' as const, label: 'Google로 계속하기', hint: 'OAuth 2.0 · PKCE' },
  { id: 'naver' as const, label: '네이버로 계속하기', hint: 'OAuth 2.0' },
  { id: 'kakao' as const, label: '카카오로 계속하기', hint: 'OAuth 2.0 · PKCE' },
]

export function LoginPage() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="page-login">
        <p className="muted">세션 확인 중…</p>
      </div>
    )
  }

  if (user) {
    return <Navigate to="/" replace />
  }

  return (
    <div className="page-login">
      <header className="page-login__header">
        <p className="eyebrow">Image Labeling Tool</p>
        <h1>로그인</h1>
        <p className="muted">
          소셜 계정으로 로그인하면 브라우저에 세션 쿠키가 저장됩니다. 개발 시 백엔드·Vite가 각각
          실행 중이어야 하며, IdP 콜백은 <code>/api/auth/oauth/…</code> 프록시를 통해 처리됩니다.
        </p>
      </header>

      <div className="oauth-stack" role="group" aria-label="OAuth 로그인">
        {providers.map((p) => (
          <button
            key={p.id}
            type="button"
            className={`oauth-btn oauth-btn--${p.id}`}
            onClick={() => startOAuthLogin(p.id)}
          >
            <span className="oauth-btn__label">{p.label}</span>
            <span className="oauth-btn__hint">{p.hint}</span>
          </button>
        ))}
      </div>

      <p className="fine-print muted">
        백엔드에서 해당 provider 클라이언트 ID·시크릿이 설정되어 있지 않으면 로그인 시작 시 503이
        반환될 수 있습니다.
      </p>
    </div>
  )
}
