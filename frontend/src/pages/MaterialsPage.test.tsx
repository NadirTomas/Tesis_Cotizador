import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MaterialsPage from "./MaterialsPage";

vi.mock("../context/AuthContext", () => ({ useAuth: () => ({ companyRole: "owner" }) }));

const createMaterial = vi.fn();
vi.mock("../services/materials", () => ({
  getMaterials: () => Promise.resolve([]),
  createMaterial: (...args: unknown[]) => createMaterial(...args),
  updateMaterial: vi.fn(),
  deleteMaterial: vi.fn(),
}));

const COST_WARNING = /con costo 0 las cotizaciones no suman costo de material/i;

async function openCreateDialog() {
  const user = userEvent.setup();
  render(<MaterialsPage />);
  await user.click(await screen.findByRole("button", { name: /crear material/i }));
  return user;
}

describe("MaterialsPage numeric inputs", () => {
  beforeEach(() => {
    createMaterial.mockReset();
    createMaterial.mockResolvedValue({});
  });

  it("lets every numeric field take decimals (step=any), so arrows and the wheel never round to an integer", async () => {
    await openCreateDialog();

    for (const label of [/espesor/i, /ancho de chapa/i, /alto de chapa/i, /costo de chapa/i]) {
      expect(screen.getByLabelText(label)).toHaveAttribute("step", "any");
    }
  });

  it("keeps a decimal thickness like 4.75 and sends it as typed", async () => {
    const user = await openCreateDialog();

    await user.type(screen.getByLabelText(/^nombre/i), "Chapa 4.75");
    await user.type(screen.getByLabelText(/tipo de material/i), "CS");
    const thickness = screen.getByLabelText(/espesor/i) as HTMLInputElement;
    await user.clear(thickness);
    await user.type(thickness, "4.75");
    expect(thickness.value).toBe("4.75");

    const width = screen.getByLabelText(/ancho de chapa/i);
    await user.clear(width);
    await user.type(width, "1500");
    const height = screen.getByLabelText(/alto de chapa/i);
    await user.clear(height);
    await user.type(height, "3000");
    const cost = screen.getByLabelText(/costo de chapa/i);
    await user.clear(cost);
    await user.type(cost, "250000.5");

    await user.click(screen.getByRole("button", { name: "Guardar" }));
    await waitFor(() => expect(createMaterial).toHaveBeenCalledTimes(1));
    expect(createMaterial).toHaveBeenCalledWith(
      expect.objectContaining({ thickness_mm: 4.75, sheet_width_mm: 1500, sheet_height_mm: 3000, sheet_cost_ars: 250000.5 })
    );
  }, 20000);

  it("warns when the sheet cost is 0 without blocking the save, and clears the warning once there is a cost", async () => {
    const user = await openCreateDialog();

    expect(screen.getByText(COST_WARNING)).toBeInTheDocument();

    await user.type(screen.getByLabelText(/^nombre/i), "Material provisto");
    await user.type(screen.getByLabelText(/tipo de material/i), "CS");
    for (const [label, value] of [[/espesor/i, "3"], [/ancho de chapa/i, "1500"], [/alto de chapa/i, "3000"]] as const) {
      const input = screen.getByLabelText(label);
      await user.clear(input);
      await user.type(input, value);
    }
    expect(screen.getByRole("button", { name: "Guardar" })).toBeEnabled();
    expect(screen.getByText(COST_WARNING)).toBeInTheDocument();

    const cost = screen.getByLabelText(/costo de chapa/i);
    await user.clear(cost);
    await user.type(cost, "52000");
    expect(screen.queryByText(COST_WARNING)).not.toBeInTheDocument();
  }, 20000);
});
