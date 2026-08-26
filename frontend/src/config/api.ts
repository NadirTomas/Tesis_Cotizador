// URL del backend - siempre HTTPS (especialmente en producción)
const envUrl = import.meta.env.VITE_API_BASE_URL;
// Producción SIEMPRE debe setear VITE_API_BASE_URL (Railway ya lo hace) --
// este fallback es solo para levantar el backend local en dev, nunca debe
// apuntar a una URL de producción hardcodeada (quedó apuntando a un
// dominio de Railway que ya no existe, ver README.md para el puerto real).
const defaultUrl = "http://localhost:8000";
let baseUrl = envUrl || defaultUrl;

// Si el frontend está en HTTPS (producción), fuerza HTTPS en el backend también
if (typeof window !== "undefined" && window.location.protocol === "https:") {
  baseUrl = baseUrl.replace(/^http:/, "https:");
}

export const API_BASE_URL = baseUrl;

// Debug -- solo en desarrollo, no debe correr en el build de producción.
if (import.meta.env.DEV && typeof window !== "undefined") {
  console.log("[API Config] Frontend protocol:", window.location.protocol);
  console.log("[API Config] VITE_API_BASE_URL:", envUrl);
  console.log("[API Config] Final API_BASE_URL:", API_BASE_URL);
}
