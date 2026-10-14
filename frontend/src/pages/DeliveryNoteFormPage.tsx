import { ArrowBack } from "@mui/icons-material";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useTouchedFields } from "../hooks/useTouchedFields";
import {
  createDeliveryNote,
  getDeliveryNote,
  getQuotationDeliveryStatus,
  issueDeliveryNote,
  updateDeliveryNote,
  type DeliveryNoteLineInput,
  type DeliveryStatus,
} from "../services/deliveryNotes";
import { CUT_PENDING_HINT, DELIVERY_STATE, parseDeliveryQuantity } from "../utils/deliveryNotes";

const NOTES_MAX = 1000;

/** Crea (desde una cotización) o edita (borrador) un remito. Los datos de la cotización son de solo lectura. */
const DeliveryNoteFormPage = () => {
  const navigate = useNavigate();
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const editingId = id ? Number(id) : null;

  const [status, setStatus] = useState<DeliveryStatus | null>(null);
  const [quantities, setQuantities] = useState<Record<number, string>>({});
  const [notes, setNotes] = useState("");
  const [savedId, setSavedId] = useState<number | null>(editingId);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  // Guard síncrono contra doble clic: `saving` se refleja recién en el próximo render, un segundo clic llegaría antes.
  const inFlight = useRef(false);
  const { touch, isTouched } = useTouchedFields();

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        let quotationId = Number(searchParams.get("quotation"));
        let initial: Record<number, string> = {};
        let initialNotes = "";
        if (editingId !== null) {
          const note = await getDeliveryNote(editingId);
          if (note.status !== "DRAFT") {
            navigate(`/delivery-notes/${note.id}`, { replace: true });
            return;
          }
          quotationId = note.quotation_id;
          initial = Object.fromEntries(note.items.map((l) => [l.quotation_item_id, String(l.quantity)]));
          initialNotes = note.notes ?? "";
        }
        if (!Number.isInteger(quotationId) || quotationId <= 0) {
          throw new Error("Falta la cotización de origen. Generá el remito desde el detalle de una cotización.");
        }
        const s = await getQuotationDeliveryStatus(quotationId);
        if (cancelled) return;
        setStatus(s);
        setQuantities(initial);
        setNotes(initialNotes);
      } catch (e) {
        if (!cancelled) setLoadError(e instanceof Error ? e.message : "No se pudo cargar la cotización.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [editingId, searchParams, navigate]);

  const rows = useMemo(
    () =>
      (status?.items ?? []).map((line) => ({
        line,
        parsed: parseDeliveryQuantity(quantities[line.quotation_item_id] ?? "", line.pending),
      })),
    [status, quantities],
  );
  const selected: DeliveryNoteLineInput[] = rows
    .filter((r) => r.parsed.quantity !== null)
    .map((r) => ({ quotation_item_id: r.line.quotation_item_id, quantity: r.parsed.quantity as number }));
  const totalUnits = selected.reduce((sum, l) => sum + l.quantity, 0);
  const hasErrors = rows.some((r) => r.parsed.error !== null);
  const canSubmit = !!status?.eligible && !hasErrors && selected.length > 0 && !saving;
  // Emitir exige corte confirmado en cada pieza del remito; guardar borrador no. El backend es la autoridad: esto solo evita el intento.
  const uncutSelected = rows.filter((r) => r.parsed.quantity !== null && !r.line.cut_confirmed);
  const canIssue = canSubmit && uncutSelected.length === 0;
  const quotationId = status?.quotation_id;

  // Al volver de la cotización (donde se confirma el corte) se recarga el estado real, sin perder lo tipeado.
  useEffect(() => {
    if (quotationId === undefined) return;
    const refresh = () => {
      getQuotationDeliveryStatus(quotationId).then(setStatus).catch(() => undefined);
    };
    window.addEventListener("focus", refresh);
    return () => window.removeEventListener("focus", refresh);
  }, [quotationId]);

  function setQuantity(itemId: number, value: string) {
    setQuantities((prev) => ({ ...prev, [itemId]: value }));
    touch(`q${itemId}`);
    setSubmitError(null);
  }

  async function persist(): Promise<number> {
    const cleanNotes = notes.trim();
    if (savedId !== null) {
      await updateDeliveryNote(savedId, { notes: cleanNotes || null, items: selected });
      return savedId;
    }
    const created = await createDeliveryNote({
      quotation_id: status!.quotation_id,
      ...(cleanNotes && { notes: cleanNotes }),
      items: selected,
    });
    setSavedId(created.id);
    return created.id;
  }

  async function handleSaveDraft() {
    if (inFlight.current) return;
    inFlight.current = true;
    setSaving(true);
    setSubmitError(null);
    try {
      const noteId = await persist();
      navigate(`/delivery-notes/${noteId}`);
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "No se pudo guardar el borrador.");
      setSaving(false);
      inFlight.current = false;
    }
  }

  async function handleIssue() {
    if (inFlight.current) return;
    inFlight.current = true;
    setSaving(true);
    setSubmitError(null);
    try {
      const noteId = await persist();
      await issueDeliveryNote(noteId);
      navigate(`/delivery-notes/${noteId}`);
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "No se pudo emitir el remito.");
      setSaving(false);
      inFlight.current = false;
    }
  }

  if (loading) {
    return <Box display="flex" justifyContent="center" mt={6}><CircularProgress /></Box>;
  }

  if (loadError || !status) {
    return <Alert severity="error">{loadError ?? "No se pudo cargar la cotización."}</Alert>;
  }

  const state = DELIVERY_STATE[status.state];

  return (
    <Box display="flex" flexDirection="column" gap={3}>
      <Box>
        <Box display="flex" alignItems="center" gap={1.5} mb={0.75}>
          <Button startIcon={<ArrowBack />} onClick={() => navigate(`/quotations/${status.quotation_id}`)} size="small" sx={{ mr: 0.5 }}>
            Volver
          </Button>
          <Box sx={{ width: 3, height: 26, bgcolor: "primary.main", borderRadius: 1, boxShadow: "0 0 10px rgba(255,107,0,0.6)", flexShrink: 0 }} />
          <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 700, fontSize: "1.8rem", letterSpacing: "0.05em", textTransform: "uppercase", lineHeight: 1 }}>
            {editingId !== null ? "Editar borrador de remito" : "Generar remito"}
          </Typography>
        </Box>
        <Typography sx={{ color: "text.secondary", fontSize: "0.82rem", ml: "19px" }}>
          {status.client_name} · Cotización {status.quotation_number}
        </Typography>
      </Box>

      {!status.eligible && <Alert severity="warning">{status.ineligible_reason}</Alert>}
      {status.eligible && uncutSelected.length > 0 && (
        <Alert severity="warning">
          El corte de {uncutSelected.map((r) => r.line.piece_name).join(", ")} todavía no fue confirmado. {CUT_PENDING_HINT}
        </Alert>
      )}
      {status.eligible && status.total_pending === 0 && (
        <Alert severity="info">Todas las unidades de esta cotización ya fueron entregadas.</Alert>
      )}

      <Paper variant="outlined" sx={{ p: 2.5 }}>
        <Box display="flex" gap={4} flexWrap="wrap" alignItems="center">
          {[
            { label: "Cliente", value: status.client_name },
            { label: "Cotización", value: status.quotation_number },
            { label: "Cotizado", value: String(status.total_quoted) },
            { label: "Ya entregado", value: String(status.total_delivered) },
            { label: "Pendiente", value: String(status.total_pending) },
          ].map(({ label, value }) => (
            <Box key={label}>
              <Typography sx={{ fontSize: "0.72rem", letterSpacing: "0.08em", textTransform: "uppercase", color: "text.secondary", mb: 0.25 }}>
                {label}
              </Typography>
              <Typography sx={{ fontWeight: 500 }}>{value}</Typography>
            </Box>
          ))}
          <Chip label={state.label} color={state.color} size="small" />
        </Box>
      </Paper>

      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Pieza</TableCell>
              <TableCell>Descripción</TableCell>
              <TableCell align="right">Cotizado</TableCell>
              <TableCell align="right">Entregado</TableCell>
              <TableCell align="right">Pendiente</TableCell>
              <TableCell align="center">Corte</TableCell>
              <TableCell align="right" sx={{ width: 250 }}>Entregar ahora</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map(({ line, parsed }) => {
              const key = `q${line.quotation_item_id}`;
              const showError = isTouched(key) && parsed.error !== null;
              return (
                <TableRow key={line.quotation_item_id}>
                  <TableCell sx={{ fontWeight: 500 }}>{line.piece_name}</TableCell>
                  <TableCell sx={{ color: "text.secondary" }}>{line.piece_description ?? "—"}</TableCell>
                  <TableCell align="right"><span className="mono">{line.quoted}</span></TableCell>
                  <TableCell align="right"><span className="mono">{line.delivered}</span></TableCell>
                  <TableCell align="right"><span className="mono">{line.pending}</span></TableCell>
                  <TableCell align="center">
                    <Chip
                      label={line.cut_confirmed ? "Confirmado" : "Sin confirmar"}
                      color={line.cut_confirmed ? "success" : "warning"}
                      size="small"
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell align="right">
                    <Box display="flex" gap={1} justifyContent="flex-end" alignItems="flex-start">
                      <Button
                        size="small"
                        disabled={line.pending === 0 || !status.eligible}
                        onClick={() => setQuantity(line.quotation_item_id, String(line.pending))}
                      >
                        Todo
                      </Button>
                      <TextField
                        size="small"
                        type="number"
                        value={quantities[line.quotation_item_id] ?? ""}
                        onChange={(e) => setQuantity(line.quotation_item_id, e.target.value)}
                        onBlur={() => touch(key)}
                        disabled={line.pending === 0 || !status.eligible}
                        error={showError}
                        helperText={showError ? parsed.error : undefined}
                        slotProps={{ htmlInput: { min: 0, max: line.pending, step: 1, "aria-label": `Entregar ahora ${line.piece_name}` } }}
                        sx={{ width: 150 }}
                      />
                    </Box>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>

      <TextField
        label="Observaciones (opcional)"
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        fullWidth
        multiline
        rows={2}
        slotProps={{ htmlInput: { maxLength: NOTES_MAX } }}
        helperText={`${notes.length}/${NOTES_MAX}`}
      />

      {submitError && <Alert severity="error">{submitError}</Alert>}

      <Box display="flex" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={2}>
        <Typography sx={{ color: "text.secondary" }}>
          Total a entregar ahora: <b>{totalUnits}</b> unidad{totalUnits !== 1 ? "es" : ""}
        </Typography>
        <Box display="flex" gap={1.5}>
          <Button variant="outlined" onClick={handleSaveDraft} disabled={!canSubmit}>
            {saving ? "Guardando..." : "Guardar borrador"}
          </Button>
          <Button variant="contained" onClick={() => setPreviewOpen(true)} disabled={!canIssue}>
            Vista previa y emitir
          </Button>
        </Box>
      </Box>

      <Dialog open={previewOpen} onClose={() => !saving && setPreviewOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Vista previa del remito</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <Typography sx={{ fontSize: "0.9rem" }}>
            <b>Cliente:</b> {status.client_name}<br />
            <b>Cotización de origen:</b> {status.quotation_number}
          </Typography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Pieza</TableCell>
                <TableCell align="right">Cantidad a entregar</TableCell>
                <TableCell>Unidad</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.filter((r) => r.parsed.quantity !== null).map(({ line, parsed }) => (
                <TableRow key={line.quotation_item_id}>
                  <TableCell>{line.piece_name}</TableCell>
                  <TableCell align="right"><span className="mono">{parsed.quantity}</span></TableCell>
                  <TableCell>{line.unit}</TableCell>
                </TableRow>
              ))}
              <TableRow>
                <TableCell sx={{ fontWeight: 600 }}>Total</TableCell>
                <TableCell align="right"><span className="mono" style={{ fontWeight: 600 }}>{totalUnits}</span></TableCell>
                <TableCell />
              </TableRow>
            </TableBody>
          </Table>
          {notes.trim() && <Typography variant="body2" color="text.secondary">Observaciones: {notes.trim()}</Typography>}
          <Alert severity="warning">
            Al emitir se asigna el número de remito y las unidades pasan a contar como entregadas. Después de emitido no se puede modificar, solo anular.
          </Alert>
          {submitError && <Alert severity="error">{submitError}</Alert>}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPreviewOpen(false)} disabled={saving}>Volver a editar</Button>
          <Button variant="contained" onClick={handleIssue} disabled={saving || !canIssue}>
            {saving ? "Emitiendo..." : "Emitir remito"}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default DeliveryNoteFormPage;
