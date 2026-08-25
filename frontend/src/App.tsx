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
import GuestRoute from "./components/GuestRoute";
import { AdminProvider } from "./context/AdminContext";
import { AuthProvider } from "./context/AuthContext";
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

import AISettings from "./pages/AISettings";
import SystemHealth from "./pages/SystemHealth";
import SystemHealthPage from "./pages/SystemHealthPage";
import DocumentsPage from "./pages/admin/DocumentsPage";
import DocumentSettingsPage from "./pages/admin/DocumentSettingsPage";
import SourceSettingsPage from "./pages/admin/SourceSettingsPage";
import AuditPage from "./pages/admin/AuditPage";
import BackupPage from "./pages/admin/BackupPage";
import SecurityManagementPage from "./pages/admin/SecurityManagementPage";
import TenantManagementPage from "./pages/admin/TenantManagementPage";
import LoginAuditPage from "./pages/admin/LoginAuditPage";
import RoleGuard from "./components/RoleGuard";


export default function App() {
  const location = useLocation();
  const isAdmin = location.pathname.startsWith("/admin");

  return (
    <div className={`font-sans antialiased min-h-screen ${isAdmin ? "bg-gray-50" : "bg-transparent"}`}>
         <AuthProvider>
            <AdminProvider>
                <ToastContainer position="bottom-right" autoClose={3000} hideProgressBar={false} newestOnTop pauseOnFocusLoss draggable pauseOnHover theme="colored" />
                <Routes>
                    <Route path="/login" element={
                        <GuestRoute>
                            <Login />
                        </GuestRoute>
                    } />
                    
                    <Route path="/admin" element={
                        <ProtectedRoute>
                            <AdminLayout />
                        </ProtectedRoute>
                    }>
                        <Route index element={<AdminDashboard />} />
                        <Route path="wizard" element={
                            <RoleGuard permission="configure_system">
                                <OnboardingWizard />
                            </RoleGuard>
                        } />
                        <Route path="legacy" element={
                            <RoleGuard permission="configure_system">
                                <LegacyOnboarding />
                            </RoleGuard>
                        } />
                        <Route path="semantic" element={
                            <RoleGuard permission="update_record">
                                <SemanticMapper />
                            </RoleGuard>
                        } />
                        <Route path="builder" element={
                            <RoleGuard permission="create_record">
                                <ReportBuilder />
                            </RoleGuard>
                        } />
                        <Route path="reports" element={
                            <RoleGuard permission="view_logs">
                                <SavedReports />
                            </RoleGuard>
                        } />
                        <Route path="relationships" element={
                            <RoleGuard permission="configure_system">
                                <RelationshipGovernance />
                            </RoleGuard>
                        } />
                        <Route path="routes" element={
                            <RoleGuard permission="configure_system">
                                <RouteMap />
                            </RoleGuard>
                        } />
                        <Route path="ai-settings" element={
                            <RoleGuard permission="configure_system">
                                <AISettings />
                            </RoleGuard>
                        } />
                        <Route path="health" element={
                            <RoleGuard permission="view_logs">
                                <SystemHealth />
                            </RoleGuard>
                        } />
                        <Route path="system-health" element={
                            <RoleGuard permission="view_logs">
                                <SystemHealthPage />
                            </RoleGuard>
                        } />
                        <Route path="documents" element={
                            <RoleGuard permission="upload_document">
                                <DocumentsPage />
                            </RoleGuard>
                        } />
                        <Route path="settings/documents" element={
                            <RoleGuard permission="configure_system">
                                <DocumentSettingsPage />
                            </RoleGuard>
                        } />
                        <Route path="settings/sources" element={
                            <RoleGuard permission="configure_system">
                                <SourceSettingsPage />
                            </RoleGuard>
                        } />
                        <Route path="audit" element={
                            <RoleGuard permission="view_logs">
                                <AuditPage />
                            </RoleGuard>
                        } />
                        <Route path="backups" element={
                            <RoleGuard permission={["restore_backup", "delete_system_data", "configure_system"]}>
                                <BackupPage />
                            </RoleGuard>
                        } />
                        <Route path="security" element={
                            <RoleGuard permission="manage_users">
                                <SecurityManagementPage />
                            </RoleGuard>
                        } />
                        <Route path="tenants" element={
                            <RoleGuard permission="configure_system">
                                <TenantManagementPage />
                            </RoleGuard>
                        } />
                        <Route path="audit/login" element={
                            <RoleGuard permission="view_logs">
                                <LoginAuditPage />
                            </RoleGuard>
                        } />
                        {/* Legacy Redirects or direct links */}
                        <Route path="users" element={
                            <RoleGuard permission="manage_users">
                                <SecurityManagementPage />
                            </RoleGuard>
                        } />
                        <Route path="roles" element={
                            <RoleGuard permission="manage_users">
                                <SecurityManagementPage />
                            </RoleGuard>
                        } />

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
