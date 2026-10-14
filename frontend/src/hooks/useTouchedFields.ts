import { useCallback, useState } from "react";

/**
 * Lleva la cuenta de qué campos ya interactuó el usuario, para no mostrar
 * errores de validación en un formulario recién abierto. Un campo cuenta como
 * tocado al modificarlo, al salir de él (blur) o al intentar enviar.
 */
export function useTouchedFields() {
  const [touched, setTouched] = useState<ReadonlySet<string>>(() => new Set());

  const touch = useCallback((field: string) => {
    setTouched((prev) => (prev.has(field) ? prev : new Set(prev).add(field)));
  }, []);

  const touchAll = useCallback((fields: readonly string[]) => {
    setTouched(new Set(fields));
  }, []);

  const reset = useCallback(() => setTouched(new Set()), []);

  const isTouched = useCallback((field: string) => touched.has(field), [touched]);

  return { touch, touchAll, reset, isTouched };
}
