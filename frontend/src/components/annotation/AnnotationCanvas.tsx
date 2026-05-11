/**
 * Konva 기반 어노테이션 캔버스 컴포넌트.
 *
 * 기능:
 * - 이미지 렌더링
 * - bbox 표시 (class 색상)
 * - bbox 선택, 이동, 리사이즈
 * - 빈 영역 드래그로 새 bbox 그리기
 * - 선택된 bbox Delete 키로 삭제
 */

import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Image as KonvaImage, Layer, Rect, Stage, Transformer } from 'react-konva'
import useImage from 'use-image'
import type { LocalBbox } from '../../types/uploads'
import type { ProjectClass } from '../../types/projects'
import { normalizeRect, normToStage } from './coordUtils'

interface Props {
  imageUrl: string
  bboxes: LocalBbox[]
  classes: ProjectClass[]
  selectedLocalId: string | null
  canEdit: boolean
  onSelect: (localId: string | null) => void
  onAdd: (partial: Omit<LocalBbox, 'localId' | 'isDirty' | 'isNew' | 'isDeleted'>) => void
  onUpdate: (localId: string, patch: Partial<Pick<LocalBbox, 'x' | 'y' | 'width' | 'height'>>) => void
  onDelete: (localId: string) => void
  activeClassId: number | null
  stageWidth: number
  stageHeight: number
}

function classColor(classes: ProjectClass[], classId: number): string {
  const pc = classes.find((c) => c.id === classId)
  return pc?.color ?? '#00BFFF'
}

const MIN_BOX_PX = 5

