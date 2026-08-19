import { API_BASE_URL } from "../config/api";
import { apiFetch, getAuthHeaders } from "./apiClient";

export interface NestingPosition {
  x: number;
  y: number;
}

export interface NestingResult {
  positions: NestingPosition[];
  pieces_fit: number;
  pieces_per_row: number;
  rows: number;
  utilization_pct: number;
  piece_width_mm: number;
  piece_height_mm: number;
  sheet_width_mm: number;
  sheet_height_mm: number;
  margin_mm: number;
}

export interface NestingRequest {
  piece_id: number;
  sheet_width_mm: number;
  sheet_height_mm: number;
  margin_mm?: number;
}

const BASE = `${API_BASE_URL}/nesting`;

export async function calculateNesting(data: NestingRequest): Promise<NestingResult> {
  const res = await apiFetch(`${BASE}/calculate`, {
    method: "POST",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Error al calcular nesting");
  }
  return res.json();
}

export interface DashboardStats {
  total: number;
  this_month: number;
  total_ars_this_month: number;
  by_status: Record<string, number>;
  expiring_soon: number;
  recent: {
    id: number;
    number: string;
    client_id: number;
    status: string;
    total_ars: number;
    issue_date: string;
  }[];
}

export async function getStats(): Promise<DashboardStats> {
  const res = await apiFetch(`${API_BASE_URL}/quotations/stats`);
  if (!res.ok) throw new Error("Error al cargar estadísticas");
  return res.json();
}
