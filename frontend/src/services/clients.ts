import { API_BASE_URL } from "../config/api";

export interface Client {
  id: number;
  name: string;
  cuit_cuil: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  notes: string | null;
  active: boolean;
  created_at: string;
}

export interface ClientCreate {
  name: string;
  cuit_cuil?: string;
  phone?: string;
  email?: string;
  address?: string;
  notes?: string;
}

export interface ClientUpdate {
  name?: string;
  cuit_cuil?: string;
  phone?: string;
  email?: string;
  address?: string;
  notes?: string;
}

const BASE = `${API_BASE_URL}/clients`;

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem("auth_token");
  return {
    "Content-Type": "application/json",
    ...(token && { "Authorization": `Bearer ${token}` }),
  };
}

export async function getClients(): Promise<Client[]> {
  const res = await fetch(BASE);
  if (!res.ok) throw new Error("Error al obtener clientes");
  return res.json();
}

export async function createClient(data: ClientCreate): Promise<Client> {
  const res = await fetch(BASE, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Error al crear cliente");
  return res.json();
}

export async function updateClient(id: number, data: ClientUpdate): Promise<Client> {
  const res = await fetch(`${BASE}/${id}`, {
    method: "PUT",
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Error al actualizar cliente");
  return res.json();
}

export async function deleteClient(id: number): Promise<void> {
  const res = await fetch(`${BASE}/${id}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Error al eliminar cliente");
}
