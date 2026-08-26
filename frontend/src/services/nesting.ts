import { API_BASE_URL } from "../config/api";
import { apiFetch, getAuthHeaders, parseErrorDetail } from "./apiClient";

export interface Placement {
  piece_id: number;
  piece_label: string;
  x: number;
  y: number;
  width_mm: number;
  height_mm: number;
  rotated: boolean;
}

export interface NestingSheet {
  placements: Placement[];
  utilization_pct: number;
}

export interface NestingResult {
  sheets: NestingSheet[];
  total_sheets: number;
  total_pieces_requested: number;
  total_pieces_placed: number;
  overall_utilization_pct: number;
  sheet_width_mm: number;
  sheet_height_mm: number;
  margin_mm: number;
}

export interface NestingItemRequest {
  piece_id: number;
  quantity: number;
}

export interface NestingRequest {
  items: NestingItemRequest[];
  sheet_width_mm: number;
  sheet_height_mm: number;
  margin_mm?: number;
  allow_rotation?: boolean;
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
    throw new Error(parseErrorDetail(err) ?? "Error al calcular nesting");
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
  const res = await apiFetch(`${API_BASE_URL}/quotations/stats`, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error("Error al cargar estadísticas");
  return res.json();
}
