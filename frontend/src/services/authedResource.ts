import { apiFetch, getAuthHeaders } from "./apiClient";

/**
 * Abre un recurso protegido (PDF) en una pestaña nueva. window.open con la
 * URL directa no manda Authorization/X-Company-Id, así que se descarga el
 * blob primero.
 */
export async function openAuthedResource(url: string): Promise<void> {
  const res = await apiFetch(url, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error("No se pudo abrir el archivo");
  const blob = await res.blob();
  const blobUrl = URL.createObjectURL(blob);
  window.open(blobUrl, "_blank");
}
