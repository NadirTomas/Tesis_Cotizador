import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch, getAuthHeaders } from "./apiClient";

describe("getAuthHeaders", () => {
  beforeEach(() => localStorage.clear());

  it("returns no auth headers when nothing is stored", () => {
    expect(getAuthHeaders()).toEqual({});
  });

  it("includes Authorization when a token is stored", () => {
    localStorage.setItem("auth_token", "abc123");
    expect(getAuthHeaders()).toEqual({ Authorization: "Bearer abc123" });
  });

  it("includes X-Company-Id when a company is stored", () => {
    localStorage.setItem("auth_token", "abc123");
    localStorage.setItem("company_id", "7");
    expect(getAuthHeaders()).toEqual({ Authorization: "Bearer abc123", "X-Company-Id": "7" });
  });

  it("merges extra headers passed in", () => {
    expect(getAuthHeaders({ "Content-Type": "application/json" })).toEqual({
      "Content-Type": "application/json",
    });
  });
});

describe("apiFetch", () => {
  const originalLocation = window.location;

  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal("fetch", vi.fn());
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...originalLocation, pathname: "/quotations", href: "" },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    Object.defineProperty(window, "location", { configurable: true, value: originalLocation });
  });

  it("returns the response as-is on success", async () => {
    const mockRes = new Response(null, { status: 200 });
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(mockRes);
    const res = await apiFetch("/anything");
    expect(res.status).toBe(200);
  });

  it("clears session storage and redirects to /login on 401", async () => {
    localStorage.setItem("auth_token", "abc123");
    localStorage.setItem("company_id", "7");
    const mockRes = new Response(null, { status: 401 });
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(mockRes);

    await apiFetch("/anything");

    expect(localStorage.getItem("auth_token")).toBeNull();
    expect(localStorage.getItem("company_id")).toBeNull();
    expect(window.location.href).toBe("/login");
  });

  it("does not redirect if already on /login", async () => {
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...originalLocation, pathname: "/login", href: "" },
    });
    const mockRes = new Response(null, { status: 401 });
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(mockRes);

    await apiFetch("/anything");

    expect(window.location.href).toBe("");
  });
});
