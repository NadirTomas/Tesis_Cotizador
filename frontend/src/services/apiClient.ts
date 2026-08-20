const AUTH_TOKEN_KEY = "auth_token";
const COMPANY_ID_KEY = "company_id";

export function getAuthHeaders(extra?: Record<string, string>): Record<string, string> {
  const token = localStorage.getItem(AUTH_TOKEN_KEY);
  const companyId = localStorage.getItem(COMPANY_ID_KEY);
  return {
    ...extra,
    ...(token && { Authorization: `Bearer ${token}` }),
    ...(companyId && { "X-Company-Id": companyId }),
  };
}

/**
 * Wrapper de fetch: si el backend responde 401 (sesión vencida o inválida),
 * limpia el token y manda al login en vez de dejar la app en un estado roto.
 */
export async function apiFetch(input: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(input, init);
  if (res.status === 401 && window.location.pathname !== "/login") {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(COMPANY_ID_KEY);
    window.location.href = "/login";
  }
  return res;
}
