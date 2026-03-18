import { Routes, Route, useLocation } from "react-router-dom";
import ChatWidget from "./components/ChatWidget";
import AmoebaChat from "./pages/AmoebaChat";
import AdminLayout from "./components/AdminLayout";
import AdminDashboard from "./pages/AdminDashboard";
import SemanticMapper from "./pages/SemanticMapper";
import ReportBuilder from "./pages/ReportBuilder";
import SavedReports from "./pages/SavedReports";
import RelationshipGovernance from "./pages/RelationshipGovernance";
import OnboardingWizard from "./pages/admin/OnboardingWizard";
import RouteMap from "./pages/admin/RouteMap";
import LegacyOnboarding from "./pages/LegacyOnboarding";
import Login from "./pages/Login";
import ProtectedRoute from "./components/ProtectedRoute";
import { AdminProvider } from "./context/AdminContext";
import { AuthProvider } from "./context/AuthContext";

import AISettings from "./pages/AISettings";

export default function App() {
  const location = useLocation();
  const isAdmin = location.pathname.startsWith("/admin");

  return (
    <div className={`font-sans antialiased min-h-screen ${isAdmin ? "bg-gray-50" : "bg-transparent"}`}>
         <AuthProvider>
            <AdminProvider>
                <Routes>
                    <Route path="/login" element={<Login />} />
                    
                    <Route path="/admin" element={
                        <ProtectedRoute>
                            <AdminLayout />
                        </ProtectedRoute>
                    }>
                        <Route index element={<AdminDashboard />} />
                        <Route path="wizard" element={<OnboardingWizard />} />
                        <Route path="legacy" element={<LegacyOnboarding />} />
                        <Route path="semantic" element={<SemanticMapper />} />
                        <Route path="builder" element={<ReportBuilder />} />
                        <Route path="reports" element={<SavedReports />} />
                        <Route path="relationships" element={<RelationshipGovernance />} />
                        <Route path="routes" element={<RouteMap />} />
                        <Route path="ai-settings" element={<AISettings />} />
                    </Route>

                    <Route path="/ai" element={<AmoebaChat />} />

                    <Route path="/" element={
                        <div className="pointer-events-auto">
                            <ChatWidget />
                        </div>
                    } />
                </Routes>
            </AdminProvider>
         </AuthProvider>
    </div>
  );
}
