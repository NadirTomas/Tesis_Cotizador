import { API_BASE_URL } from "../config/api";

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

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem("auth_token");
  return {
    "Content-Type": "application/json",
    ...(token && { "Authorization": `Bearer ${token}` }),
  };
}

function getAuthHeadersMultipart(): Record<string, string> {
  const token = localStorage.getItem("auth_token");
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

export async function getCompany(): Promise<CompanyConfig> {
  const res = await fetch(BASE);
  if (!res.ok) throw new Error("Error al obtener configuración de empresa");
  return res.json();
}

export async function updateCompany(data: CompanyConfigUpdate): Promise<CompanyConfig> {
  const res = await fetch(BASE, {
    method: "PUT",
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Error al guardar configuración de empresa");
  return res.json();
}

export async function uploadLogo(file: File): Promise<CompanyConfig> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${BASE}/logo`, {
    method: "POST",
    headers: getAuthHeadersMultipart(),
    body: formData,
  });
  if (!res.ok) throw new Error("Error al subir el logo");
  return res.json();
}

export function getCompanyLogoUrl(): string {
  return `${BASE}/logo`;
}
