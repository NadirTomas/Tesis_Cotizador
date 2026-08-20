import { Box, CircularProgress } from "@mui/material";
import { lazy, Suspense } from "react";
import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import MainLayout from "./layouts/MainLayout";
import LoginPage from "./pages/LoginPage";

const ClientsPage = lazy(() => import("./pages/ClientsPage"));
const CompanyPage = lazy(() => import("./pages/CompanyPage"));
const CreateCompanyPage = lazy(() => import("./pages/CreateCompanyPage"));
const EmployeesPage = lazy(() => import("./pages/EmployeesPage"));
const HomePage = lazy(() => import("./pages/HomePage"));
const MachineConfigsPage = lazy(() => import("./pages/MachineConfigsPage"));
const MaterialsPage = lazy(() => import("./pages/MaterialsPage"));
const NestingPage = lazy(() => import("./pages/NestingPage"));
const PiecesPage = lazy(() => import("./pages/PiecesPage"));
const QuotationDetailPage = lazy(() => import("./pages/QuotationDetailPage"));
const QuoteFromCadWizardPage = lazy(() => import("./pages/QuoteFromCadWizardPage"));
const QuotationsPage = lazy(() => import("./pages/QuotationsPage"));
const SelectCompanyPage = lazy(() => import("./pages/SelectCompanyPage"));
const StockPage = lazy(() => import("./pages/StockPage"));
const StockDetailPage = lazy(() => import("./pages/StockDetailPage"));

function RouteFallback() {
  return (
    <Box display="flex" justifyContent="center" mt={6}>
      <CircularProgress />
    </Box>
  );
}

function ProtectedRoute() {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />;
}

function RequireCompany() {
  const { hasCompany } = useAuth();
  return hasCompany ? <Outlet /> : <Navigate to="/select-company" replace />;
}

function RequireOwner({ children }: { children: React.ReactNode }) {
  const { companyRole } = useAuth();
  return companyRole === "owner" ? <>{children}</> : <Navigate to="/" replace />;
}

function App() {
  return (
    <Suspense fallback={<RouteFallback />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/select-company" element={<SelectCompanyPage />} />
          <Route path="/companies/new" element={<CreateCompanyPage />} />
          <Route element={<RequireCompany />}>
            <Route element={<MainLayout />}>
              <Route path="/" element={<HomePage />} />
              <Route path="/pieces" element={<PiecesPage />} />
              <Route path="/clients" element={<ClientsPage />} />
              <Route path="/quotations" element={<QuotationsPage />} />
              <Route path="/quotations/:id" element={<QuotationDetailPage />} />
              <Route path="/materials" element={<MaterialsPage />} />
              <Route path="/machine-configs" element={<MachineConfigsPage />} />
              <Route path="/company" element={<CompanyPage />} />
              <Route path="/employees" element={<RequireOwner><EmployeesPage /></RequireOwner>} />
              <Route path="/nesting" element={<NestingPage />} />
              <Route path="/stock" element={<StockPage />} />
              <Route path="/stock/:id" element={<StockDetailPage />} />
              <Route path="/quotes/new-from-cad" element={<QuoteFromCadWizardPage />} />
            </Route>
          </Route>
        </Route>
      </Routes>
    </Suspense>
  );
}

export default App;
