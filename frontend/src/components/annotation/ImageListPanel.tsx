/**
 * 에디터 좌측 이미지 목록 패널
 * - 어노: 전체 / 완료 / 작업 중 / 반려 탭
 * - 리뷰(?mode=review): 검토 큐만 평목록(탭 없음)
 */

import { useState } from 'react'
import { Link } from 'react-router-dom'
import { getImageContentUrl, type ParticipantScopeParam } from '../../api/uploads'
import type { AssignmentStatus, UploadImage } from '../../types/uploads'

type FilterKey = 'all' | 'in_progress' | 'done' | 'reverted'

const FILTER_LABELS: Record<FilterKey, string> = {
  all: '전체',
  in_progress: '진행',
  done: '완료',
  reverted: '반려',
}

const IN_PROGRESS_STATUSES: AssignmentStatus[] = ['assigned', 'in_progress']
/** 썸네일 테두리(검토·승인 단계 포함) */
const CARD_DONE_BORDER_STATUSES: AssignmentStatus[] = ['done', 'submitted', 'review_assigned', 'approved']

function isAnnotateAllTabStatus(s: AssignmentStatus | null | undefined): boolean {
  if (!s) return false
  if (IN_PROGRESS_STATUSES.includes(s)) return true
  if (s === 'done') return true
  return s === 'reverted'
}

function isReviewListItem(s: AssignmentStatus | null | undefined): boolean {
  return s === 'review_assigned' || s === 'submitted'
}

function filterImages(
  images: UploadImage[],
  filter: FilterKey,
  listScope: ParticipantScopeParam,
): UploadImage[] {
  if (listScope === 'review') {
    // 리뷰 스코프는 부모에서 전체 검토 큐만 넘기므로 사실상 사용하지 않음(평목록)
    return images.filter((i) => isReviewListItem(i.assignment_status))
  }
  if (filter === 'all') return images.filter((i) => isAnnotateAllTabStatus(i.assignment_status))
  if (filter === 'in_progress')
    return images.filter((i) => i.assignment_status && IN_PROGRESS_STATUSES.includes(i.assignment_status))
  if (filter === 'done') return images.filter((i) => i.assignment_status === 'done')
  return images.filter((i) => i.assignment_status === 'reverted')
}

function statusBorderClass(status: AssignmentStatus | undefined): string {
  if (!status) return ''
  if (CARD_DONE_BORDER_STATUSES.includes(status)) return 'img-panel-item--done'
  if (IN_PROGRESS_STATUSES.includes(status)) return 'img-panel-item--wip'
  if (status === 'reverted') return 'img-panel-item--reverted'
  return ''
}

interface Props {
  images: UploadImage[]
  currentImageId: number
  projectId: number
  jobId: number
  loading: boolean
  /** 라벨 에디터 링크에 붙일 추가 쿼리 (예: &mode=annotate) */
  labelQueryExtras?: string
  /** owner 참여(어노테이션/리뷰 탭) — 썸네일 원본 URL */
  participantScope?: ParticipantScopeParam
}

export default function ImageListPanel({
  images,
  currentImageId,
  projectId,
  jobId,
  loading,
  labelQueryExtras = '',
  participantScope = false,
}: Props) {
  const [filter, setFilter] = useState<FilterKey>('all')

  const isReviewPanel = participantScope === 'review'
  const filtered = isReviewPanel ? images : filterImages(images, filter, participantScope)

  const makeUrl = (img: UploadImage) =>
    `/images/${img.id}/label?project_id=${projectId}&upload_job_id=${jobId}${labelQueryExtras}`

  const thumbSrc = (img: UploadImage) => getImageContentUrl(img.id, participantScope)

  return (
    <aside className="img-panel">
      {!isReviewPanel ? (
        <div className="img-panel-tabs">
          {(Object.keys(FILTER_LABELS) as FilterKey[]).map((key) => (
            <button
              key={key}
              className={`img-panel-tab${filter === key ? ' img-panel-tab--active' : ''}`}
              onClick={() => setFilter(key)}
              title={`${FILTER_LABELS[key]} (${filterImages(images, key, participantScope).length})`}
            >
              {FILTER_LABELS[key]}
            </button>
          ))}
        </div>
      ) : null}

      {/* 이미지 목록 */}
      <div className="img-panel-list">
        {loading && <p className="img-panel-empty">불러오는 중…</p>}
        {!loading && filtered.length === 0 && (
          <p className="img-panel-empty">{isReviewPanel ? '검토 대기 이미지가 없습니다' : '이미지가 없습니다'}</p>
        )}
        {filtered.map((img) => (
          <Link
            key={img.id}
            to={makeUrl(img)}
            className={[
              'img-panel-item',
              statusBorderClass(img.assignment_status),
              img.id === currentImageId ? 'img-panel-item--active' : '',
            ]
              .filter(Boolean)
              .join(' ')}
          >
            <img
              src={thumbSrc(img)}
              alt={img.file_name}
              loading="lazy"
              crossOrigin="use-credentials"
            />
          </Link>
        ))}
      </div>
    </aside>
  )
}
