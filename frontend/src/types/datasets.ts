export type DatasetVersionSummary = {
  id: number
  project_id: number
  name: string
  description: string | null
  created_by: number
  created_at: string
  item_count: number
}

export type DatasetItem = {
  id: number
  image_id: number
  assignment_id: number
  created_at: string
}

export type DatasetVersionDetail = DatasetVersionSummary & {
  items: DatasetItem[]
}

export type DatasetSplit = {
  id: number
  dataset_version_id: number
  name: string
  train_ratio: number
  val_ratio: number
  test_ratio: number
  random_seed: number
  created_by: number
  created_at: string
  train_count: number
  val_count: number
  test_count: number
  total_count: number
}

export type ExportFormat = 'yolo' | 'coco'

export type ExportJob = {
  id: number
  project_id: number
  dataset_version_id: number
  split_id: number
  format: ExportFormat
  status: string
  export_path: string | null
  error_message: string | null
  created_at: string
  completed_at: string | null
  download_url: string | null
}
