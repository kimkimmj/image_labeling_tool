import { Link } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'

export function HomePage() {
  const { user, logout } = useAuth()

  return (
    <div className="page-home">
      <header className="page-home__header">
        <div>
          <p className="eyebrow">대시보드</p>
          <h1>Image Labeling Tool</h1>
          <p className="muted home-lead">
            로그인되었습니다. STEP 1에서는 사용자·OAuth 세션만 다루며, 프로젝트 등 다른 기능은 이후
            단계에서 연결합니다.
          </p>
        </div>
        <div className="page-home__actions">
          <span className="user-chip" title={user?.email}>
            {user?.email}
          </span>
          <button type="button" className="btn-secondary" onClick={() => void logout()}>
            로그아웃
          </button>
        </div>
      </header>

      <section className="panel">
        <h2>계정</h2>
        <dl className="account-dl">
          <dt>사용자 ID</dt>
          <dd>
            <code>{user?.id}</code>
          </dd>
          <dt>가입일</dt>
          <dd>{user?.created_at ? new Date(user.created_at).toLocaleString() : '—'}</dd>
        </dl>
      </section>

      <p className="muted fine-print">
        다른 계정으로 로그인하려면{' '}
        <Link to="/login" className="inline-link">
          로그인 페이지
        </Link>
        로 이동한 뒤 진행하세요 (먼저 로그아웃하는 것이 안전합니다).
      </p>
    </div>
  )
}
