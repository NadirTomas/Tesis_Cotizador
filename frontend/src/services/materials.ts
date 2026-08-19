import { API_BASE_URL } from "../config/api";

export interface Material {
  id: number;
  name: string;
  thickness_mm: number;
  sheet_width_mm: number;
  sheet_height_mm: number;
  sheet_cost_ars: number;
  active: boolean;
  created_at: string;
}

export interface MaterialCreate {
  name: string;
  thickness_mm: number;
  sheet_width_mm: number;
  sheet_height_mm: number;
  sheet_cost_ars: number;
}

export interface MaterialUpdate {
  name?: string;
  thickness_mm?: number;
  sheet_width_mm?: number;
  sheet_height_mm?: number;
  sheet_cost_ars?: number;
}

const BASE = `${API_BASE_URL}/materials`;

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem("auth_token");
  return {
    "Content-Type": "application/json",
    ...(token && { "Authorization": `Bearer ${token}` }),
  };
}

export async function getMaterials(): Promise<Material[]> {
  const res = await fetch(BASE);
  if (!res.ok) throw new Error("Error al obtener materiales");
  return res.json();
}

export async function createMaterial(data: MaterialCreate): Promise<Material> {
  const res = await fetch(BASE, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Error al crear material");
  return res.json();
}

export async function updateMaterial(id: number, data: MaterialUpdate): Promise<Material> {
  const res = await fetch(`${BASE}/${id}`, {
    method: "PUT",
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Error al actualizar material");
  return res.json();
}

export async function deleteMaterial(id: number): Promise<void> {
  const res = await fetch(`${BASE}/${id}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Error al eliminar material");
}
