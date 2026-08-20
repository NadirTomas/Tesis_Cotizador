import { useEffect, useState } from "react";
import { Box, type SxProps, type Theme } from "@mui/material";
import { apiFetch, getAuthHeaders } from "../services/apiClient";

interface AuthedImageProps {
  src: string;
  alt: string;
  sx?: SxProps<Theme>;
  fallback?: React.ReactNode;
}

/**
 * <img> para recursos protegidos (preview de pieza, logo de empresa): un
 * <img src=...> normal no puede mandar Authorization/X-Company-Id, así que
 * se pide el blob a mano y se muestra como object URL.
 */
export default function AuthedImage({ src, alt, sx, fallback = null }: AuthedImageProps) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    setBlobUrl(null);
    apiFetch(src, { headers: getAuthHeaders() })
      .then((res) => (res.ok ? res.blob() : Promise.reject()))
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
