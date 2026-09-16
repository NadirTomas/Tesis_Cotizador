import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import HomePage from "./HomePage";
import { formatLongDate } from "../utils/date";

vi.mock("react-router-dom", () => ({
  useNavigate: () => vi.fn(),
}));

const getStats = vi.fn();
vi.mock("../services/quotations", () => ({
  getStats: () => getStats(),
}));

const getClients = vi.fn();
vi.mock("../services/clients", () => ({
  getClients: () => getClients(),
}));

describe("HomePage", () => {
  beforeEach(() => {
    // Fecha fija (no depende de qué día sea hoy cuando corran los tests).
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-15T12:00:00"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders today's date, generated dynamically, under the dashboard title", () => {
    getStats.mockReturnValue(new Promise(() => {})); // nunca resuelve, no importa para este test
    getClients.mockReturnValue(new Promise(() => {}));

    render(<HomePage />);

    expect(screen.getByText("Panel Principal")).toBeInTheDocument();
    expect(screen.getByText(formatLongDate(new Date("2026-09-15T12:00:00")))).toBeInTheDocument();
  });
});
