import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { Layout } from "./components/Layout";
import { Loading } from "./components/States";
import { AdminPage } from "./pages/AdminPage";
import { AuditTrailPage } from "./pages/AuditTrailPage";
import { CommandCenter } from "./pages/CommandCenter";
import { DocumentBatchReview } from "./pages/documents/DocumentBatchReview";
import { DocumentCentre } from "./pages/documents/DocumentCentre";
import { DocumentDetailPage } from "./pages/documents/DocumentDetailPage";
import { BatchDetail } from "./pages/imports/BatchDetail";
import { ImportCentre } from "./pages/imports/ImportCentre";
import { Model360Page } from "./pages/model360/Model360Page";
import { ModelForm } from "./pages/ModelForm";
import { OperationsBoard } from "./pages/OperationsBoard";
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
        <Route index element={<CommandCenter />} />
        <Route path="operations" element={<OperationsBoard />} />
        <Route path="models" element={<Navigate to="/operations" replace />} />
        <Route path="models/new" element={<ModelForm />} />
        <Route path="models/:modelId" element={<Model360Page />} />
        <Route path="models/:modelId/edit" element={<ModelForm />} />
        <Route path="monitoring" element={<PlannedPage {...PLANNED.monitoring} />} />
        <Route path="data-audit" element={<PlannedPage {...PLANNED.dataAudit} />} />
        <Route path="documents" element={<DocumentCentre />} />
        <Route path="documents/batches/:batchId" element={<DocumentBatchReview />} />
        <Route path="documents/:documentId" element={<DocumentDetailPage />} />
        <Route path="imports" element={<ImportCentre />} />
        <Route path="imports/:batchId" element={<BatchDetail />} />
        <Route path="audit" element={<AuditTrailPage />} />
        <Route path="admin" element={<AdminPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
