import { useEffect, useState } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import Sidebar from './components/shared/sidebar'
import DashboardPage from './pages/DashboardPage'
import OrdersPage from './pages/OrdersPage'
import OrderDetailPage from './pages/OrderDetailPage'
import ExceptionsPage from './pages/ExceptionsPage'
import MasterDataPage from './pages/MasterDataPage'
import { getDashboard } from './services/api'

export default function App() {
  const [exceptionCount, setExceptionCount] = useState(0)
  const location = useLocation()

  useEffect(() => {
    getDashboard()
      .then(d => setExceptionCount(d.kpis.exceptions_pending))
      .catch(() => {})
  }, [location.pathname])

  return (
    <div className="app-shell">
      <Sidebar exceptionCount={exceptionCount} />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/orders" element={<OrdersPage />} />
          <Route path="/orders/:id" element={<OrderDetailPage />} />
          <Route path="/exceptions" element={<ExceptionsPage />} />
          <Route path="/master-data" element={<MasterDataPage />} />
        </Routes>
      </main>
    </div>
  )
}