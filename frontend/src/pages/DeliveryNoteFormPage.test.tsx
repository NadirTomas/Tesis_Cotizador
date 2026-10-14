import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DeliveryNoteFormPage from "./DeliveryNoteFormPage";
import type { DeliveryStatus } from "../services/deliveryNotes";

const getQuotationDeliveryStatus = vi.fn();
const createDeliveryNote = vi.fn();
const issueDeliveryNote = vi.fn();
vi.mock("../services/deliveryNotes", () => ({
  getQuotationDeliveryStatus: (...a: unknown[]) => getQuotationDeliveryStatus(...a),
  createDeliveryNote: (...a: unknown[]) => createDeliveryNote(...a),
  issueDeliveryNote: (...a: unknown[]) => issueDeliveryNote(...a),
  updateDeliveryNote: vi.fn(),
  getDeliveryNote: vi.fn(),
}));

const status = (over: Partial<DeliveryStatus> = {}): DeliveryStatus => ({
  quotation_id: 5,
  quotation_number: "COT-0005",
  quotation_status: "accepted",
  client_name: "Metalúrgica 24",
  cut_confirmed: true,
  eligible: true,
  ineligible_reason: null,
  state: "PARTIAL",
  total_quoted: 100,
  total_delivered: 40,
  total_pending: 60,
  items: [
    { quotation_item_id: 11, piece_id: 1, piece_name: "Soporte", piece_description: "Con 4 agujeros", unit: "un", quoted: 100, delivered: 40, pending: 60, cut_confirmed: true },
  ],
  ...over,
});

