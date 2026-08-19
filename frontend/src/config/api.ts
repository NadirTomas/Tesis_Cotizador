// URL del backend - siempre HTTPS (especialmente en producción)
const envUrl = import.meta.env.VITE_API_BASE_URL;
const defaultUrl = "https://backend-production-3f21c.up.railway.app";
let baseUrl = envUrl || defaultUrl;

// Si el frontend está en HTTPS (producción), fuerza HTTPS en el backend también
if (typeof window !== "undefined" && window.location.protocol === "https:") {
  baseUrl = baseUrl.replace(/^http:/, "https:");
}

export const API_BASE_URL = baseUrl;

// Debug
if (typeof window !== "undefined") {
  console.log("[API Config] Frontend protocol:", window.location.protocol);
  console.log("[API Config] VITE_API_BASE_URL:", envUrl);
  console.log("[API Config] Final API_BASE_URL:", API_BASE_URL);
}
