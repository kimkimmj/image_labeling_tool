import { apiJson } from './client'
import type { MlModel } from '../types/projects'

export function uploadMlModel(file: File): Promise<MlModel> {
  const form = new FormData()
  form.append('model_file', file)
  return apiJson<MlModel>('/api/ml-models', {
    method: 'POST',
    body: form,
  })
}

export function fetchMlModels(): Promise<MlModel[]> {
  return apiJson<MlModel[]>('/api/ml-models')
}
