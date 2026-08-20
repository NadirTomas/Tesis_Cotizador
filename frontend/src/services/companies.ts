import { API_BASE_URL } from "../config/api";
import { apiFetch, getAuthHeaders } from "./apiClient";

export interface Company {
  id: number;
  company_name: string;
  legal_name: string | null;
  cuit: string | null;
  address: string | null;
  phone: string | null;
  email: string | null;
  is_active: boolean;
  has_logo: boolean;
  created_at: string;
}

export interface CompanyCreate {
  company_name: string;
  legal_name?: string;
  cuit?: string;
  address?: string;
  phone?: string;
  email?: string;
}

export interface CompanyUpdate {
  company_name?: string;
  legal_name?: string;
  cuit?: string;
  address?: string;
  phone?: string;
  email?: string;
}

export interface MyCompany {
  id: number;
  company_name: string;
  is_active: boolean;
  role: "owner" | "employee";
  member_is_active: boolean;
}

export interface CompanyMember {
  id: number;
  company_id: number;
  user_id: number;
  email: string;
  role: "owner" | "employee";
  is_active: boolean;
  created_at: string;
}

export interface CompanyMemberCreate {
  email: string;
  password: string;
  role?: "owner" | "employee";
}

export interface CompanyMemberUpdate {
  role?: "owner" | "employee";
  is_active?: boolean;
}

const BASE = `${API_BASE_URL}/companies`;

export async function getMyCompanies(): Promise<MyCompany[]> {
  const res = await apiFetch(`${BASE}/me`, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error("Error al obtener tus empresas");
  return res.json();
}

export async function createCompany(data: CompanyCreate): Promise<Company> {
  const res = await apiFetch(BASE, {
    method: "POST",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Error al crear la empresa");
  return res.json();
}

export async function getCompany(id: number): Promise<Company> {
  const res = await apiFetch(`${BASE}/${id}`, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error("Error al obtener la empresa");
  return res.json();
}

export async function updateCompany(id: number, data: CompanyUpdate): Promise<Company> {
  const res = await apiFetch(`${BASE}/${id}`, {
    method: "PUT",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Error al guardar la empresa");
  return res.json();
}

export async function uploadLogo(id: number, file: File): Promise<Company> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await apiFetch(`${BASE}/${id}/logo`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: formData,
  });
  if (!res.ok) throw new Error("Error al subir el logo");
  return res.json();
}

export function getCompanyLogoUrl(id: number): string {
  return `${BASE}/${id}/logo`;
}

export async function getMembers(companyId: number): Promise<CompanyMember[]> {
  const res = await apiFetch(`${BASE}/${companyId}/members`, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error("Error al obtener los empleados");
  return res.json();
}

export async function createMember(companyId: number, data: CompanyMemberCreate): Promise<CompanyMember> {
  const res = await apiFetch(`${BASE}/${companyId}/members`, {
    method: "POST",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Error al crear el empleado");
  }
  return res.json();
}

export async function updateMember(
  companyId: number,
  memberId: number,
  data: CompanyMemberUpdate
): Promise<CompanyMember> {
  const res = await apiFetch(`${BASE}/${companyId}/members/${memberId}`, {
    method: "PATCH",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Error al actualizar el empleado");
  }
  return res.json();
}
