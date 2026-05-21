/**
 * 우측 사이드바: 프로젝트 클래스 목록 + 선택 bbox 속성
 */

import { useLayoutEffect, useRef } from 'react'
import type { ProjectClass } from '../../types/projects'
import type { LocalBbox } from '../../types/uploads'

interface Props {
  classes: ProjectClass[]
  activeClassId: number | null
  onSelectClass: (classId: number) => void
  selectedBbox: LocalBbox | null
  onChangeClass: (classId: number) => void
  onDelete: () => void
  canEdit: boolean
  bboxes: LocalBbox[]
  onSelectBbox: (localId: string | null) => void
}

function BboxSelectedPanel({
  selectedBbox,
  activeClasses,
  canEdit,
  onChangeClass,
  onDelete,
  className,
}: {
  selectedBbox: LocalBbox
  activeClasses: ProjectClass[]
  canEdit: boolean
  onChangeClass: (classId: number) => void
  onDelete: () => void
  className?: string
}) {
  return (
    <div className={className ? `bbox-selected-panel ${className}` : 'bbox-selected-panel'}>
      <h5 className="bbox-selected-panel__title">선택된 bbox</h5>
      <dl className="bbox-props">
        <dt>클래스</dt>
        <dd>
          {canEdit ? (
            <select
              value={selectedBbox.class_id}
              onChange={(e) => onChangeClass(Number(e.target.value))}
              className="bbox-class-select"
            >
              {activeClasses.map((pc) => (
                <option key={pc.id} value={pc.id}>
                  {pc.name}
                </option>
              ))}
            </select>
          ) : (
            activeClasses.find((c) => c.id === selectedBbox.class_id)?.name ?? selectedBbox.class_id
          )}
        </dd>
        <dt>출처</dt>
        <dd>
          <span className={`source-badge source-badge--${selectedBbox.source}`}>
            {selectedBbox.source}
          </span>
        </dd>
        <dt>x</dt>
        <dd>{selectedBbox.x.toFixed(4)}</dd>
        <dt>y</dt>
        <dd>{selectedBbox.y.toFixed(4)}</dd>
        <dt>w</dt>
        <dd>{selectedBbox.width.toFixed(4)}</dd>
        <dt>h</dt>
        <dd>{selectedBbox.height.toFixed(4)}</dd>
      </dl>
      {canEdit && (
        <button type="button" className="btn btn-danger btn-sm" onClick={onDelete}>
          삭제
        </button>
      )}
    </div>
  )
}

export default function ClassSidebar({
  classes,
  activeClassId,
  onSelectClass,
  selectedBbox,
  onChangeClass,
  onDelete,
  canEdit,
  bboxes,
  onSelectBbox,
}: Props) {
  const activeClasses = classes.filter((c) => c.is_active)

  // 활성 클래스에 속한 살아있는 bbox 목록
  const classBboxes = activeClassId
    ? bboxes.filter((b) => !b.isDeleted && b.class_id === activeClassId)
    : []

  const activeClass = activeClasses.find((c) => c.id === activeClassId)

  const selectionInVisibleList =
    selectedBbox != null &&
    classBboxes.some((b) => b.localId === selectedBbox.localId)

  const bboxRowRefs = useRef<Map<string, HTMLLIElement | null>>(new Map())
  const detachedPanelWrapRef = useRef<HTMLDivElement | null>(null)

  useLayoutEffect(() => {
    const id = selectedBbox?.localId
    if (!id) return
    window.requestAnimationFrame(() => {
      if (selectionInVisibleList) {
        const row = bboxRowRefs.current.get(id)
        row?.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'auto' })
      } else {
        detachedPanelWrapRef.current?.scrollIntoView({
          block: 'nearest',
          inline: 'nearest',
          behavior: 'auto',
        })
      }
    })
  }, [selectedBbox?.localId, selectionInVisibleList])

  return (
    <aside className="annotation-sidebar">
      {/* 클래스 목록 */}
      <section className="sidebar-section">
        <h4 className="sidebar-title">클래스</h4>
        <ul className="class-list">
          {activeClasses.map((pc) => (
            <li
              key={pc.id}
              className={`class-item${activeClassId === pc.id ? ' class-item--active' : ''}`}
              onClick={() => canEdit && onSelectClass(pc.id)}
              title={`ID: ${pc.id}`}
            >
              <span
                className="class-color-dot"
                style={{ background: pc.color ?? '#00BFFF' }}
              />
              <span className="class-name">{pc.name}</span>
            </li>
          ))}
          {activeClasses.length === 0 && (
            <li className="class-item class-item--empty">클래스가 없습니다</li>
          )}
        </ul>
      </section>

      {/* 활성 클래스의 bbox 목록 */}
      {activeClassId && (
        <section className="sidebar-section">
          <h4 className="sidebar-title">
            {activeClass?.name ?? '?'}
            <span className="sidebar-badge">{classBboxes.length}</span>
          </h4>
          {classBboxes.length === 0 ? (
            <p className="sidebar-empty">bbox 없음</p>
          ) : (
            <ul className="bbox-list">
              {classBboxes.map((b, idx) => (
                <li
                  key={b.localId}
                  className="bbox-list-row"
                  ref={(el) => {
                    if (el) bboxRowRefs.current.set(b.localId, el)
                    else bboxRowRefs.current.delete(b.localId)
                  }}
                >
                  <div
                    role="button"
                    tabIndex={0}
                    className={`bbox-list-item${selectedBbox?.localId === b.localId ? ' bbox-list-item--active' : ''}`}
                    onClick={() => onSelectBbox(b.localId)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        onSelectBbox(b.localId)
                      }
                    }}
                  >
                    <span className="bbox-list-idx">#{idx + 1}</span>
                    <span className="bbox-list-coords">
                      ({b.x.toFixed(2)}, {b.y.toFixed(2)})
                    </span>
                    <span className="bbox-list-size">
                      {b.width.toFixed(2)}×{b.height.toFixed(2)}
                    </span>
                    {b.source === 'auto' && (
                      <span className="source-badge source-badge--auto">auto</span>
                    )}
                  </div>
                  {selectedBbox?.localId === b.localId && (
                    <BboxSelectedPanel
                      selectedBbox={selectedBbox}
                      activeClasses={activeClasses}
                      canEdit={canEdit}
                      onChangeClass={onChangeClass}
                      onDelete={onDelete}
                    />
                  )}
                </li>
              ))}
            </ul>
          )}
          {selectedBbox && !selectionInVisibleList ? (
            <div ref={detachedPanelWrapRef} className="bbox-selected-panel-anchor">
              <BboxSelectedPanel
                className="bbox-selected-panel--detached"
                selectedBbox={selectedBbox}
                activeClasses={activeClasses}
                canEdit={canEdit}
                onChangeClass={onChangeClass}
                onDelete={onDelete}
              />
            </div>
          ) : null}
        </section>
      )}
    </aside>
  )
}
