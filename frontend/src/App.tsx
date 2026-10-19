import { Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { useAuth } from "./lib/auth";
import { ExecutiveDashboard } from "./pages/ExecutiveDashboard";
import { IcuRiskPage } from "./pages/IcuRiskPage";
import { LoginPage } from "./pages/LoginPage";
import { PatientsPage } from "./pages/PatientsPage";
import { DiseaseAnalyticsPage } from "./pages/DiseaseAnalyticsPage";
import { GlucoTwinPage } from "./pages/GlucoTwinPage";
import { ReportsPage } from "./pages/ReportsPage";

function RootRedirect() {
  const { user, isLoading } = useAuth();
  if (isLoading) return null;
  return <Navigate to={user ? "/dashboard" : "/login"} replace />;
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<RootRedirect />} />
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <ExecutiveDashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/icu-risk"
        element={
          <ProtectedRoute>
            <IcuRiskPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/glucotwin"
        element={
          <ProtectedRoute>
            <GlucoTwinPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/analytics"
        element={
          <ProtectedRoute>
            <DiseaseAnalyticsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/patients"
        element={
          <ProtectedRoute>
            <PatientsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/reports"
        element={
          <ProtectedRoute>
            <ReportsPage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<RootRedirect />} />
    </Routes>
  );
}

export default App;
