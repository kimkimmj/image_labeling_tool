import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  createProject,
  deleteProject,
  fetchMemberProjects,
  fetchOwnedProjects,
} from '../api/projects'
import type { ProjectSummary } from '../types/projects'

export function ProjectsPage() {
  const [owned, setOwned] = useState<ProjectSummary[] | null>(null)
  const [member, setMember] = useState<ProjectSummary[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [createName, setCreateName] = useState('')
  const [createDesc, setCreateDesc] = useState('')
  const [creating, setCreating] = useState(false)

  const [ownedDeleteTarget, setOwnedDeleteTarget] = useState<{ id: number; name: string } | null>(null)
  const [ownedDeleteConfirmName, setOwnedDeleteConfirmName] = useState('')
  const [ownedDeleteBusy, setOwnedDeleteBusy] = useState(false)
  const [ownedDeleteError, setOwnedDeleteError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [o, m] = await Promise.all([fetchOwnedProjects(), fetchMemberProjects()])
      setOwned(o)
      setMember(m)
    } catch (e) {
      setError(e instanceof Error ? e.message : '목록을 불러오지 못했습니다.')
      setOwned([])
      setMember([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  async function handleDeleteOwnedProject(e: React.FormEvent) {
    e.preventDefault()
    if (!ownedDeleteTarget || ownedDeleteConfirmName !== ownedDeleteTarget.name) return
    setOwnedDeleteBusy(true)
    setOwnedDeleteError(null)
    try {
      await deleteProject(ownedDeleteTarget.id, ownedDeleteConfirmName)
      setOwnedDeleteTarget(null)
      setOwnedDeleteConfirmName('')
      await load()
    } catch (err) {
      const raw = err instanceof Error ? err.message : '삭제 실패'
      let msg = raw
      if (raw.includes('project_delete_name_mismatch')) msg = '프로젝트 이름이 일치하지 않습니다.'
      else if (raw.includes('project_has_active_uploads'))
        msg = '처리 중인 ZIP 업로드가 있을 때는 삭제할 수 없습니다. 완료·실패 후 다시 시도하세요.'
      else if (raw.includes('project_storage_purge_failed') || raw.startsWith('HTTP 503'))
        msg = '파일 저장소 정리에 실패했습니다. 잠시 후 다시 시도하세요. 프로젝트 데이터는 그대로입니다.'
      setOwnedDeleteError(msg)
    } finally {
      setOwnedDeleteBusy(false)
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    if (!createName.trim()) return
    setCreating(true)
    setError(null)
    try {
      await createProject({
        name: createName.trim(),
        description: createDesc.trim() || null,
      })
      setCreateName('')
      setCreateDesc('')
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : '생성 실패')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="page-projects">
      <header className="page-home__header">
        <div>
          <p className="eyebrow">STEP 1.1</p>
          <h1>프로젝트</h1>
          <p className="muted home-lead">
            내가 소유한 프로젝트와 참여 중인 프로젝트를 구분해 봅니다. 소유자만 멤버 목록·초대 링크를
            만들 수 있습니다.
          </p>
        </div>
        <Link to="/" className="btn-secondary">
          홈으로
        </Link>
      </header>

      {error ? (
        <p className="banner banner--error" role="alert">
          {error}
        </p>
      ) : null}

      <section className="panel panel--spaced">
        <h2>새 프로젝트</h2>
        <form onSubmit={(e) => void handleCreate(e)} className="form-stack">
          <label className="form-field">
            <span className="form-label">이름</span>
            <input
              className="input-text"
              value={createName}
              onChange={(e) => setCreateName(e.target.value)}
              placeholder="예: 검증용 데이터셋"
              required
            />
          </label>
          <label className="form-field">
            <span className="form-label">설명 (선택)</span>
            <textarea
              className="input-text input-text--area"
              value={createDesc}
              onChange={(e) => setCreateDesc(e.target.value)}
              rows={2}
            />
          </label>
          <button type="submit" className="btn-primary" disabled={creating}>
            {creating ? '생성 중…' : '프로젝트 만들기 (나 = owner)'}
          </button>
        </form>
      </section>

      {loading ? (
        <p className="muted">불러오는 중…</p>
      ) : (
        <>
          <section className="panel panel--spaced">
            <div className="projects-section-head">
              <h2>내가 owner인 프로젝트</h2>
              <Link to="/models" className="btn-secondary">
                모델 관리
              </Link>
            </div>
            <p className="muted fine-muted">초대 링크 생성·멤버 보기는 상세에서.</p>
            <ul className="link-list">
              {owned?.length === 0 ? (
                <li className="muted">없음</li>
              ) : (
                owned?.map((p) => (
                  <li key={p.id}>
                    <div
                      style={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        alignItems: 'center',
                        gap: '8px',
                      }}
                    >
                      <Link to={`/projects/${p.id}`} className="inline-link">
                        {p.name}
                      </Link>
                      <span className="muted list-meta"> · #{p.id}</span>
                      <button
                        type="button"
                        className="btn-secondary"
                        onClick={() => {
                          setOwnedDeleteError(null)
                          if (ownedDeleteTarget?.id === p.id) {
                            setOwnedDeleteTarget(null)
                            setOwnedDeleteConfirmName('')
                          } else {
                            setOwnedDeleteTarget({ id: p.id, name: p.name })
                            setOwnedDeleteConfirmName('')
                          }
                        }}
                      >
                        {ownedDeleteTarget?.id === p.id ? '취소' : '삭제'}
                      </button>
                    </div>
                    {ownedDeleteTarget?.id === p.id ? (
                      <form
                        onSubmit={(e) => void handleDeleteOwnedProject(e)}
                        className="form-stack"
                        style={{ marginTop: 10 }}
                      >
                        <label className="form-field">
                          <span className="form-label fine-muted">
                            «{p.name}» 이름을 입력하면 영구 삭제됩니다
                          </span>
                          <input
                            className="input-text"
                            value={ownedDeleteConfirmName}
                            onChange={(e) => setOwnedDeleteConfirmName(e.target.value)}
                            placeholder={p.name}
                            autoComplete="off"
                          />
                        </label>
                        <button
                          type="submit"
                          className="btn-danger"
                          disabled={ownedDeleteBusy || ownedDeleteConfirmName !== p.name}
                        >
                          {ownedDeleteBusy ? '삭제 중…' : '영구 삭제'}
                        </button>
                        {ownedDeleteError ? (
                          <p className="banner banner--error" role="alert">
                            {ownedDeleteError}
                          </p>
                        ) : null}
                      </form>
                    ) : null}
                  </li>
                ))
              )}
            </ul>
          </section>

          <section className="panel panel--spaced">
            <h2>멤버로 참여 중 (owner 아님)</h2>
            <ul className="link-list">
              {member?.length === 0 ? (
                <li className="muted">없음</li>
              ) : (
                member?.map((p) => (
                  <li key={p.id}>
                    <Link to={`/projects/${p.id}`} className="inline-link">
                      {p.name}
                    </Link>
                    <span className="muted list-meta"> · #{p.id}</span>
                  </li>
                ))
              )}
            </ul>
          </section>
        </>
      )}

      <p className="fine-print muted">
        초대 받은 경우 로그인 후{' '}
        <Link className="inline-link" to="/join">
          /join?token=…
        </Link>
        로 참여하세요.
      </p>
    </div>
  )
}
