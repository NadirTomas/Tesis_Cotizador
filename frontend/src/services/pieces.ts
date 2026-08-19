import { API_BASE_URL } from "../config/api";

export interface Piece {
  id: number;
  name: string;
  description: string | null;
  material_id: number | null;
  dxf_filename: string | null;
  has_dxf: boolean;
  has_preview: boolean;
  length_cut_mm: number | null;
  area_mm2: number | null;
  active: boolean;
  created_at: string;
}

export function getPiecePreviewUrl(id: number): string {
  return `${API_BASE_URL}/pieces/${id}/preview`;
}

export interface PieceCreate {
  name: string;
  description?: string;
  material_id?: number;
}

export interface PieceUpdate {
  name?: string;
  description?: string;
  material_id?: number;
  active?: boolean;
}

export interface DxfAnalysisResult {
  length_cut_mm: number;
  area_mm2: number;
}

const BASE = `${API_BASE_URL}/pieces`;

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem("auth_token");
  return {
    "Content-Type": "application/json",
    ...(token && { "Authorization": `Bearer ${token}` }),
  };
}

function getAuthHeadersMultipart(): Record<string, string> {
  const token = localStorage.getItem("auth_token");
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

export async function getPieces(): Promise<Piece[]> {
  const res = await fetch(BASE);
  if (!res.ok) throw new Error("Error al obtener piezas");
  return res.json();
}

export async function getPiece(id: number): Promise<Piece> {
  const res = await fetch(`${BASE}/${id}`);
  if (!res.ok) throw new Error("Error al obtener pieza");
  return res.json();
}

export async function createPiece(data: PieceCreate): Promise<Piece> {
  const res = await fetch(BASE, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Error al crear pieza");
  return res.json();
}

export async function updatePiece(id: number, data: PieceUpdate): Promise<Piece> {
  const res = await fetch(`${BASE}/${id}`, {
    method: "PUT",
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Error al actualizar pieza");
  return res.json();
}

export async function deletePiece(id: number): Promise<void> {
  const res = await fetch(`${BASE}/${id}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Error al eliminar pieza");
}

export async function uploadDxf(id: number, file: File): Promise<Piece> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${BASE}/${id}/upload-dxf`, {
    method: "POST",
    headers: getAuthHeadersMultipart(),
    body: formData,
  });
  if (!res.ok) throw new Error("Error al subir DXF");
  return res.json();
}
