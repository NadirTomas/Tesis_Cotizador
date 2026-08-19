import { API_BASE_URL } from "../config/api";

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

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem("auth_token");
  return {
    "Content-Type": "application/json",
    ...(token && { "Authorization": `Bearer ${token}` }),
  };
}

export async function getMachineConfigs(): Promise<MachineConfig[]> {
  const res = await fetch(BASE);
  if (!res.ok) throw new Error("Error al obtener configuraciones de máquina");
  return res.json();
}

export async function createMachineConfig(data: MachineConfigCreate): Promise<MachineConfig> {
  const res = await fetch(BASE, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Error al crear configuración de máquina");
  return res.json();
}

export async function updateMachineConfig(id: number, data: MachineConfigUpdate): Promise<MachineConfig> {
  const res = await fetch(`${BASE}/${id}`, {
    method: "PUT",
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Error al actualizar configuración de máquina");
  return res.json();
}

export async function deleteMachineConfig(id: number): Promise<void> {
  const res = await fetch(`${BASE}/${id}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Error al eliminar configuración de máquina");
}
