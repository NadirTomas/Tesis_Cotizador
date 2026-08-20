import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "./AuthContext";

vi.mock("../services/auth", () => ({
  refreshTokenRequest: vi.fn().mockRejectedValue(new Error("not used in these tests")),
}));

function Probe() {
  const auth = useAuth();
  return (
    <div>
      <span data-testid="isAuthenticated">{String(auth.isAuthenticated)}</span>
      <span data-testid="hasCompany">{String(auth.hasCompany)}</span>
      <span data-testid="companyName">{auth.companyName ?? ""}</span>
      <button onClick={() => auth.login("tok-123")}>login</button>
      <button onClick={() => auth.selectCompany(1, "owner", "Acme")}>selectCompany</button>
      <button onClick={() => auth.clearCompany()}>clearCompany</button>
      <button onClick={() => auth.logout()}>logout</button>
    </div>
  );
}

describe("AuthContext", () => {
  beforeEach(() => localStorage.clear());

  it("starts unauthenticated with no stored token", () => {
    render(<AuthProvider><Probe /></AuthProvider>);
    expect(screen.getByTestId("isAuthenticated").textContent).toBe("false");
  });

  it("login persists the token and flips isAuthenticated", () => {
    render(<AuthProvider><Probe /></AuthProvider>);
    act(() => screen.getByText("login").click());
    expect(screen.getByTestId("isAuthenticated").textContent).toBe("true");
    expect(localStorage.getItem("auth_token")).toBe("tok-123");
  });

  it("selectCompany persists company info and clearCompany removes it", () => {
    render(<AuthProvider><Probe /></AuthProvider>);
    act(() => screen.getByText("selectCompany").click());
    expect(screen.getByTestId("hasCompany").textContent).toBe("true");
    expect(screen.getByTestId("companyName").textContent).toBe("Acme");
    expect(localStorage.getItem("company_id")).toBe("1");

    act(() => screen.getByText("clearCompany").click());
    expect(screen.getByTestId("hasCompany").textContent).toBe("false");
    expect(localStorage.getItem("company_id")).toBeNull();
  });

  it("logout clears token and company state", () => {
    render(<AuthProvider><Probe /></AuthProvider>);
    act(() => screen.getByText("login").click());
    act(() => screen.getByText("selectCompany").click());

    act(() => screen.getByText("logout").click());

    expect(screen.getByTestId("isAuthenticated").textContent).toBe("false");
    expect(screen.getByTestId("hasCompany").textContent).toBe("false");
    expect(localStorage.getItem("auth_token")).toBeNull();
    expect(localStorage.getItem("company_id")).toBeNull();
  });
});
