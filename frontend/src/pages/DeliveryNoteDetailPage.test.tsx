import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DeliveryNoteDetailPage from "./DeliveryNoteDetailPage";
import type { DeliveryNote } from "../services/deliveryNotes";

let role = "owner";
vi.mock("../context/AuthContext", () => ({ useAuth: () => ({ companyRole: role }) }));

const getDeliveryNote = vi.fn();
const voidDeliveryNote = vi.fn();
const issueDeliveryNote = vi.fn();
vi.mock("../services/deliveryNotes", () => ({
  getDeliveryNote: (...a: unknown[]) => getDeliveryNote(...a),
  voidDeliveryNote: (...a: unknown[]) => voidDeliveryNote(...a),
  issueDeliveryNote: (...a: unknown[]) => issueDeliveryNote(...a),
  deleteDeliveryNote: vi.fn(),
  getDeliveryNotePdfUrl: (id: number) => `/delivery-notes/${id}/pdf`,
}));
vi.mock("../services/authedResource", () => ({ openAuthedResource: vi.fn() }));

const note = (over: Partial<DeliveryNote> = {}): DeliveryNote => ({
  id: 3,
  company_id: 1,
  quotation_id: 5,
  client_id: 2,
  number: "R-000003",
  status: "ISSUED",
  issue_date: "2026-10-14T10:00:00",
  notes: "Retira Juan",
  quotation_number: "COT-0005",
  client_name: "Metalúrgica 24",
  client_tax_id: "20-12345678-9",
  client_address: "Calle 123",
  issued_at: "2026-10-14T10:00:00",
  voided_at: null,
  void_reason: null,
  created_at: "2026-10-14T09:00:00",
  updated_at: "2026-10-14T10:00:00",
  total_units: 25,
  cut_confirmed: null,
  cut_pending_pieces: [],
  items: [{ id: 1, quotation_item_id: 11, piece_id: 1, piece_name: "Soporte", piece_description: null, quantity: 25, unit: "un" }],
  ...over,
});

function renderDetail() {
  return render(
    <MemoryRouter initialEntries={["/delivery-notes/3"]}>
      <Routes>
        <Route path="/delivery-notes/:id" element={<DeliveryNoteDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("DeliveryNoteDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    role = "owner";
    getDeliveryNote.mockResolvedValue(note());
  });

  it("shows an issued note as read-only: no edit or issue actions", async () => {
    renderDetail();
    expect((await screen.findAllByText("R-000003")).length).toBeGreaterThan(0);
    expect(screen.getByText("Soporte")).toBeInTheDocument();
    expect(screen.getByText(/20-12345678-9/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Editar/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Emitir remito/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Anular/ })).toBeInTheDocument();
  });

  it("hides the void action from employees", async () => {
    role = "employee";
    renderDetail();
    await screen.findByText("Soporte");
    expect(screen.queryByRole("button", { name: /Anular/ })).not.toBeInTheDocument();
  });

  it("requires a reason to void: no error on open, button disabled, then voids", async () => {
    const user = userEvent.setup();
    voidDeliveryNote.mockResolvedValue(note({ status: "VOIDED", voided_at: "2026-10-14T12:00:00", void_reason: "Error de carga" }));
    renderDetail();
    await user.click(await screen.findByRole("button", { name: /^Anular$/ }));

    const reason = screen.getByLabelText(/Motivo de la anulación/);
    expect(reason).toHaveAttribute("aria-invalid", "false");
    const confirm = screen.getByRole("button", { name: "Anular remito" });
    expect(confirm).toBeDisabled();

    await user.type(reason, "ab");
    expect(await screen.findByText(/mínimo 3 caracteres/)).toBeInTheDocument();
    expect(confirm).toBeDisabled();

    await user.type(reason, "c carga");
    await waitFor(() => expect(confirm).toBeEnabled());
    await user.click(confirm);

    await waitFor(() => expect(voidDeliveryNote).toHaveBeenCalledWith(3, "abc carga"));
    expect(await screen.findByText(/Remito anulado el/)).toBeInTheDocument();
  });

  it("blocks issuing a draft while the cut is not confirmed, and explains why", async () => {
    getDeliveryNote.mockResolvedValue(
      note({ status: "DRAFT", number: null, issue_date: null, issued_at: null, cut_confirmed: false, cut_pending_pieces: ["Soporte"] }),
    );
    renderDetail();
    expect(await screen.findByText(/el corte de Soporte todavía no fue confirmado/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Emitir remito$/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Editar/ })).toBeEnabled();
    expect(screen.getByRole("button", { name: /Eliminar borrador/ })).toBeEnabled();
  });

  it("unblocks the draft after the cut is confirmed (reloaded when the window regains focus)", async () => {
    getDeliveryNote.mockResolvedValue(
      note({ status: "DRAFT", number: null, issue_date: null, issued_at: null, cut_confirmed: false, cut_pending_pieces: ["Soporte"] }),
    );
    renderDetail();
    await screen.findByText(/el corte de Soporte todavía no fue confirmado/);

    getDeliveryNote.mockResolvedValue(note({ status: "DRAFT", number: null, issue_date: null, issued_at: null, cut_confirmed: true }));
    window.dispatchEvent(new Event("focus"));

    await waitFor(() => expect(screen.getByRole("button", { name: /^Emitir remito$/ })).toBeEnabled());
    expect(screen.queryByText(/todavía no fue confirmado/)).not.toBeInTheDocument();
  });

  it("ignores a double click on the issue confirmation (a single issue request)", async () => {
    const user = userEvent.setup();
    getDeliveryNote.mockResolvedValue(note({ status: "DRAFT", number: null, issue_date: null, issued_at: null, cut_confirmed: true }));
    issueDeliveryNote.mockImplementation(() => new Promise((resolve) => setTimeout(() => resolve(note()), 30)));
    renderDetail();
    await user.click(await screen.findByRole("button", { name: /^Emitir remito$/ }));

    const confirm = await screen.findByRole("button", { name: "Emitir" });
    fireEvent.click(confirm);
    fireEvent.click(confirm);
    await waitFor(() => expect(issueDeliveryNote).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByText(/Remito emitido: el contenido es de solo lectura/)).toBeInTheDocument());
    expect(issueDeliveryNote).toHaveBeenCalledTimes(1);
  });

  it("asks for confirmation before issuing a draft", async () => {
    const user = userEvent.setup();
    getDeliveryNote.mockResolvedValue(note({ status: "DRAFT", number: null, issue_date: null, issued_at: null, cut_confirmed: true }));
    issueDeliveryNote.mockResolvedValue(note());
    renderDetail();

    expect(await screen.findByText(/es un borrador/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^Emitir remito$/ }));
    expect(issueDeliveryNote).not.toHaveBeenCalled();
    expect(await screen.findByText(/Se le asignará el próximo número/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Emitir" }));
    await waitFor(() => expect(issueDeliveryNote).toHaveBeenCalledWith(3));
  });
});
