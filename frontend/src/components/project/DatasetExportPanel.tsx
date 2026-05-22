import { useCallback, useEffect, useState } from 'react'

import {
  createDatasetSplit,
  createDatasetVersion,
  createExportJob,
  fetchDatasetSplits,
  fetchDatasetVersions,
  fetchExportJob,
} from '../../api/datasets'
import type { DatasetSplit, DatasetVersionSummary, ExportFormat, ExportJob } from '../../types/datasets'

function exportStatusLabel(status: string): string {
  const map: Record<string, string> = {
    pending: '대기',
    processing: '생성 중',
    completed: '완료',
    failed: '실패',
  }
  return map[status] ?? status
}

type Props = {
  projectId: number
}

export function DatasetExportPanel({ projectId }: Props) {
  const [versions, setVersions] = useState<DatasetVersionSummary[] | null>(null)
  const [versionsError, setVersionsError] = useState<string | null>(null)
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null)

  const [versionName, setVersionName] = useState('')
  const [versionDesc, setVersionDesc] = useState('')
  const [versionBusy, setVersionBusy] = useState(false)

  const [splits, setSplits] = useState<DatasetSplit[] | null>(null)
  const [splitsError, setSplitsError] = useState<string | null>(null)
  const [selectedSplitId, setSelectedSplitId] = useState<number | null>(null)

  const [splitName, setSplitName] = useState('')
  const [trainRatio, setTrainRatio] = useState(70)
  const [valRatio, setValRatio] = useState(20)
  const [testRatio, setTestRatio] = useState(10)
  const [randomSeed, setRandomSeed] = useState(0)
  const [splitBusy, setSplitBusy] = useState(false)

  const [exportFormat, setExportFormat] = useState<ExportFormat>('yolo')
  const [exportBusy, setExportBusy] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)
  const [activeExport, setActiveExport] = useState<ExportJob | null>(null)

  const loadVersions = useCallback(async () => {
    setVersionsError(null)
    try {
      const list = await fetchDatasetVersions(projectId)
      setVersions(list)
      if (list.length > 0) {
        setSelectedVersionId((cur) => cur ?? list[0].id)
      }
    } catch (e) {
      setVersionsError(e instanceof Error ? e.message : '버전 목록을 불러오지 못했습니다.')
      setVersions(null)
    }
  }, [projectId])

  const loadSplits = useCallback(async (versionId: number) => {
    setSplitsError(null)
    try {
      const list = await fetchDatasetSplits(projectId, versionId)
      setSplits(list)
      if (list.length > 0) {
        setSelectedSplitId((cur) => (cur != null && list.some((s) => s.id === cur) ? cur : list[0].id))
      } else {
        setSelectedSplitId(null)
      }
    } catch (e) {
      setSplitsError(e instanceof Error ? e.message : '분할 목록을 불러오지 못했습니다.')
      setSplits(null)
    }
  }, [projectId])

  useEffect(() => {
    void loadVersions()
  }, [loadVersions])

  useEffect(() => {
    if (selectedVersionId == null) {
      setSplits(null)
      setSelectedSplitId(null)
      return
    }
    void loadSplits(selectedVersionId)
  }, [selectedVersionId, loadSplits])

  useEffect(() => {
    if (!activeExport || activeExport.status === 'completed' || activeExport.status === 'failed') {
      return
    }
    const timer = window.setInterval(() => {
      void fetchExportJob(projectId, activeExport.id)
        .then(setActiveExport)
        .catch(() => {
          /* ignore poll errors */
        })
    }, 2000)
    return () => window.clearInterval(timer)
  }, [activeExport, projectId])

  async function handleCreateVersion(e: React.FormEvent) {
    e.preventDefault()
    const name = versionName.trim()
    if (!name) return
    setVersionBusy(true)
    setVersionsError(null)
    try {
      const created = await createDatasetVersion(projectId, {
        name,
        description: versionDesc.trim() || null,
      })
      setVersionName('')
      setVersionDesc('')
      await loadVersions()
      setSelectedVersionId(created.id)
    } catch (err) {
      setVersionsError(err instanceof Error ? err.message : '버전 생성 실패')
    } finally {
      setVersionBusy(false)
    }
  }

  async function handleCreateSplit(e: React.FormEvent) {
    e.preventDefault()
    if (selectedVersionId == null) return
    const name = splitName.trim()
    if (!name) return
    const total = trainRatio + valRatio + testRatio
    if (Math.abs(total - 100) > 0.01) {
      setSplitsError('train + val + test 비율 합은 100이어야 합니다.')
      return
    }
    setSplitBusy(true)
    setSplitsError(null)
    try {
      const created = await createDatasetSplit(projectId, {
        dataset_version_id: selectedVersionId,
        name,
        train_ratio: trainRatio,
        val_ratio: valRatio,
        test_ratio: testRatio,
        random_seed: randomSeed,
      })
      setSplitName('')
      await loadSplits(selectedVersionId)
      setSelectedSplitId(created.id)
    } catch (err) {
      setSplitsError(err instanceof Error ? err.message : '분할 생성 실패')
    } finally {
      setSplitBusy(false)
    }
  }

  async function handleStartExport() {
    if (selectedVersionId == null || selectedSplitId == null) return
    setExportBusy(true)
    setExportError(null)
    setActiveExport(null)
    try {
      const job = await createExportJob(projectId, {
        dataset_version_id: selectedVersionId,
        dataset_split_id: selectedSplitId,
        format: exportFormat,
      })
      setActiveExport(job)
    } catch (err) {
      setExportError(err instanceof Error ? err.message : '보내기 요청 실패')
    } finally {
      setExportBusy(false)
    }
  }

  const selectedVersion = versions?.find((v) => v.id === selectedVersionId)
  const selectedSplit = splits?.find((s) => s.id === selectedSplitId)

  return (
    <div className="dataset-export-panel">
      <p className="muted fine-muted" style={{ marginBottom: 12 }}>
        승인된 이미지만 모아 <strong>데이터셋 버전(고정)</strong>을 만든 뒤, train/val/test 비율로 분할하고 YOLO 또는
        COCO ZIP을 다운로드합니다.
      </p>

      {versionsError ? (
        <p className="banner banner--error" role="alert">
          {versionsError}
        </p>
      ) : null}

      <h3 className="dataset-export-panel__step">1. 버전 고정 (Freeze)</h3>
      <form onSubmit={(e) => void handleCreateVersion(e)} className="form-stack form-inline" style={{ marginBottom: 12 }}>
        <input
          className="input-text"
          placeholder="버전 이름 (예: v1.0-approved)"
          value={versionName}
          onChange={(e) => setVersionName(e.target.value)}
          style={{ minWidth: 200 }}
        />
        <input
          className="input-text"
          placeholder="설명 (선택)"
          value={versionDesc}
          onChange={(e) => setVersionDesc(e.target.value)}
          style={{ minWidth: 160 }}
        />
        <button type="submit" className="btn-primary" disabled={versionBusy || !versionName.trim()}>
          {versionBusy ? '생성 중…' : '버전 생성'}
        </button>
      </form>

      {!versions ? (
        <p className="muted">버전 목록 불러오는 중…</p>
      ) : versions.length === 0 ? (
        <p className="muted">아직 버전이 없습니다. 승인된 라벨이 있어야 항목이 포함됩니다.</p>
      ) : (
        <label className="form-field">
          <span className="form-label">버전 선택</span>
          <select
            className="input-text"
            value={selectedVersionId ?? ''}
            onChange={(e) => setSelectedVersionId(Number.parseInt(e.target.value, 10))}
          >
            {versions.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name} — {v.item_count}장 · {new Date(v.created_at).toLocaleString()}
              </option>
            ))}
          </select>
        </label>
      )}

      {selectedVersion ? (
        <p className="muted fine-muted">
          선택 버전: <strong>{selectedVersion.item_count}</strong>장 (승인 스냅샷)
        </p>
      ) : null}

      <hr className="dataset-export-panel__hr" />

      <h3 className="dataset-export-panel__step">2. Train / Val / Test 분할</h3>
      {selectedVersionId == null ? (
        <p className="muted">먼저 버전을 선택하세요.</p>
      ) : (
        <>
          {splitsError ? (
            <p className="banner banner--error" role="alert">
              {splitsError}
            </p>
          ) : null}
          <form onSubmit={(e) => void handleCreateSplit(e)} className="form-stack" style={{ marginBottom: 12 }}>
            <div className="form-inline" style={{ flexWrap: 'wrap', gap: 8 }}>
              <input
                className="input-text"
                placeholder="분할 이름 (예: seed42-70-20-10)"
                value={splitName}
                onChange={(e) => setSplitName(e.target.value)}
                style={{ minWidth: 200 }}
              />
              <label className="form-field form-field--inline">
                <span className="form-label">Train %</span>
                <input
                  type="number"
                  className="input-text"
                  min={0}
                  max={100}
                  value={trainRatio}
                  onChange={(e) => setTrainRatio(Number(e.target.value))}
                  style={{ width: 72 }}
                />
              </label>
              <label className="form-field form-field--inline">
                <span className="form-label">Val %</span>
                <input
                  type="number"
                  className="input-text"
                  min={0}
                  max={100}
                  value={valRatio}
                  onChange={(e) => setValRatio(Number(e.target.value))}
                  style={{ width: 72 }}
                />
              </label>
              <label className="form-field form-field--inline">
                <span className="form-label">Test %</span>
                <input
                  type="number"
                  className="input-text"
                  min={0}
                  max={100}
                  value={testRatio}
                  onChange={(e) => setTestRatio(Number(e.target.value))}
                  style={{ width: 72 }}
                />
              </label>
              <label className="form-field form-field--inline">
                <span className="form-label">Seed</span>
                <input
                  type="number"
                  className="input-text"
                  value={randomSeed}
                  onChange={(e) => setRandomSeed(Number.parseInt(e.target.value, 10) || 0)}
                  style={{ width: 88 }}
                />
              </label>
              <button type="submit" className="btn-primary" disabled={splitBusy || !splitName.trim()}>
                {splitBusy ? '분할 중…' : '분할 생성'}
              </button>
            </div>
            <p className="muted fine-muted">합계: {trainRatio + valRatio + testRatio}% (100이어야 함)</p>
          </form>

          {!splits ? (
            <p className="muted">분할 목록 불러오는 중…</p>
          ) : splits.length === 0 ? (
            <p className="muted">이 버전에 대한 분할이 없습니다.</p>
          ) : (
            <label className="form-field">
              <span className="form-label">분할 선택</span>
              <select
                className="input-text"
                value={selectedSplitId ?? ''}
                onChange={(e) => setSelectedSplitId(Number.parseInt(e.target.value, 10))}
              >
                {splits.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} — train {s.train_count} / val {s.val_count} / test {s.test_count} (seed {s.random_seed})
                  </option>
                ))}
              </select>
            </label>
          )}
        </>
      )}

      <hr className="dataset-export-panel__hr" />

      <h3 className="dataset-export-panel__step">3.보내기 (ZIP)</h3>
      {selectedSplit ? (
        <p className="muted fine-muted">
          분할 통계: train <strong>{selectedSplit.train_count}</strong> · val{' '}
          <strong>{selectedSplit.val_count}</strong> · test <strong>{selectedSplit.test_count}</strong>
        </p>
      ) : null}

      <div className="form-inline" style={{ flexWrap: 'wrap', gap: 12, marginTop: 8 }}>
        <label className="form-field form-field--inline">
          <span className="form-label">포맷</span>
          <select
            className="input-text"
            value={exportFormat}
            onChange={(e) => setExportFormat(e.target.value as ExportFormat)}
          >
            <option value="yolo">YOLO (Ultralytics)</option>
            <option value="coco">COCO Detection</option>
          </select>
        </label>
        <button
          type="button"
          className="btn-primary"
          disabled={exportBusy || selectedVersionId == null || selectedSplitId == null}
          onClick={() => void handleStartExport()}
        >
          {exportBusy ? '요청 중…' : 'ZIP보내기 시작'}
        </button>
      </div>

      {exportError ? (
        <p className="banner banner--error" role="alert">
          {exportError}
        </p>
      ) : null}

      {activeExport ? (
        <div className="invite-result" style={{ marginTop: 12 }}>
          <p>
            Job #{activeExport.id} · {exportStatusLabel(activeExport.status)} · 포맷{' '}
            <strong>{activeExport.format.toUpperCase()}</strong>
          </p>
          {activeExport.status === 'processing' || activeExport.status === 'pending' ? (
            <p className="muted fine-muted">Celery 워커가 ZIP을 생성 중입니다. 잠시 후 새로고침됩니다.</p>
          ) : null}
          {activeExport.status === 'failed' && activeExport.error_message ? (
            <p className="banner banner--error">{activeExport.error_message}</p>
          ) : null}
          {activeExport.status === 'completed' && activeExport.download_url ? (
            <p>
              <a href={activeExport.download_url} className="btn-primary" download rel="noopener noreferrer">
                ZIP 다운로드
              </a>
            </p>
          ) : activeExport.status === 'completed' ? (
            <p className="muted">완료됨. 다운로드 URL을 불러오지 못했습니다. 상태를 다시 조회해 보세요.</p>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
