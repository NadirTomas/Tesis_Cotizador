import { useEffect, useState } from "react";
import { Box, type SxProps, type Theme } from "@mui/material";
import { apiFetch, getAuthHeaders } from "../services/apiClient";

interface AuthedImageProps {
  src: string;
  alt: string;
  sx?: SxProps<Theme>;
  fallback?: React.ReactNode;
}

// Una lista con muchas piezas monta un AuthedImage por fila, y cada uno
// disparaba su fetch autenticado de inmediato — con ~17 piezas eso son 17
// pedidos concurrentes, suficientes para agotar el pool de conexiones a la
// base (incidente en producción 2026-09-26). Se limita a MAX_CONCURRENT en
// vuelo por vez; el resto espera su turno en cola.
const MAX_CONCURRENT = 4;
let running = 0;
const queue: Array<() => void> = [];

function runWithLimit<T>(task: () => Promise<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    const run = () => {
      running++;
      task()
        .then(resolve, reject)
        .finally(() => {
          running--;
          const next = queue.shift();
          if (next) next();
        });
    };
    if (running < MAX_CONCURRENT) run();
    else queue.push(run);
  });
}

/**
 * <img> para recursos protegidos (preview de pieza, logo de empresa): un
 * <img src=...> normal no puede mandar Authorization/X-Company-Id, así que
 * se pide el blob a mano y se muestra como object URL.
 */
export default function AuthedImage({ src, alt, sx, fallback = null }: AuthedImageProps) {
  const [loadedSrc, setLoadedSrc] = useState(src);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);

  // Reseteo del blob anterior al cambiar de src: se hace durante el render
  // (no en el efecto) siguiendo el patrón que React recomienda para "ajustar
  // estado cuando cambia una prop" — evita el error de lint de setState
  // síncrono dentro de un efecto sin necesitar un remount por key.
  if (loadedSrc !== src) {
    setLoadedSrc(src);
    setBlobUrl(null);
  }

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    runWithLimit(() => apiFetch(src, { headers: getAuthHeaders() }).then((res) => (res.ok ? res.blob() : Promise.reject())))
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setBlobUrl(objectUrl);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [src]);

  if (!blobUrl) return <>{fallback}</>;
  return <Box component="img" src={blobUrl} alt={alt} sx={sx} />;
}
