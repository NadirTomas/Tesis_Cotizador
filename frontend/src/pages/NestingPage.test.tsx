import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import NestingPage from "./NestingPage";
import { loadNestingDraft, saveNestingDraft } from "../utils/nestingDraft";

let companyId = 1;
vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({ companyId }),
}));

const getPieces = vi.fn();
vi.mock("../services/pieces", () => ({ getPieces: () => getPieces() }));
vi.mock("../services/materials", () => ({ getMaterials: () => Promise.resolve([]) }));
vi.mock("../services/nesting", () => ({ calculateNesting: vi.fn() }));

const piece = (id: number, name: string) => ({
  id,
  name,
  description: null,
  material_id: null,
  dxf_filename: `${name}.dxf`,
  has_dxf: true,
  has_preview: false,
  length_cut_mm: 100,
  area_mm2: 100,
  active: true,
  created_at: "2026-01-01T00:00:00",
});

const baseDraft = {
  cart: [{ piece_id: 1, quantity: 4 }],
  sheetW: 1250,
  sheetH: 2500,
  margin: 9,
  allowRotation: false,
  result: null,
  activeSheet: 0,
};

describe("NestingPage persistence across navigation", () => {
  beforeEach(() => {
    sessionStorage.clear();
    companyId = 1;
    getPieces.mockResolvedValue([piece(1, "Soporte"), piece(2, "Brida")]);
  });

  it("restores cart and sheet settings after the page is remounted", async () => {
    saveNestingDraft(1, baseDraft);
    render(<NestingPage />);

    expect(await screen.findByText(/Soporte/)).toBeInTheDocument();
    expect(screen.getByDisplayValue("4")).toBeInTheDocument();
    expect(screen.getByDisplayValue("1250")).toBeInTheDocument();
    expect(screen.getByDisplayValue("2500")).toBeInTheDocument();
    expect(screen.getByDisplayValue("9")).toBeInTheDocument();
  });

  it("does not restore another company's draft", async () => {
    saveNestingDraft(1, baseDraft);
    companyId = 2;
    render(<NestingPage />);

    await waitFor(() => expect(screen.queryByText("Soporte")).not.toBeInTheDocument());
    expect(screen.queryByDisplayValue("1250")).not.toBeInTheDocument();
  });

  it("drops cart items whose piece no longer exists and persists the cleaned draft", async () => {
    saveNestingDraft(1, { ...baseDraft, cart: [{ piece_id: 1, quantity: 2 }, { piece_id: 99, quantity: 1 }] });
    render(<NestingPage />);

    await screen.findByText(/Soporte/);
    await waitFor(() => expect(loadNestingDraft(1)?.cart).toEqual([{ piece_id: 1, quantity: 2 }]));
  });
});
