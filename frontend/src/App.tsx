import { useEffect, type ReactNode } from 'react'
import { Navigate, Route, Routes, useNavigate } from 'react-router-dom'

import { useAuth } from './auth/AuthContext'
import { HomePage } from './pages/HomePage'
import { JoinPage } from './pages/JoinPage'
import { LoginPage } from './pages/LoginPage'
import { ProjectDetailPage } from './pages/ProjectDetailPage'
import { ProjectsPage } from './pages/ProjectsPage'

import './App.css'

const RETURN_TO_KEY = 'ilt_return_to'

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="page-shell page-shell--center">
        <p className="muted">세션 확인 중…</p>
      </div>
    )
  }

  if (!user) {
    const dest = window.location.pathname + window.location.search
    if (dest !== '/' && dest !== '/login') {
      sessionStorage.setItem(RETURN_TO_KEY, dest)
    }
    return <Navigate to="/login" replace />
  }

  return children
}

/** 로그인 직후 원래 가려던 경로(sessionStorage)로 자동 이동 */
function PostLoginRedirect() {
  const { user, loading } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (loading || !user) return
    const returnTo = sessionStorage.getItem(RETURN_TO_KEY)
    if (returnTo) {
      sessionStorage.removeItem(RETURN_TO_KEY)
      navigate(returnTo, { replace: true })
    }
  }, [user, loading, navigate])

  return null
}

export default function App() {
  return (
    <>
      <PostLoginRedirect />
      <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/join"
        element={
          <ProtectedRoute>
            <JoinPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:projectId"
        element={
          <ProtectedRoute>
            <ProjectDetailPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects"
        element={
          <ProtectedRoute>
            <ProjectsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <HomePage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </>
  )
}
