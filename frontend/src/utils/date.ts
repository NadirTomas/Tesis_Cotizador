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
