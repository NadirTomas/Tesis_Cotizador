import type { NestingResult } from "../services/nesting";

export interface NestingCartItem {
  piece_id: number;
  quantity: number;
}

export interface NestingDraft {
  cart: NestingCartItem[];
  sheetW: number;
  sheetH: number;
  margin: number;
  allowRotation: boolean;
  result: NestingResult | null;
  activeSheet: number;
}

interface StoredDraft {
  companyId: number;
  draft: NestingDraft;
}

// Borrador temporal de la sesión del navegador (se pierde al cerrar la pestaña):
// evita perder el trabajo al navegar entre secciones. No es un "proyecto guardado".
export const NESTING_DRAFT_KEY = "nesting_draft";

const isFiniteNumber = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

function isValidDraft(d: unknown): d is NestingDraft {
  if (!d || typeof d !== "object") return false;
  const x = d as Record<string, unknown>;
  return (
    Array.isArray(x.cart) &&
    x.cart.every((i) => i && isFiniteNumber(i.piece_id) && isFiniteNumber(i.quantity) && i.quantity >= 1) &&
    isFiniteNumber(x.sheetW) &&
    isFiniteNumber(x.sheetH) &&
    isFiniteNumber(x.margin) &&
    typeof x.allowRotation === "boolean" &&
    isFiniteNumber(x.activeSheet) &&
    (x.result === null || (typeof x.result === "object" && Array.isArray((x.result as NestingResult).sheets)))
  );
}

export function loadNestingDraft(companyId: number | null): NestingDraft | null {
  if (companyId === null) return null;
  try {
    const raw = sessionStorage.getItem(NESTING_DRAFT_KEY);
    if (!raw) return null;
    const stored = JSON.parse(raw) as Partial<StoredDraft>;
    if (stored.companyId !== companyId || !isValidDraft(stored.draft)) return null;
    return stored.draft;
  } catch {
    return null;
  }
}

export function saveNestingDraft(companyId: number | null, draft: NestingDraft): void {
  if (companyId === null) return;
  try {
    sessionStorage.setItem(NESTING_DRAFT_KEY, JSON.stringify({ companyId, draft } satisfies StoredDraft));
  } catch {
    // sessionStorage no disponible o lleno: se sigue funcionando sin persistencia.
  }
}

export function clearNestingDraft(): void {
  try {
    sessionStorage.removeItem(NESTING_DRAFT_KEY);
  } catch {
    // nada que limpiar
  }
}
