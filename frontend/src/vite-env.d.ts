/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 비우면 `/api/...` 상대 경로. 예: `http://127.0.0.1:8000` */
  readonly VITE_API_BASE_URL?: string
}