function renderForm() {
  return render(
    <MemoryRouter initialEntries={["/delivery-notes/new?quotation=5"]}>
      <Routes>
        <Route path="/delivery-notes/new" element={<DeliveryNoteFormPage />} />
        <Route path="/delivery-notes/:id" element={<div>DETALLE DEL REMITO</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("DeliveryNoteFormPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getQuotationDeliveryStatus.mockResolvedValue(status());
  });

  it("shows client, quoted / delivered / pending and opens without any validation error", async () => {
    renderForm();
    expect(await screen.findByText("Soporte")).toBeInTheDocument();
    expect(screen.getAllByText(/Metalúrgica 24/).length).toBeGreaterThan(0);
    expect(screen.getByText("Con 4 agujeros")).toBeInTheDocument();

    const input = screen.getByLabelText("Entregar ahora Soporte");
    expect(input).toHaveAttribute("aria-invalid", "false");
    expect(screen.getByRole("button", { name: "Guardar borrador" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Vista previa y emitir" })).toBeDisabled();
  });

  it("reports a negative quantity as an error (never flips the sign) and keeps submit disabled", async () => {
    const user = userEvent.setup();
    renderForm();
    const input = (await screen.findByLabelText("Entregar ahora Soporte")) as HTMLInputElement;
    await user.type(input, "-5");

    expect(input.value).toBe("-5");
    expect(await screen.findByText("La cantidad no puede ser negativa.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Vista previa y emitir" })).toBeDisabled();
  });

  it("rejects more than the pending amount", async () => {
    const user = userEvent.setup();
    renderForm();
    await user.type(await screen.findByLabelText("Entregar ahora Soporte"), "61");
    expect(await screen.findByText(/No puede superar lo pendiente \(60\)/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Guardar borrador" })).toBeDisabled();
  });

  it("previews, asks for confirmation and then creates and issues the note", async () => {
    const user = userEvent.setup();
    createDeliveryNote.mockResolvedValue({ id: 77 });
    issueDeliveryNote.mockResolvedValue({ id: 77, number: "R-000002" });
    renderForm();

    await user.type(await screen.findByLabelText("Entregar ahora Soporte"), "35");
    await user.type(screen.getByLabelText(/Observaciones/), "Retira Juan");
    await user.click(screen.getByRole("button", { name: "Vista previa y emitir" }));

    expect(await screen.findByText("Vista previa del remito")).toBeInTheDocument();
    expect(createDeliveryNote).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Emitir remito" }));
    await waitFor(() => expect(screen.getByText("DETALLE DEL REMITO")).toBeInTheDocument());
    expect(createDeliveryNote).toHaveBeenCalledWith({
      quotation_id: 5,
      notes: "Retira Juan",
      items: [{ quotation_item_id: 11, quantity: 35 }],
    });
    expect(issueDeliveryNote).toHaveBeenCalledWith(77);
  });

  it("without a confirmed cut: warns, still saves drafts, but cannot preview/issue", async () => {
    const user = userEvent.setup();
    const uncut = status({
      cut_confirmed: false,
      items: [{ quotation_item_id: 11, piece_id: 1, piece_name: "Soporte", piece_description: null, unit: "un", quoted: 100, delivered: 40, pending: 60, cut_confirmed: false }],
    });
    getQuotationDeliveryStatus.mockResolvedValue(uncut);
    createDeliveryNote.mockResolvedValue({ id: 88 });
    renderForm();

    await user.type(await screen.findByLabelText("Entregar ahora Soporte"), "10");
    expect(await screen.findByText(/El corte de Soporte todavía no fue confirmado/)).toBeInTheDocument();
    expect(screen.getByText("Sin confirmar")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Vista previa y emitir" })).toBeDisabled();

    const saveDraft = screen.getByRole("button", { name: "Guardar borrador" });
    expect(saveDraft).toBeEnabled();
    await user.click(saveDraft);
    await waitFor(() => expect(screen.getByText("DETALLE DEL REMITO")).toBeInTheDocument());
    expect(createDeliveryNote).toHaveBeenCalledWith({ quotation_id: 5, items: [{ quotation_item_id: 11, quantity: 10 }] });
    expect(issueDeliveryNote).not.toHaveBeenCalled();
  });

  it("enables issuing again once the cut gets confirmed (state reloaded on window focus)", async () => {
    const user = userEvent.setup();
    const uncutLine = { quotation_item_id: 11, piece_id: 1, piece_name: "Soporte", piece_description: null, unit: "un", quoted: 100, delivered: 40, pending: 60 };
    getQuotationDeliveryStatus.mockResolvedValue(status({ cut_confirmed: false, items: [{ ...uncutLine, cut_confirmed: false }] }));
    renderForm();
    await user.type(await screen.findByLabelText("Entregar ahora Soporte"), "10");
    expect(screen.getByRole("button", { name: "Vista previa y emitir" })).toBeDisabled();

    getQuotationDeliveryStatus.mockResolvedValue(status({ cut_confirmed: true, items: [{ ...uncutLine, cut_confirmed: true }] }));
    window.dispatchEvent(new Event("focus"));

    await waitFor(() => expect(screen.getByRole("button", { name: "Vista previa y emitir" })).toBeEnabled());
    expect(screen.queryByText(/todavía no fue confirmado/)).not.toBeInTheDocument();
  });

  it("ignores a double click on 'Guardar borrador' (a single draft is created)", async () => {
    const user = userEvent.setup();
    createDeliveryNote.mockImplementation(() => new Promise((resolve) => setTimeout(() => resolve({ id: 5 }), 30)));
    renderForm();
    await user.type(await screen.findByLabelText("Entregar ahora Soporte"), "10");

    const save = screen.getByRole("button", { name: "Guardar borrador" });
    fireEvent.click(save);
    fireEvent.click(save);
    await waitFor(() => expect(screen.getByText("DETALLE DEL REMITO")).toBeInTheDocument());
    expect(createDeliveryNote).toHaveBeenCalledTimes(1);
  });

  it("does not offer to generate a note for an ineligible quotation", async () => {
    getQuotationDeliveryStatus.mockResolvedValue(
      status({ eligible: false, ineligible_reason: "Solo se pueden generar remitos de cotizaciones aceptadas.", quotation_status: "sent" }),
    );
    renderForm();
    expect(await screen.findByText(/Solo se pueden generar remitos/)).toBeInTheDocument();
    expect(screen.getByLabelText("Entregar ahora Soporte")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Vista previa y emitir" })).toBeDisabled();
  });

  it("keeps the draft and shows the backend error when issuing fails", async () => {
    const user = userEvent.setup();
    createDeliveryNote.mockResolvedValue({ id: 77 });
    issueDeliveryNote.mockRejectedValue(new Error("No se puede entregar 35 de 'Soporte': solo quedan 10 pendientes."));
    renderForm();
    await user.type(await screen.findByLabelText("Entregar ahora Soporte"), "35");
    await user.click(screen.getByRole("button", { name: "Vista previa y emitir" }));
    await user.click(await screen.findByRole("button", { name: "Emitir remito" }));

    expect((await screen.findAllByText(/solo quedan 10 pendientes/)).length).toBeGreaterThan(0);
    expect(screen.queryByText("DETALLE DEL REMITO")).not.toBeInTheDocument();
  });
});
