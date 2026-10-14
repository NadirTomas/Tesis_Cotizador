export const CLIENT_NAME_NUMERIC_ERROR = "El nombre debe incluir al menos una letra (no puede ser solo números).";

export function getClientNameError(name: string): string | null {
  const trimmed = name.trim();
  if (!trimmed) return null;
  return /\p{L}/u.test(trimmed) ? null : CLIENT_NAME_NUMERIC_ERROR;
}
