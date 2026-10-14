import { API_BASE_URL } from "../config/api";
import { apiFetch, getAuthHeaders, parseErrorDetail } from "./apiClient";

export type DeliveryNoteStatus = "DRAFT" | "ISSUED" | "VOIDED";
export type DeliveryState = "NONE" | "PARTIAL" | "COMPLETE";

export interface DeliveryNoteItem {
  id: number;
  quotation_item_id: number;
  piece_id: number | null;
  piece_name: string;
  piece_description: string | null;
  quantity: number;
  unit: string;
}

export interface DeliveryNote {
  id: number;
  company_id: number;
  quotation_id: number;
  client_id: number;
  number: string | null;
  status: DeliveryNoteStatus;
  issue_date: string | null;
  notes: string | null;
  quotation_number: string;
  client_name: string;
  client_tax_id: string | null;
  client_address: string | null;
  issued_at: string | null;
  voided_at: string | null;
  void_reason: string | null;
  created_at: string;
  updated_at: string;
  total_units: number;
  /** Solo para borradores: ¿el corte de todas sus líneas está confirmado? (condición para emitir). null si no aplica. */
  cut_confirmed: boolean | null;
  cut_pending_pieces: string[];
  items: DeliveryNoteItem[];
}

export interface DeliveryNoteSummary {
  id: number;
  quotation_id: number;
  number: string | null;
  status: DeliveryNoteStatus;
  issue_date: string | null;
  quotation_number: string;
  client_name: string;
  total_units: number;
  created_at: string;
}

export interface DeliveryStatusLine {
  quotation_item_id: number;
  piece_id: number | null;
  piece_name: string;
  piece_description: string | null;
  unit: string;
  quoted: number;
  delivered: number;
  pending: number;
  cut_confirmed: boolean;
}

export interface DeliveryStatus {
  quotation_id: number;
  quotation_number: string;
  quotation_status: string;
  client_name: string;
  cut_confirmed: boolean;
  eligible: boolean;
  ineligible_reason: string | null;
  state: DeliveryState;
  total_quoted: number;
  total_delivered: number;
  total_pending: number;
  items: DeliveryStatusLine[];
}

export interface DeliveryNoteLineInput {
  quotation_item_id: number;
  quantity: number;
}

const BASE = `${API_BASE_URL}/delivery-notes`;

async function request<T>(url: string, init: RequestInit, fallback: string): Promise<T> {
  const res = await apiFetch(url, init);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(parseErrorDetail(err) ?? fallback);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: getAuthHeaders({ "Content-Type": "application/json" }),
  ...(body !== undefined && { body: JSON.stringify(body) }),
});

export const getDeliveryNotes = () =>
  request<DeliveryNoteSummary[]>(BASE, { headers: getAuthHeaders() }, "Error al obtener los remitos");

export const getDeliveryNote = (id: number) =>
  request<DeliveryNote>(`${BASE}/${id}`, { headers: getAuthHeaders() }, "Error al obtener el remito");

export const getQuotationDeliveryStatus = (quotationId: number) =>
  request<DeliveryStatus>(`${BASE}/quotation/${quotationId}/status`, { headers: getAuthHeaders() }, "Error al obtener el estado de entrega");

export const getQuotationDeliveryNotes = (quotationId: number) =>
  request<DeliveryNoteSummary[]>(`${BASE}/quotation/${quotationId}`, { headers: getAuthHeaders() }, "Error al obtener los remitos de la cotización");

export const createDeliveryNote = (data: { quotation_id: number; notes?: string; items: DeliveryNoteLineInput[] }) =>
  request<DeliveryNote>(BASE, json("POST", data), "Error al crear el remito");

export const updateDeliveryNote = (id: number, data: { notes: string | null; items: DeliveryNoteLineInput[] }) =>
  request<DeliveryNote>(`${BASE}/${id}`, json("PUT", data), "Error al guardar el borrador");

export const deleteDeliveryNote = (id: number) =>
  request<void>(`${BASE}/${id}`, { method: "DELETE", headers: getAuthHeaders() }, "Error al eliminar el borrador");

export const issueDeliveryNote = (id: number) =>
  request<DeliveryNote>(`${BASE}/${id}/issue`, json("POST"), "Error al emitir el remito");

export const voidDeliveryNote = (id: number, reason: string) =>
  request<DeliveryNote>(`${BASE}/${id}/void`, json("POST", { reason }), "Error al anular el remito");

export const getDeliveryNotePdfUrl = (id: number): string => `${BASE}/${id}/pdf`;
