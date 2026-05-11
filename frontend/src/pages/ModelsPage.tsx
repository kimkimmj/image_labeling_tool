import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { fetchMlModels, uploadMlModel } from '../api/mlModels'
import type { MlModel } from '../types/projects'

export function ModelsPage() {
  const [models, setModels] = useState<MlModel[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [uploadBusy, setUploadBusy] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    fetchMlModels()
      .then(setModels)
      .catch((e) => setLoadError(e instanceof Error ? e.message : '목록 로드 실패'))
  }, [])

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault()
    const file = fileRef.current?.files?.[0]
    if (!file) return
    setUploadBusy(true)
    setUploadError(null)
    setUploadSuccess(null)
    try {
      const model = await uploadMlModel(file)
      setModels((prev) => [model, ...prev])
      setUploadSuccess(`"${model.name}" 업로드 완료`)
      if (fileRef.current) fileRef.current.value = ''
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : '업로드 실패')
    } finally {
      setUploadBusy(false)
    }
  }

  return (
    <div className="page-projects">
      <header className="page-home__header">
        <div>
          <p className="eyebrow">내 계정</p>
          <h1>ML 모델 관리</h1>
          <p className="muted home-lead">
            Detection .pt 파일을 업로드하면 내가 소유한 프로젝트에서 자동 라벨링에 사용할 수 있습니다.
          </p>
        </div>
        <Link to="/" className="btn-secondary">
          홈으로
        </Link>
      </header>

      <section className="panel panel--spaced">
        <h2>모델 업로드</h2>
        <form onSubmit={(e) => void handleUpload(e)} className="form-stack form-inline">
          <input ref={fileRef} type="file" accept=".pt" className="input-text" />
          <button type="submit" className="btn-primary" disabled={uploadBusy}>
            {uploadBusy ? '업로드 중…' : '업로드'}
          </button>
        </form>
        {uploadError ? (
          <p className="banner banner--error" role="alert">
            {uploadError}
          </p>
        ) : null}
        {uploadSuccess ? (
          <p className="banner banner--success" role="status">
            {uploadSuccess}
          </p>
        ) : null}
      </section>

      <section className="panel panel--spaced">
        <h2>내 모델</h2>
        {loadError ? <p className="banner banner--error">{loadError}</p> : null}
        {models.length === 0 ? (
          <p className="muted">등록된 모델이 없습니다.</p>
        ) : (
          <ul className="member-list">
            {models.map((m) => (
              <li key={m.id}>
                <strong>{m.name}</strong>
                <span className="muted"> · {m.framework}</span>
                {m.version ? <span className="muted"> · v{m.version}</span> : null}
                <span className="muted fine-muted"> · {new Date(m.created_at).toLocaleString()}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