export default function AnnotationCanvas({
  imageUrl,
  bboxes,
  classes,
  selectedLocalId,
  canEdit,
  onSelect,
  onAdd,
  onUpdate,
  onDelete,
  activeClassId,
  stageWidth,
  stageHeight,
}: Props) {
  const [image] = useImage(imageUrl, 'anonymous')
  const transformerRef = useRef<any>(null)
  const shapeRefs = useRef<Record<string, any>>({})

  // 드래그로 새 bbox 그리기 상태
  const isDrawing = useRef(false)
  const drawStart = useRef<{ x: number; y: number } | null>(null)
  const [drawRect, setDrawRect] = useState<{ x: number; y: number; w: number; h: number } | null>(null)

  // Transformer를 선택된 shape에 연결
  useEffect(() => {
    if (!transformerRef.current) return
    if (selectedLocalId && shapeRefs.current[selectedLocalId]) {
      transformerRef.current.nodes([shapeRefs.current[selectedLocalId]])
    } else {
      transformerRef.current.nodes([])
    }
    transformerRef.current.getLayer()?.batchDraw()
  }, [selectedLocalId])

  // Delete 키 처리
  useEffect(() => {
    if (!canEdit) return
    const handler = (e: KeyboardEvent) => {
      if ((e.key === 'Delete' || e.key === 'Backspace') && selectedLocalId) {
        onDelete(selectedLocalId)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [canEdit, selectedLocalId, onDelete])

  const handleStageMouseDown = useCallback(
    (e: any) => {
      if (!canEdit) return
      const clickedOnEmpty = e.target === e.target.getStage()
      if (!clickedOnEmpty) return
      if (!activeClassId) return

      onSelect(null)
      isDrawing.current = true
      const pos = e.target.getStage().getPointerPosition()
      drawStart.current = pos
      setDrawRect({ x: pos.x, y: pos.y, w: 0, h: 0 })
    },
    [canEdit, activeClassId, onSelect],
  )

  const handleStageMouseMove = useCallback((e: any) => {
    if (!isDrawing.current || !drawStart.current) return
    const pos = e.target.getStage().getPointerPosition()
    setDrawRect({
      x: Math.min(drawStart.current.x, pos.x),
      y: Math.min(drawStart.current.y, pos.y),
      w: Math.abs(pos.x - drawStart.current.x),
      h: Math.abs(pos.y - drawStart.current.y),
    })
  }, [])

  const handleStageMouseUp = useCallback(
    (e: any) => {
      if (!isDrawing.current || !drawStart.current || !activeClassId) return
      isDrawing.current = false
      const pos = e.target.getStage()?.getPointerPosition() ?? drawStart.current

      if (Math.abs(pos.x - drawStart.current.x) < MIN_BOX_PX ||
          Math.abs(pos.y - drawStart.current.y) < MIN_BOX_PX) {
        setDrawRect(null)
        drawStart.current = null
        return
      }

      const norm = normalizeRect(
        drawStart.current.x, drawStart.current.y,
        pos.x, pos.y,
        stageWidth, stageHeight,
      )

      onAdd({
        serverId: undefined,
        class_id: activeClassId,
        x: norm.x,
        y: norm.y,
        width: norm.width,
        height: norm.height,
        source: 'manual',
      })

      setDrawRect(null)
      drawStart.current = null
    },
    [activeClassId, onAdd, stageWidth, stageHeight],
  )

  const visible = bboxes.filter((b) => !b.isDeleted)
  const drawPreviewColor =
    activeClassId != null ? classColor(classes, activeClassId) : '#808080'

  return (
    <Stage
      width={stageWidth}
      height={stageHeight}
      onMouseDown={handleStageMouseDown}
      onMouseMove={handleStageMouseMove}
      onMouseUp={handleStageMouseUp}
      style={{ cursor: canEdit && activeClassId ? 'crosshair' : 'default' }}
    >
      {/* 이미지 레이어 */}
      <Layer>
        {image && (
          <KonvaImage
            image={image}
            x={0}
            y={0}
            width={stageWidth}
            height={stageHeight}
            listening={false}
          />
        )}
      </Layer>

      {/* bbox 레이어 */}
      <Layer>
        {visible.map((bbox) => {
          const px = normToStage(bbox, stageWidth, stageHeight)
          const color = classColor(classes, bbox.class_id)
          const isSelected = bbox.localId === selectedLocalId

          return (
            <Rect
              key={bbox.localId}
              ref={(node) => {
                if (node) shapeRefs.current[bbox.localId] = node
                else delete shapeRefs.current[bbox.localId]
              }}
              x={px.x}
              y={px.y}
              width={px.width}
              height={px.height}
              stroke={color}
              strokeWidth={isSelected ? 2.5 : 1.5}
              fill={`${color}22`}
              dash={bbox.source === 'auto' ? [6, 3] : undefined}
              draggable={canEdit}
              onClick={(e) => {
                e.cancelBubble = true
                onSelect(bbox.localId)
              }}
              onTap={(e) => {
                e.cancelBubble = true
                onSelect(bbox.localId)
              }}
              onDragEnd={(e) => {
                const node = e.target
                const newPx = {
                  x: node.x(),
                  y: node.y(),
                  width: node.width() * node.scaleX(),
                  height: node.height() * node.scaleY(),
                }
                node.scaleX(1)
                node.scaleY(1)
                const norm = normToStage(newPx, 1 / stageWidth, 1 / stageHeight)
                // stageToNorm 대신 직접 계산
                const nx = Math.max(0, Math.min(1, newPx.x / stageWidth))
                const ny = Math.max(0, Math.min(1, newPx.y / stageHeight))
                const nw = Math.max(0.001, Math.min(1 - nx, newPx.width / stageWidth))
                const nh = Math.max(0.001, Math.min(1 - ny, newPx.height / stageHeight))
                onUpdate(bbox.localId, { x: nx, y: ny, width: nw, height: nh })
              }}
              onTransformEnd={(e) => {
                const node = e.target
                const scaleX = node.scaleX()
                const scaleY = node.scaleY()
                node.scaleX(1)
                node.scaleY(1)
                const newPx = {
                  x: node.x(),
                  y: node.y(),
                  width: Math.max(MIN_BOX_PX, node.width() * scaleX),
                  height: Math.max(MIN_BOX_PX, node.height() * scaleY),
                }
                const nx = Math.max(0, Math.min(1, newPx.x / stageWidth))
                const ny = Math.max(0, Math.min(1, newPx.y / stageHeight))
                const nw = Math.max(0.001, Math.min(1 - nx, newPx.width / stageWidth))
                const nh = Math.max(0.001, Math.min(1 - ny, newPx.height / stageHeight))
                onUpdate(bbox.localId, { x: nx, y: ny, width: nw, height: nh })
              }}
            />
          )
        })}

        {/* Transformer (리사이즈 핸들) */}
        <Transformer
          ref={transformerRef}
          rotateEnabled={false}
          keepRatio={false}
          boundBoxFunc={(oldBox, newBox) => {
            if (newBox.width < MIN_BOX_PX || newBox.height < MIN_BOX_PX) return oldBox
            return newBox
          }}
        />
      </Layer>

      {/* 새 bbox 그리는 중 미리보기 */}
      {drawRect && (
        <Layer listening={false}>
          <Rect
            x={drawRect.x}
            y={drawRect.y}
            width={drawRect.w}
            height={drawRect.h}
            stroke={drawPreviewColor}
            strokeWidth={1.5}
            dash={[4, 2]}
            fill={`${drawPreviewColor}22`}
          />
        </Layer>
      )}
    </Stage>
  )
}
