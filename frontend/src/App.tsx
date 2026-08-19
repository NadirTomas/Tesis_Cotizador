import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import MainLayout from "./layouts/MainLayout";
import ClientsPage from "./pages/ClientsPage";
import CompanyPage from "./pages/CompanyPage";
import HomePage from "./pages/HomePage";
import LoginPage from "./pages/LoginPage";
import MachineConfigsPage from "./pages/MachineConfigsPage";
import MaterialsPage from "./pages/MaterialsPage";
import NestingPage from "./pages/NestingPage";
import PiecesPage from "./pages/PiecesPage";
import QuotationDetailPage from "./pages/QuotationDetailPage";
import QuoteFromCadWizardPage from "./pages/QuoteFromCadWizardPage";
import QuotationsPage from "./pages/QuotationsPage";

function ProtectedRoute() {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />;
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<MainLayout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/pieces" element={<PiecesPage />} />
          <Route path="/clients" element={<ClientsPage />} />
          <Route path="/quotations" element={<QuotationsPage />} />
          <Route path="/quotations/:id" element={<QuotationDetailPage />} />
          <Route path="/materials" element={<MaterialsPage />} />
          <Route path="/machine-configs" element={<MachineConfigsPage />} />
          <Route path="/company" element={<CompanyPage />} />
          <Route path="/nesting" element={<NestingPage />} />
          <Route path="/quotes/new-from-cad" element={<QuoteFromCadWizardPage />} />
        </Route>
      </Route>
    </Routes>
  );
}

export default App;
