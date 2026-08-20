import { API_BASE_URL } from "../config/api";
import { apiFetch, getAuthHeaders } from "./apiClient";

export type StockType = "FULL_SHEET" | "REMNANT";
export type StockStatus = "AVAILABLE" | "RESERVED" | "CONSUMED" | "DISCARDED";

export interface GeoJSONPolygon {
  type: "Polygon";
  coordinates: number[][][];
}

export interface StockSheet {
  id: number;
  company_id: number;
  material_id: number;
  code: string;
  stock_type: StockType;
  status: StockStatus;
  original_width_mm: number | null;
  original_height_mm: number | null;
  original_area_mm2: number;
  remaining_area_mm2: number;
  geometry: GeoJSONPolygon;
  source_sheet_id: number | null;
  source_quotation_id: number | null;
  created_at: string;
  updated_at: string;
  created_by_id: number | null;
}

export interface StockSheetCreate {
  material_id: number;
  stock_type: StockType;
  width_mm?: number;
  height_mm?: number;
  geometry?: GeoJSONPolygon;
  source_sheet_id?: number;
  source_quotation_id?: number;
}

export interface StockFilters {
  material_id?: number;
  material_type?: string;
  alloy?: string;
  thickness_mm?: number;
  status?: StockStatus;
  stock_type?: StockType;
}

export interface StockRecommendation {
  stock_sheet_id: number;
  stock_code: string;
  stock_type: StockType;
  rotation: number;
  x: number;
  y: number;
  piece_area_mm2: number;
  piece_width_mm: number;
  piece_height_mm: number;
  stock_remaining_area_mm2: number;
  utilization_percent: number;
  score: number;
  reason: string;
}

export interface StockReservation {
  id: number;
  stock_sheet_id: number;
  piece_id: number;
  quotation_id: number;
  quotation_item_id: number | null;
  rotation: number;
  x: number;
  y: number;
  status: "ACTIVE" | "RELEASED" | "CONSUMED";
  created_by_id: number | null;
  created_at: string;
}

export interface RemnantResult {
  stock_sheet_id: number;
  code: string;
  area_mm2: number;
}

export interface ConfirmCutResult {
  reservation_id: number;
  stock_sheet_id: number;
  stock_code: string;
  status: string;
  remnants: RemnantResult[];
}

export interface StockMovement {
  id: number;
  stock_sheet_id: number;
  movement_type: string;
  quotation_id: number | null;
  created_by_id: number | null;
  created_at: string;
  details: Record<string, unknown> | null;
}

const BASE = `${API_BASE_URL}/stock`;

function buildQuery(filters: StockFilters): string {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  });
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export async function getStock(filters: StockFilters = {}): Promise<StockSheet[]> {
  const res = await apiFetch(`${BASE}${buildQuery(filters)}`, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error("Error al obtener el stock");
  return res.json();
}

export async function getStockSheet(id: number): Promise<StockSheet> {
  const res = await apiFetch(`${BASE}/${id}`, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error("Error al obtener el stock");
  return res.json();
}

export async function createStockSheet(data: StockSheetCreate): Promise<StockSheet> {
  const res = await apiFetch(BASE, {
    method: "POST",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Error al crear el stock");
  }
  return res.json();
}

export async function discardStockSheet(id: number): Promise<StockSheet> {
  const res = await apiFetch(`${BASE}/${id}/discard`, { method: "PATCH", headers: getAuthHeaders() });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Error al descartar el stock");
  }
  return res.json();
}

export async function getStockMovements(id: number): Promise<StockMovement[]> {
  const res = await apiFetch(`${BASE}/${id}/movements`, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error("Error al obtener el historial de movimientos");
  return res.json();
}

export async function recommendStock(pieceId: number, materialId: number): Promise<StockRecommendation[]> {
  const res = await apiFetch(`${BASE}/recommendations`, {
    method: "POST",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ piece_id: pieceId, material_id: materialId }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "No se encontró stock disponible para esta pieza");
  }
  return res.json();
}

export async function reserveStock(
  stockId: number,
  data: { piece_id: number; material_id: number; quotation_id: number; quotation_item_id?: number }
): Promise<StockReservation> {
  const res = await apiFetch(`${BASE}/${stockId}/reserve`, {
    method: "POST",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Error al reservar el material");
  }
  return res.json();
}

export async function releaseReservation(reservationId: number): Promise<StockReservation> {
  const res = await apiFetch(`${BASE}/reservations/${reservationId}/release`, {
    method: "POST",
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Error al liberar la reserva");
  }
  return res.json();
}

export async function confirmCut(reservationId: number): Promise<ConfirmCutResult> {
  const res = await apiFetch(`${BASE}/reservations/${reservationId}/confirm-cut`, {
    method: "POST",
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Error al confirmar el corte");
  }
  return res.json();
}
