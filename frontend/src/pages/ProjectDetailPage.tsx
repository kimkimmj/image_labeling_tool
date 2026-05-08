import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import {
  createInvitation,
  fetchProject,
  fetchProjectMembers,
} from '../api/projects'
import type { ProjectDetail, ProjectMember } from '../types/projects'

export function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const id = projectId ? Number.parseInt(projectId, 10) : NaN

  const [detail, setDetail] = useState<ProjectDetail | null>(null)
  const [members, setMembers] = useState<ProjectMember[] | null>(null)
  const [membersError, setMembersError] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [inviteRole, setInviteRole] = useState<'annotator' | 'reviewer'>('annotator')
  const [inviteBusy, setInviteBusy] = useState(false)
  const [inviteError, setInviteError] = useState<string | null>(null)
  const [lastInvite, setLastInvite] = useState<{ token: string; join_url: string; expires_at: string } | null>(null)

  const loadDetail = useCallback(async () => {
    if (!Number.isFinite(id)) return
    setLoadError(null)
    try {
      const d = await fetchProject(id)
      setDetail(d)
      setMembers(null)
      setMembersError(null)
      setLastInvite(null)
      if (d.my_role === 'owner') {
        try {
          const m = await fetchProjectMembers(id)
          setMembers(m)
        } catch (e) {
          setMembersError(e instanceof Error ? e.message : '멤버 목록 실패')
        }
      }
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : '불러오기 실패')
      setDetail(null)
    }
  }, [id])

  useEffect(() => {
    void loadDetail()
  }, [loadDetail])

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault()
    if (!Number.isFinite(id)) return
    setInviteBusy(true)
    setLastInvite(null)
    setInviteError(null)
    try {
      const res = await createInvitation(id, inviteRole)
      setLastInvite({ token: res.token, join_url: res.join_url, expires_at: res.expires_at })
    } catch (err) {
      setLastInvite(null)
      setInviteError(err instanceof Error ? err.message : '초대 생성 실패')
    } finally {
      setInviteBusy(false)
    }
  }

  if (!Number.isFinite(id)) {
    return (
      <div className="page-projects">
        <p className="banner banner--error">잘못된 프로젝트 ID</p>
        <Link to="/projects" className="inline-link">
          목록으로
        </Link>
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="page-projects">
        <p className="banner banner--error">{loadError}</p>
        <Link to="/projects" className="inline-link">
          목록으로
        </Link>
      </div>
    )
  }

  if (!detail) {
    return (
      <div className="page-projects">
        <p className="muted">불러오는 중…</p>
      </div>
    )
  }

  const isOwner = detail.my_role === 'owner'

  return (
    <div className="page-projects">
      <header className="page-home__header">
        <div>
          <p className="eyebrow">프로젝트 #{detail.id}</p>
          <h1>{detail.name}</h1>
          <p className="muted home-lead">
            내 역할: <strong>{detail.my_role}</strong>
          </p>
          {detail.description ? <p className="muted">{detail.description}</p> : null}
        </div>
        <Link to="/projects" className="btn-secondary">
          목록으로
        </Link>
      </header>

      <section className="panel panel--spaced">
        <h2>정보</h2>
        <dl className="account-dl">
          <dt>생성 시각</dt>
          <dd>{new Date(detail.created_at).toLocaleString()}</dd>
        </dl>
      </section>

      {isOwner ? (
        <>
          <section className="panel panel--spaced">
            <h2>멤버</h2>
            {membersError ? <p className="banner banner--error">{membersError}</p> : null}
            {!members ? (
              <p className="muted">불러오는 중…</p>
            ) : (
              <ul className="member-list">
                {members.map((m) => (
                  <li key={m.user_id}>
                    <code>{m.email}</code>
                    <span className="muted"> · {m.role}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="panel panel--spaced">
            <h2>초대 링크 만들기</h2>
            <p className="muted fine-muted">역할을 고르고 생성하면 토큰·URL이 한 번만 표시됩니다. (수동 공유)</p>
            <form onSubmit={(e) => void handleInvite(e)} className="form-stack form-inline">
              <label className="form-field form-field--inline">
                <span className="form-label">역할</span>
                <select
                  className="input-text"
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value as 'annotator' | 'reviewer')}
                >
                  <option value="annotator">annotator</option>
                  <option value="reviewer">reviewer</option>
                </select>
              </label>
              <button type="submit" className="btn-primary" disabled={inviteBusy}>
                {inviteBusy ? '생성 중…' : '링크 생성'}
              </button>
            </form>
            {inviteError ? (
              <p className="banner banner--error" role="alert">
                {inviteError}
              </p>
            ) : null}
            {lastInvite ? (
              <div className="invite-result">
                <p className="fine-muted">만료: {new Date(lastInvite.expires_at).toLocaleString()} · 10분 후 자동 만료</p>
                <label className="form-label">참여 URL — 이 링크를 복사해서 전달하세요</label>
                <pre className="code-block">{lastInvite.join_url}</pre>
              </div>
            ) : null}
          </section>
        </>
      ) : null}

      <p className="fine-print muted">
        참여자는 이 화면에서 멤버·초대를 볼 수 없습니다. 초대 링크는 owner에게 받으세요.
      </p>
    </div>
  )
}
