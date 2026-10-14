import { BUSINESS_TIMEZONE } from "../config/business";

/**
 * Formatea una fecha en español (es-AR), estilo "Martes, 15 de septiembre
 * de 2026". Recibe la fecha como parámetro (default: la actual) para poder
 * testearla sin mockear el reloj global.
 */
export function formatLongDate(date: Date = new Date()): string {
  const formatted = new Intl.DateTimeFormat("es-AR", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(date);
  return formatted.charAt(0).toUpperCase() + formatted.slice(1);
}

/**
 * "Hoy" como "YYYY-MM-DD" en la zona horaria del negocio (no la del navegador
 * ni la del servidor). Es la misma referencia que usa el backend para validar.
 */
export function todayInBusinessTimezone(now: Date = new Date(), timeZone: string = BUSINESS_TIMEZONE): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now);
}
