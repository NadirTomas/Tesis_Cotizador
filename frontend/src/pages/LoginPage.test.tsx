import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../context/AuthContext";
import LoginPage from "./LoginPage";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}));

const loginRequest = vi.fn();
vi.mock("../services/auth", () => ({
  loginRequest: (...args: unknown[]) => loginRequest(...args),
  refreshTokenRequest: vi.fn().mockRejectedValue(new Error("not used")),
}));

const getMyCompanies = vi.fn();
vi.mock("../services/companies", () => ({
  getMyCompanies: () => getMyCompanies(),
}));

function renderLoginPage() {
  return render(
    <AuthProvider>
      <LoginPage />
    </AuthProvider>
  );
}

describe("LoginPage", () => {
  beforeEach(() => {
    localStorage.clear();
    mockNavigate.mockClear();
    loginRequest.mockReset();
    getMyCompanies.mockReset();
  });

  it("logs in and goes straight to / when the user has exactly one active company", async () => {
    const user = userEvent.setup();
    loginRequest.mockResolvedValue({ access_token: "tok-123", token_type: "bearer" });
    getMyCompanies.mockResolvedValue([
      { id: 1, company_name: "Acme", role: "owner", is_active: true, member_is_active: true },
    ]);

    renderLoginPage();
    await user.type(screen.getByLabelText(/email/i), "demo@test.com");
    await user.type(screen.getByLabelText(/contraseña/i), "Password1!");
    await user.click(screen.getByRole("button", { name: /ingresar/i }));

    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/"));
    expect(loginRequest).toHaveBeenCalledWith("demo@test.com", "Password1!");
    expect(localStorage.getItem("auth_token")).toBe("tok-123");
  });

  it("rejects a deactivated employee even though the login credentials are valid", async () => {
    const user = userEvent.setup();
    loginRequest.mockResolvedValue({ access_token: "tok-123", token_type: "bearer" });
    getMyCompanies.mockResolvedValue([
      { id: 1, company_name: "Acme", role: "employee", is_active: true, member_is_active: false },
    ]);

    renderLoginPage();
    await user.type(screen.getByLabelText(/email/i), "empleado@test.com");
    await user.type(screen.getByLabelText(/contraseña/i), "Password1!");
    await user.click(screen.getByRole("button", { name: /ingresar/i }));

    expect(await screen.findByText(/acceso.*desactivado/i)).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalledWith("/");
    expect(mockNavigate).not.toHaveBeenCalledWith("/companies/new");
    expect(localStorage.getItem("auth_token")).toBeNull();
  });

  it("sends the user to create a company when they have none", async () => {
    const user = userEvent.setup();
    loginRequest.mockResolvedValue({ access_token: "tok-123", token_type: "bearer" });
    getMyCompanies.mockResolvedValue([]);

    renderLoginPage();
    await user.type(screen.getByLabelText(/email/i), "demo@test.com");
    await user.type(screen.getByLabelText(/contraseña/i), "Password1!");
    await user.click(screen.getByRole("button", { name: /ingresar/i }));

    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/companies/new"));
  });

  it("shows an error message when login fails", async () => {
    const user = userEvent.setup();
    loginRequest.mockRejectedValue(new Error("Credenciales incorrectas"));

    renderLoginPage();
    await user.type(screen.getByLabelText(/email/i), "demo@test.com");
    await user.type(screen.getByLabelText(/contraseña/i), "wrong");
    await user.click(screen.getByRole("button", { name: /ingresar/i }));

    expect(await screen.findByText("Credenciales incorrectas")).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
