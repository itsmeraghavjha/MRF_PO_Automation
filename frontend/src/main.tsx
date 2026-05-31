import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'

// Import your global styles
import './styles/global.css'

// Import your pages
import DashboardPage from './pages/DashboardPage'

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        {/* The Dashboard is your home page */}
        <Route path="/" element={<DashboardPage />} />
        
        {/* You can add your other routes here later as you build them: */}
        {/* <Route path="/orders" element={<OrdersPage />} /> */}
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
)