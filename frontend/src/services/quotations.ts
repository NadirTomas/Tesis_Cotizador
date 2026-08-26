import { API_BASE_URL } from "../config/api";
import { apiFetch, getAuthHeaders } from "./apiClient";

export interface Quotation {
  id: number;
  number: string;
  client_id: number;
  issue_date: string;
  due_date: string | null;
  currency: string;
  exchange_rate: number | null;
  notes: string | null;
  status: string;
  total_ars: number;
  total_usd: number;
  created_at: string;
  updated_at: string;
}

export interface QuotationCreate {
  client_id: number;
  issue_date: string;
  due_date?: string;
  currency?: string;
  exchange_rate?: number;
  notes?: string;
}

export interface QuotationItem {
  id: number;
  quotation_id: number;
  piece_id: number;
  material_id: number;
  quantity: number;
  margin_percent: number;
  cost_material_ars: number;
  cost_machine_ars: number;
  cost_labor_ars: number;
  unit_price_ars: number;
  total_price_ars: number;
  created_at: string;
}

export interface QuotationItemCreate {
  quotation_id: number;
  piece_id: number;
  material_id: number;
  quantity: number;
  margin_percent: number;
}

export interface QuotationItemUpdate {
  quantity?: number;
  margin_percent?: number;
}

export interface QuotationEvent {
  id: number;
  event_type: string;
  description: string;
  created_by_id: number | null;
  created_by_email: string | null;
  created_at: string;
}

const BASE = `${API_BASE_URL}/quotations`;
const ITEMS_BASE = `${API_BASE_URL}/quotation-items`;

export async function getQuotations(): Promise<Quotation[]> {
  const res = await apiFetch(BASE, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error("Error al obtener cotizaciones");
  return res.json();
}

export async function getQuotation(id: number): Promise<Quotation> {
  const res = await apiFetch(`${BASE}/${id}`, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error("Error al obtener cotización");
  return res.json();
}

export async function createQuotation(data: QuotationCreate): Promise<Quotation> {
  const res = await apiFetch(BASE, {
    method: "POST",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Error al crear cotización");
  return res.json();
}

export async function getQuotationItems(quotationId: number): Promise<QuotationItem[]> {
  const res = await apiFetch(`${ITEMS_BASE}/quotation/${quotationId}`, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error("Error al obtener ítems de cotización");
  return res.json();
}

export async function createQuotationItem(data: QuotationItemCreate): Promise<QuotationItem> {
  const res = await apiFetch(ITEMS_BASE, {
    method: "POST",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Error al crear ítem de cotización");
  return res.json();
}

export async function updateQuotationItem(itemId: number, data: QuotationItemUpdate): Promise<QuotationItem> {
  const res = await apiFetch(`${ITEMS_BASE}/${itemId}`, {
    method: "PUT",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Error al actualizar ítem de cotización");
  return res.json();
}

export function getQuotationPdfUrl(id: number): string {
  return `${BASE}/${id}/pdf`;
}

export async function updateQuotationStatus(id: number, status: string): Promise<Quotation> {
  const res = await apiFetch(`${BASE}/${id}/status`, {
    method: "PATCH",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error("Error al actualizar estado");
  return res.json();
}

export async function deleteQuotationItem(itemId: number): Promise<void> {
  const res = await apiFetch(`${ITEMS_BASE}/${itemId}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Error al eliminar ítem");
}

export async function getQuotationEvents(id: number): Promise<QuotationEvent[]> {
  const res = await apiFetch(`${BASE}/${id}/events`, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error("Error al obtener el historial");
  return res.json();
}
