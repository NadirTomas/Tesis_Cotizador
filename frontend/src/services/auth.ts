import { API_BASE_URL } from "../config/api";

interface TokenResponse {
  access_token: string;
  token_type: string;
}

export async function loginRequest(email: string, password: string): Promise<TokenResponse> {
  const res = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Error al iniciar sesión");
  }
  return res.json();
}
