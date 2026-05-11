/**
 * 좌표 변환 유틸리티
 *
 * 서버는 정규화 좌표 (0~1) 로 저장하고,
 * Konva 캔버스는 픽셀 좌표로 동작한다.
 *
 * 규칙:
 *   norm  = 정규화 좌표 (x, y, width, height) — YOLO top-left 기준
 *   stage = Konva Stage 위의 픽셀 좌표
 */

export interface NormBbox {
  x: number
  y: number
  width: number
  height: number
}

export interface StageBbox {
  x: number
  y: number
  width: number
  height: number
}

/** 정규화 → 픽셀 */
export function normToStage(norm: NormBbox, stageW: number, stageH: number): StageBbox {
  return {
    x: norm.x * stageW,
    y: norm.y * stageH,
    width: norm.width * stageW,
    height: norm.height * stageH,
  }
}

/** 픽셀 → 정규화 (0~1 클램프 포함) */
export function stageToNorm(stage: StageBbox, stageW: number, stageH: number): NormBbox {
  const x = Math.max(0, Math.min(1, stage.x / stageW))
  const y = Math.max(0, Math.min(1, stage.y / stageH))
  const w = Math.max(0.001, Math.min(1 - x, stage.width / stageW))
  const h = Math.max(0.001, Math.min(1 - y, stage.height / stageH))
  return { x, y, width: w, height: h }
}

/** 드래그 방향 무관하게 정규화 bbox 반환 (음수 width/height 교정) */
export function normalizeRect(
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  stageW: number,
  stageH: number,
): NormBbox {
  const minX = Math.min(x1, x2)
  const minY = Math.min(y1, y2)
  const maxX = Math.max(x1, x2)
  const maxY = Math.max(y1, y2)
  return stageToNorm(
    { x: minX, y: minY, width: maxX - minX, height: maxY - minY },
    stageW,
    stageH,
  )
}
