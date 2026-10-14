import type { DeliveryNoteStatus, DeliveryState } from "../services/deliveryNotes";

export const NOTE_STATUS: Record<DeliveryNoteStatus, { label: string; color: "warning" | "success" | "error" }> = {
  DRAFT: { label: "Borrador", color: "warning" },
  ISSUED: { label: "Emitido", color: "success" },
  VOIDED: { label: "Anulado", color: "error" },
};

export const DELIVERY_STATE: Record<DeliveryState, { label: string; color: "default" | "info" | "success" }> = {
  NONE: { label: "Sin entregas", color: "default" },
  PARTIAL: { label: "Entrega parcial", color: "info" },
  COMPLETE: { label: "Entrega completa", color: "success" },
};

export const CUT_PENDING_HINT =
  "Podés guardar el borrador, pero no se puede emitir hasta que el corte esté confirmado (en la cotización: reservar material y confirmar el corte)."

export interface ParsedQuantity {
  /** Cantidad a entregar; null si la línea no se entrega (vacío o 0). */
  quantity: number | null;
  error: string | null;
}

/**
 * Valida lo que el usuario escribió en "Entregar ahora". Nunca corrige el valor
 * por su cuenta: un negativo o un decimal se informa como error, no se
 * convierte en otro número. Vacío o 0 significa "esta línea no se entrega".
 */
export function parseDeliveryQuantity(raw: string, pending: number): ParsedQuantity {
  const text = raw.trim();
  if (text === "") return { quantity: null, error: null };
  if (!/^-?\d+$/.test(text)) return { quantity: null, error: "Ingresá un número entero." };
  const value = Number(text);
  if (value < 0) return { quantity: null, error: "La cantidad no puede ser negativa." };
  if (value === 0) return { quantity: null, error: null };
  if (value > pending) return { quantity: null, error: `No puede superar lo pendiente (${pending}).` };
  return { quantity: value, error: null };
}

export function formatDate(iso: string | null): string {
  return iso ? new Date(iso).toLocaleDateString("es-AR") : "—";
}
