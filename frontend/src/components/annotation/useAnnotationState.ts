/**
 * 어노테이션 로컬 상태 관리 hook.
 *
 * CVAT AnnotationsSaver 의 "초기 스냅샷 + created/updated/deleted 분리" 패턴을 단순화했다.
 * - created : serverId 없음
 * - updated : serverId 있고 isDirty
 * - deleted : isDeleted
 */

import { useCallback, useRef, useState } from 'react'
import { v4 as uuidv4 } from 'uuid'
import type { Annotation, LocalBbox } from '../../types/uploads'

export function annotationToLocal(a: Annotation): LocalBbox {
  return {
    localId: uuidv4(),
    serverId: a.id,
    class_id: a.class_id,
    x: a.x,
    y: a.y,
    width: a.width,
    height: a.height,
    source: a.source,
    isDirty: false,
    isNew: false,
    isDeleted: false,
  }
}

export function useAnnotationState() {
  const [bboxes, setBboxes] = useState<LocalBbox[]>([])
  const [selectedLocalId, setSelectedLocalId] = useState<string | null>(null)

  /** 서버에서 받은 annotation 목록으로 초기화 */
  const load = useCallback((anns: Annotation[]) => {
    setBboxes(anns.map(annotationToLocal))
    setSelectedLocalId(null)
  }, [])

  /** 새 bbox 추가 */
  const add = useCallback((partial: Omit<LocalBbox, 'localId' | 'isDirty' | 'isNew' | 'isDeleted'>) => {
    const item: LocalBbox = {
      ...partial,
      localId: uuidv4(),
      isDirty: false,
      isNew: true,
      isDeleted: false,
    }
    setBboxes((prev) => [...prev, item])
    setSelectedLocalId(item.localId)
    return item.localId
  }, [])

  /** bbox 좌표 / class 수정 */
  const update = useCallback((localId: string, patch: Partial<Pick<LocalBbox, 'x' | 'y' | 'width' | 'height' | 'class_id'>>) => {
    setBboxes((prev) =>
      prev.map((b) =>
        b.localId === localId
          ? { ...b, ...patch, isDirty: !b.isNew, source: 'manual' as const }
          : b,
      ),
    )
  }, [])

  /** bbox soft delete */
  const remove = useCallback((localId: string) => {
    setBboxes((prev) =>
      prev.map((b) =>
        b.localId === localId ? { ...b, isDeleted: true } : b,
      ),
    )
    setSelectedLocalId((prev) => (prev === localId ? null : prev))
  }, [])

  /** 변경사항 없는지 확인 */
  const isDirty = bboxes.some((b) => b.isNew || b.isDirty || b.isDeleted)

  /** PATCH 증분 저장 payload 계산 */
  const computeDiff = useCallback(() => {
    const created = bboxes.filter((b) => b.isNew && !b.isDeleted)
    const updated = bboxes.filter((b) => b.isDirty && !b.isNew && !b.isDeleted)
    const deleted = bboxes.filter((b) => b.isDeleted && !b.isNew && b.serverId != null)
    return { created, updated, deleted }
  }, [bboxes])

  /** PUT payload — 현재 살아있는 모든 bbox */
  const computeAll = useCallback(() => {
    return bboxes.filter((b) => !b.isDeleted)
  }, [bboxes])

  /** 저장 후 서버 응답으로 상태 갱신 */
  const syncFromServer = useCallback((serverAnns: Annotation[]) => {
    setBboxes(serverAnns.map(annotationToLocal))
    setSelectedLocalId(null)
  }, [])

  return {
    bboxes,
    selectedLocalId,
    setSelectedLocalId,
    load,
    add,
    update,
    remove,
    isDirty,
    computeDiff,
    computeAll,
    syncFromServer,
  }
}
