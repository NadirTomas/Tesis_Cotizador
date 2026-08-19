import { API_BASE_URL } from "../config/api";
import { apiFetch, getAuthHeaders } from "./apiClient";

export interface CompanyConfig {
  id: number;
  company_name: string;
  legal_name: string | null;
  cuit: string | null;
  address: string | null;
  phone: string | null;
  email: string | null;
  has_logo: boolean;
}

export interface CompanyConfigUpdate {
  company_name?: string;
  legal_name?: string;
  cuit?: string;
  address?: string;
  phone?: string;
  email?: string;
}

const BASE = `${API_BASE_URL}/company`;

export async function getCompany(): Promise<CompanyConfig> {
  const res = await apiFetch(BASE);
  if (!res.ok) throw new Error("Error al obtener configuración de empresa");
  return res.json();
}

export async function updateCompany(data: CompanyConfigUpdate): Promise<CompanyConfig> {
  const res = await apiFetch(BASE, {
    method: "PUT",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Error al guardar configuración de empresa");
  return res.json();
}

export async function uploadLogo(file: File): Promise<CompanyConfig> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await apiFetch(`${BASE}/logo`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: formData,
  });
  if (!res.ok) throw new Error("Error al subir el logo");
  return res.json();
}

export function getCompanyLogoUrl(): string {
  return `${BASE}/logo`;
}
