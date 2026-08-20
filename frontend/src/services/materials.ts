import { API_BASE_URL } from "../config/api";
import { apiFetch, getAuthHeaders } from "./apiClient";

export interface Material {
  id: number;
  name: string;
  material_type: string | null;
  alloy: string | null;
  thickness_mm: number;
  sheet_width_mm: number;
  sheet_height_mm: number;
  sheet_cost_ars: number;
  active: boolean;
  created_at: string;
}

export interface MaterialCreate {
  name: string;
  material_type: string;
  alloy?: string;
  thickness_mm: number;
  sheet_width_mm: number;
  sheet_height_mm: number;
  sheet_cost_ars: number;
}

export interface MaterialUpdate {
  name?: string;
  material_type?: string;
  alloy?: string;
  thickness_mm?: number;
  sheet_width_mm?: number;
  sheet_height_mm?: number;
  sheet_cost_ars?: number;
}

const BASE = `${API_BASE_URL}/materials`;

export async function getMaterials(): Promise<Material[]> {
  const res = await apiFetch(BASE, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error("Error al obtener materiales");
  return res.json();
}

export async function createMaterial(data: MaterialCreate): Promise<Material> {
  const res = await apiFetch(BASE, {
    method: "POST",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Error al crear material");
  return res.json();
}

export async function updateMaterial(id: number, data: MaterialUpdate): Promise<Material> {
  const res = await apiFetch(`${BASE}/${id}`, {
    method: "PUT",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Error al actualizar material");
  return res.json();
}

export async function deleteMaterial(id: number): Promise<void> {
  const res = await apiFetch(`${BASE}/${id}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Error al eliminar material");
}
