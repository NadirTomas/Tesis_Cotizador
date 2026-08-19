import { API_BASE_URL } from "../config/api";

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
  number: string;
  client_id: number;
  issue_date: string;
  due_date?: string;
  currency?: string;
  exchange_rate?: number;
  notes?: string;
  status?: string;
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

const BASE = `${API_BASE_URL}/quotations`;
const ITEMS_BASE = `${API_BASE_URL}/quotation-items`;

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem("auth_token");
  return {
    "Content-Type": "application/json",
    ...(token && { "Authorization": `Bearer ${token}` }),
  };
}

export async function getQuotations(): Promise<Quotation[]> {
  const res = await fetch(BASE);
  if (!res.ok) throw new Error("Error al obtener cotizaciones");
  return res.json();
}

export async function getQuotation(id: number): Promise<Quotation> {
  const res = await fetch(`${BASE}/${id}`);
  if (!res.ok) throw new Error("Error al obtener cotización");
  return res.json();
}

export async function createQuotation(data: QuotationCreate): Promise<Quotation> {
  const res = await fetch(BASE, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Error al crear cotización");
  return res.json();
}

export async function getQuotationItems(quotationId: number): Promise<QuotationItem[]> {
  const res = await fetch(`${ITEMS_BASE}/quotation/${quotationId}`);
  if (!res.ok) throw new Error("Error al obtener ítems de cotización");
  return res.json();
}

export async function createQuotationItem(data: QuotationItemCreate): Promise<QuotationItem> {
  const res = await fetch(ITEMS_BASE, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Error al crear ítem de cotización");
  return res.json();
}

export function getQuotationPdfUrl(id: number): string {
  return `${BASE}/${id}/pdf`;
}

export async function updateQuotationStatus(id: number, status: string): Promise<Quotation> {
  const res = await fetch(`${BASE}/${id}/status`, {
    method: "PATCH",
    headers: getAuthHeaders(),
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error("Error al actualizar estado");
  return res.json();
}

export async function deleteQuotationItem(itemId: number): Promise<void> {
  const res = await fetch(`${ITEMS_BASE}/${itemId}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Error al eliminar ítem");
}
