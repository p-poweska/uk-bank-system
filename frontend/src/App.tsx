import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Register from './pages/Register';
import SetupPage from './pages/SetupPage';
import ProtectedRoute from './components/ProtectedRoute';
import JuniorRoute from './components/JuniorRoute';
import Dashboard from './pages/Dashboard';
import Accounts from './pages/Accounts';
import Cards from './pages/Cards';
import History from './pages/History';
import Settings from './pages/Settings';
import Profile from './pages/Profile';
import Payments from './pages/Payments';
import Analytics from './pages/Analytics';
import JuniorDashboard from './pages/JuniorDashboard';
import JuniorPayments from './pages/JuniorPayments';
import JuniorHistory from './pages/JuniorHistory';
import JuniorProfile from './pages/JuniorProfile';
import JuniorAnalytics from './pages/JuniorAnalytics';
import PublicRoute from './components/PublicRoute';
import Layout from './components/Layout';
import JuniorLayout from './components/JuniorLayout';
import { ThemeProvider } from './context/ThemeContext';
import Klik from './pages/Klik';

function App() {
  return (
    <ThemeProvider>
    <Router>
      <Routes>
        
        {/* PUBLIC ROUTES - Chronione przed ZALOGOWANYMI użytkownikami */}
        <Route 
          path="/login" 
          element={
            <PublicRoute>
              <Login />
            </PublicRoute>
          } 
        />
        
        <Route 
          path="/register" 
          element={
            <PublicRoute>
              <Register />
            </PublicRoute>
          } 
        />

        {/* DEFAULT REDIRECT - Jeśli wejdziesz na "localhost:5173/" */}
        <Route 
          path="/" 
          element={
            <PublicRoute>
              {/* Jeśli NIE jesteś zalogowany, PublicRoute puści Cię dalej i Navigate wyrzuci Cię na /login */}
              <Navigate to="/login" replace />
            </PublicRoute>
          } 
        />

        {/* PROTECTED ROUTES - Dostępne tylko po zalogowaniu */}
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/setup" element={<SetupPage />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/accounts" element={<Accounts />} />
            <Route path="/cards" element={<Cards />} />
            <Route path="/klik" element={<Klik />} />
            <Route path="/history" element={<History />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/payments" element={<Payments />} />
            <Route path="/analytics" element={<Analytics />} />
          </Route>
        </Route>
        
        {/* JUNIOR ROUTES */}
        <Route element={<JuniorRoute />}>
          <Route element={<JuniorLayout />}>
            <Route path="/junior/dashboard" element={<JuniorDashboard />} />
            <Route path="/junior/payments" element={<JuniorPayments />} />
            <Route path="/junior/history" element={<JuniorHistory />} />
            <Route path="/junior/profile"   element={<JuniorProfile />} />
            <Route path="/junior/analytics" element={<JuniorAnalytics />} />
          </Route>
        </Route>

        {/* CATCH ALL */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />

      </Routes>
    </Router>
    </ThemeProvider>
  );
}

export default App;