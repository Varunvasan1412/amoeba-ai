import { Routes, Route, useLocation } from "react-router-dom";
import ChatWidget from "./components/ChatWidget";
import AdminLayout from "./components/AdminLayout";
import AdminDashboard from "./pages/AdminDashboard";
import SemanticMapper from "./pages/SemanticMapper";
import ReportBuilder from "./pages/ReportBuilder";
import SavedReports from "./pages/SavedReports";
import RelationshipGovernance from "./pages/RelationshipGovernance";
import ClientSetup from "./pages/ClientSetup";
import LegacyOnboarding from "./pages/LegacyOnboarding";
import Login from "./pages/Login";
import ProtectedRoute from "./components/ProtectedRoute";
import { AdminProvider } from "./context/AdminContext";
import { AuthProvider } from "./context/AuthContext";

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
                        <Route path="setup" element={<ClientSetup />} />
                        <Route path="legacy" element={<LegacyOnboarding />} />
                        <Route path="semantic" element={<SemanticMapper />} />
                        <Route path="builder" element={<ReportBuilder />} />
                        <Route path="reports" element={<SavedReports />} />
                        <Route path="relationships" element={<RelationshipGovernance />} />
                    </Route>

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
