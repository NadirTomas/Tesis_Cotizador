import { API_BASE_URL } from "../config/api";
import { apiFetch, getAuthHeaders } from "./apiClient";

export interface MachineConfig {
  id: number;
  material_id: number;
  cut_speed_mm_min: number;
  machine_cost_per_hour_ars: number;
  setup_time_min: number;
  labor_percent: number;
  active: boolean;
}

export interface MachineConfigCreate {
  material_id: number;
  cut_speed_mm_min: number;
  machine_cost_per_hour_ars: number;
  setup_time_min: number;
  labor_percent?: number;
}

export interface MachineConfigUpdate {
  cut_speed_mm_min?: number;
  machine_cost_per_hour_ars?: number;
  setup_time_min?: number;
  labor_percent?: number;
  active?: boolean;
}

const BASE = `${API_BASE_URL}/machine-configs`;

export async function getMachineConfigs(): Promise<MachineConfig[]> {
  const res = await apiFetch(BASE, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error("Error al obtener configuraciones de máquina");
  return res.json();
}

export async function createMachineConfig(data: MachineConfigCreate): Promise<MachineConfig> {
  const res = await apiFetch(BASE, {
    method: "POST",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Error al crear configuración de máquina");
  return res.json();
}

export async function updateMachineConfig(id: number, data: MachineConfigUpdate): Promise<MachineConfig> {
  const res = await apiFetch(`${BASE}/${id}`, {
    method: "PUT",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Error al actualizar configuración de máquina");
  return res.json();
}

export async function deleteMachineConfig(id: number): Promise<void> {
  const res = await apiFetch(`${BASE}/${id}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Error al eliminar configuración de máquina");
}
