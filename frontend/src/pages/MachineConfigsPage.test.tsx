import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import MachineConfigsPage from "./MachineConfigsPage";

vi.mock("../context/AuthContext", () => ({ useAuth: () => ({ companyRole: "owner" }) }));
vi.mock("../services/machineConfigs", () => ({
  getMachineConfigs: () => Promise.resolve([]),
  createMachineConfig: vi.fn(),
  updateMachineConfig: vi.fn(),
  deleteMachineConfig: vi.fn(),
}));
vi.mock("../services/materials", () => ({
  getMaterials: () =>
    Promise.resolve([{ id: 1, name: "Sae 2020", thickness_mm: 3, sheet_width_mm: 1500, sheet_height_mm: 3000 }]),
}));

describe("MachineConfigsPage numeric inputs", () => {
  it("opens a fresh form without any validation error, with Save disabled", async () => {
    const user = userEvent.setup();
    render(<MachineConfigsPage />);
    await user.click(await screen.findByRole("button", { name: /crear configuración/i }));

    expect(screen.queryByText("Debe ser mayor a 0.")).not.toBeInTheDocument();
    expect(screen.getByLabelText(/velocidad de corte/i)).toHaveAttribute("aria-invalid", "false");
    expect(screen.getByLabelText(/costo por hora/i)).toHaveAttribute("aria-invalid", "false");
    expect(screen.getByRole("button", { name: "Guardar" })).toBeDisabled();
  });

  it("shows the error only after the user edits or leaves the field", async () => {
    const user = userEvent.setup();
    render(<MachineConfigsPage />);
    await user.click(await screen.findByRole("button", { name: /crear configuración/i }));

    const speed = screen.getByLabelText(/velocidad de corte/i);
    const cost = screen.getByLabelText(/costo por hora/i);
    await user.click(speed);
    await user.tab();
    expect(speed).toHaveAttribute("aria-invalid", "true");
    expect(cost).toHaveAttribute("aria-invalid", "false");
    expect(screen.getAllByText("Debe ser mayor a 0.")).toHaveLength(1);
  });


  it("never keeps a negative value and blocks saving until speed and cost are > 0", async () => {
    const user = userEvent.setup();
    render(<MachineConfigsPage />);
    await user.click(await screen.findByRole("button", { name: /crear configuración/i }));

    const speed = screen.getByLabelText(/velocidad de corte/i) as HTMLInputElement;
    const cost = screen.getByLabelText(/costo por hora/i) as HTMLInputElement;
    const setup = screen.getByLabelText(/tiempo de setup/i) as HTMLInputElement;
    const labor = screen.getByLabelText(/mano de obra/i) as HTMLInputElement;

    for (const input of [speed, cost, setup, labor]) {
      await user.clear(input);
      await user.type(input, "-5");
      expect(Number(input.value)).toBeGreaterThanOrEqual(0);
    }

    const save = screen.getByRole("button", { name: "Guardar" });
    await user.clear(speed);
    await user.type(speed, "0");
    await waitFor(() => expect(save).toBeDisabled());

    await user.clear(speed);
    await user.type(speed, "3000");
    await user.clear(cost);
    await user.type(cost, "18000");
    await waitFor(() => expect(save).toBeEnabled());
  });
});
