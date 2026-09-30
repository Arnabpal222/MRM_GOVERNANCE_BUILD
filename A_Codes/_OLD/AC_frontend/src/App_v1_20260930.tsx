import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { Layout } from "./components/Layout";
import { Loading } from "./components/States";
import { AdminPage } from "./pages/AdminPage";
import { AuditTrailPage } from "./pages/AuditTrailPage";
import { PlannedPage } from "./pages/PlannedPage";
import { PLANNED } from "./pages/plannedScreens";
import { SignInPage } from "./pages/SignInPage";

export function App() {
  const { me, isLoading } = useAuth();
  if (isLoading) return <div className="signin"><Loading label="Signing in…" /></div>;
  if (!me) return <SignInPage />;

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<PlannedPage {...PLANNED.command} />} />
        <Route path="operations" element={<PlannedPage {...PLANNED.operations} />} />
        <Route path="models" element={<PlannedPage {...PLANNED.model360} />} />
        <Route path="models/:modelId" element={<PlannedPage {...PLANNED.model360} />} />
        <Route path="monitoring" element={<PlannedPage {...PLANNED.monitoring} />} />
        <Route path="data-audit" element={<PlannedPage {...PLANNED.dataAudit} />} />
        <Route path="documents" element={<PlannedPage {...PLANNED.documents} />} />
        <Route path="imports" element={<PlannedPage {...PLANNED.imports} />} />
        <Route path="audit" element={<AuditTrailPage />} />
        <Route path="admin" element={<AdminPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
