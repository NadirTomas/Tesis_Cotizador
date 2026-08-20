import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { refreshTokenRequest } from "../services/auth";

const REFRESH_INTERVAL_MS = 6 * 60 * 60 * 1000; // 6 horas

interface AuthContextType {
  token: string | null;
  isAuthenticated: boolean;
  companyId: number | null;
  companyName: string | null;
  companyRole: string | null;
  hasCompany: boolean;
  login: (token: string) => void;
  logout: () => void;
  selectCompany: (companyId: number, role: string, companyName: string) => void;
  clearCompany: () => void;
}

const AuthContext = createContext<AuthContextType>(null!);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("auth_token"));
  const [companyId, setCompanyId] = useState<number | null>(() => {
    const raw = localStorage.getItem("company_id");
    return raw ? Number(raw) : null;
  });
  const [companyRole, setCompanyRole] = useState<string | null>(() =>
    localStorage.getItem("company_role")
  );
  const [companyName, setCompanyName] = useState<string | null>(() =>
    localStorage.getItem("company_name")
  );

  const login = (t: string) => {
    localStorage.setItem("auth_token", t);
    setToken(t);
  };

  const logout = () => {
    localStorage.removeItem("auth_token");
    localStorage.removeItem("company_id");
    localStorage.removeItem("company_role");
    localStorage.removeItem("company_name");
    setToken(null);
    setCompanyId(null);
    setCompanyRole(null);
    setCompanyName(null);
  };

  const selectCompany = (id: number, role: string, name: string) => {
    localStorage.setItem("company_id", String(id));
    localStorage.setItem("company_role", role);
    localStorage.setItem("company_name", name);
    setCompanyId(id);
    setCompanyRole(role);
    setCompanyName(name);
  };

  const clearCompany = () => {
    localStorage.removeItem("company_id");
    localStorage.removeItem("company_role");
    localStorage.removeItem("company_name");
    setCompanyId(null);
    setCompanyRole(null);
    setCompanyName(null);
  };

  // Refresco silencioso: mientras haya sesión activa, renueva el token
  // periódicamente para que una pestaña abierta mucho tiempo no expire de
  // golpe. Si falla (token ya vencido), no hace nada — el 401 handler de
  // apiFetch ya cubre ese caso en la próxima request real.
  useEffect(() => {
    if (!token) return;
    const interval = setInterval(() => {
      refreshTokenRequest()
        .then((res) => {
          localStorage.setItem("auth_token", res.access_token);
          setToken(res.access_token);
        })
        .catch(() => {});
    }, REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [token]);

  return (
    <AuthContext.Provider
      value={{
        token,
        isAuthenticated: !!token,
        companyId,
        companyName,
        companyRole,
        hasCompany: !!companyId,
        login,
        logout,
        selectCompany,
        clearCompany,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
