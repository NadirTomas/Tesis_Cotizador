// Misma zona que BUSINESS_TIMEZONE del backend: define qué es "hoy" para las reglas
// de fechas (ej. la emisión de una cotización no puede ser anterior a hoy), sin
// depender de la zona del navegador ni de la del servidor.
export const BUSINESS_TIMEZONE: string =
  import.meta.env.VITE_BUSINESS_TIMEZONE || "America/Argentina/Buenos_Aires";
