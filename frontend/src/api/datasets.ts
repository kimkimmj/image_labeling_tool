import { apiJson } from './client'
import type {
  DatasetSplit,
  DatasetVersionDetail,
  DatasetVersionSummary,
  ExportFormat,
  ExportJob,
} from '../types/datasets'

export function fetchDatasetVersions(projectId: number): Promise<DatasetVersionSummary[]> {
  return apiJson(`/api/projects/${projectId}/dataset-versions`)
}

export function createDatasetVersion(
  projectId: number,
  body: { name: string; description?: string | null },
): Promise<DatasetVersionDetail> {
  return apiJson(`/api/projects/${projectId}/dataset-versions`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function fetchDatasetVersion(
  projectId: number,
  versionId: number,
): Promise<DatasetVersionDetail> {
  return apiJson(`/api/projects/${projectId}/dataset-versions/${versionId}`)
}

export function fetchDatasetSplits(
  projectId: number,
  versionId: number,
): Promise<DatasetSplit[]> {
  return apiJson(`/api/projects/${projectId}/dataset-versions/${versionId}/dataset-splits`)
}

export function createDatasetSplit(
  projectId: number,
  body: {
    dataset_version_id: number
    name: string
    train_ratio: number
    val_ratio: number
    test_ratio: number
    random_seed?: number
  },
): Promise<DatasetSplit> {
  return apiJson(`/api/projects/${projectId}/dataset-splits`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function createExportJob(
  projectId: number,
  body: {
    dataset_version_id: number
    dataset_split_id: number
    format: ExportFormat
  },
): Promise<ExportJob> {
  return apiJson(`/api/projects/${projectId}/exports`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function fetchExportJob(projectId: number, exportJobId: number): Promise<ExportJob> {
  return apiJson(`/api/projects/${projectId}/exports/${exportJobId}`)
}
