import { ArrowBack, Block, Delete, Edit, PictureAsPdf, Send } from "@mui/icons-material";
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
  Snackbar,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useTouchedFields } from "../hooks/useTouchedFields";
import { openAuthedResource } from "../services/authedResource";
import {
  deleteDeliveryNote,
  getDeliveryNote,
  getDeliveryNotePdfUrl,
  issueDeliveryNote,
  voidDeliveryNote,
  type DeliveryNote,
} from "../services/deliveryNotes";
import { CUT_PENDING_HINT, formatDate, NOTE_STATUS } from "../utils/deliveryNotes";

const MIN_REASON_LENGTH = 3;

const DeliveryNoteDetailPage = () => {
  const { id } = useParams();
  const noteId = Number(id);
  const navigate = useNavigate();
  const { companyRole } = useAuth();
  const isOwner = companyRole === "owner";

  const [note, setNote] = useState<DeliveryNote | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const inFlight = useRef(false); // guard síncrono contra doble clic (busy se refleja recién en el próximo render)

  const [confirmIssue, setConfirmIssue] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [voidOpen, setVoidOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [dialogError, setDialogError] = useState<string | null>(null);
  const { touch, touchAll, reset: resetTouched, isTouched } = useTouchedFields();

  const load = useCallback(async () => {
    try {
      setNote(await getDeliveryNote(noteId));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo cargar el remito.");
    } finally {
      setLoading(false);
    }
  }, [noteId]);

  useEffect(() => {
    load();
  }, [load]);

  // Un borrador bloqueado por corte pendiente se destraba al confirmar el corte en la cotización: se recarga al volver a esta pestaña.
  const isDraft = note?.status === "DRAFT";
  useEffect(() => {
    if (!isDraft) return;
    window.addEventListener("focus", load);
    return () => window.removeEventListener("focus", load);
  }, [isDraft, load]);

  async function handlePdf() {
    try {
      await openAuthedResource(getDeliveryNotePdfUrl(noteId));
    } catch {
      setToast("No se pudo abrir el PDF del remito.");
    }
  }

  async function handleIssue() {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setDialogError(null);
    try {
      const issued = await issueDeliveryNote(noteId);
      setNote(issued);
      setConfirmIssue(false);
      setToast(`Remito ${issued.number} emitido.`);
    } catch (e) {
      setDialogError(e instanceof Error ? e.message : "No se pudo emitir el remito.");
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setDialogError(null);
    try {
      await deleteDeliveryNote(noteId);
      navigate("/delivery-notes");
    } catch (e) {
      setDialogError(e instanceof Error ? e.message : "No se pudo eliminar el borrador.");
      inFlight.current = false;
      setBusy(false);
    }
  }

  const reasonInvalid = reason.trim().length < MIN_REASON_LENGTH;

  async function handleVoid() {
    if (reasonInvalid) {
      touchAll(["reason"]);
      return;
    }
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setDialogError(null);
    try {
      setNote(await voidDeliveryNote(noteId, reason.trim()));
      setVoidOpen(false);
      setToast("Remito anulado. Las cantidades volvieron a quedar pendientes.");
    } catch (e) {
      setDialogError(e instanceof Error ? e.message : "No se pudo anular el remito.");
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  function openVoid() {
    setReason("");
    setDialogError(null);
    resetTouched();
    setVoidOpen(true);
  }

  if (loading) {
    return <Box display="flex" justifyContent="center" mt={6}><CircularProgress /></Box>;
  }

  if (error || !note) {
    return <Alert severity="error">{error ?? "Remito no encontrado."}</Alert>;
  }

  const status = NOTE_STATUS[note.status];
  const cutPending = note.status === "DRAFT" && note.cut_confirmed === false;
  const title = note.number ?? "Remito en borrador";

  return (
    <Box display="flex" flexDirection="column" gap={3}>
      <Box display="flex" justifyContent="space-between" alignItems="flex-start" flexWrap="wrap" gap={2}>
        <Box>
          <Box display="flex" alignItems="center" gap={1.5} mb={0.75}>
            <Button startIcon={<ArrowBack />} onClick={() => navigate("/delivery-notes")} size="small" sx={{ mr: 0.5 }}>
              Volver
            </Button>
            <Box sx={{ width: 3, height: 26, bgcolor: "primary.main", borderRadius: 1, boxShadow: "0 0 10px rgba(255,107,0,0.6)", flexShrink: 0 }} />
            <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 700, fontSize: "1.8rem", letterSpacing: "0.05em", textTransform: "uppercase", lineHeight: 1 }}>
              {title}
            </Typography>
          </Box>
          <Typography sx={{ color: "text.secondary", fontSize: "0.82rem", ml: "19px" }}>
            {note.client_name} · {formatDate(note.issue_date ?? note.created_at)}
          </Typography>
        </Box>
        <Box display="flex" alignItems="center" flexWrap="wrap" gap={1.5}>
          <Chip label={status.label} color={status.color} size="small" />
          {note.status === "DRAFT" && (
            <>
              <Button size="small" variant="outlined" startIcon={<Edit />} onClick={() => navigate(`/delivery-notes/${note.id}/edit`)}>
                Editar
              </Button>
              <Button size="small" variant="outlined" color="error" startIcon={<Delete />} onClick={() => { setDialogError(null); setConfirmDelete(true); }}>
                Eliminar borrador
              </Button>
              <Button size="small" variant="contained" startIcon={<Send />} disabled={cutPending} onClick={() => { setDialogError(null); setConfirmIssue(true); }}>
                Emitir remito
              </Button>
            </>
          )}
          {note.status === "ISSUED" && isOwner && (
            <Button size="small" variant="outlined" color="error" startIcon={<Block />} onClick={openVoid}>
              Anular
            </Button>
          )}
          <Button variant="contained" startIcon={<PictureAsPdf />} onClick={handlePdf}>
            {note.status === "DRAFT" ? "Vista previa PDF" : "PDF"}
          </Button>
        </Box>
      </Box>

      {note.status === "DRAFT" && (
        <Alert severity="warning">
          Este remito es un borrador: todavía no tiene número y no cuenta como entrega. Se puede editar hasta emitirlo.
        </Alert>
      )}
      {cutPending && (
        <Alert
          severity="warning"
          action={
            <Button color="inherit" size="small" onClick={() => navigate(`/quotations/${note.quotation_id}`)}>
              Ir a la cotización
            </Button>
          }
        >
          No se puede emitir porque el corte de {note.cut_pending_pieces.join(", ")} todavía no fue confirmado. {CUT_PENDING_HINT}
        </Alert>
      )}
      {note.status === "ISSUED" && (
        <Alert severity="info">
          Remito emitido: el contenido es de solo lectura. Si hay un error, se anula y se genera uno nuevo.
          {!isOwner && " Solo el OWNER puede anular remitos."}
        </Alert>
      )}
      {note.status === "VOIDED" && (
        <Alert severity="error">
          Remito anulado el {formatDate(note.voided_at)}. Motivo: {note.void_reason}. Las unidades volvieron a estar pendientes de entrega.
        </Alert>
      )}

      <Paper variant="outlined" sx={{ p: 2.5 }}>
        <Box display="flex" gap={4} flexWrap="wrap">
          {[
            { label: "Cliente", value: note.client_name },
            ...(note.client_tax_id ? [{ label: "CUIT/CUIL", value: note.client_tax_id }] : []),
            ...(note.client_address ? [{ label: "Dirección", value: note.client_address }] : []),
            { label: "Cotización", value: note.quotation_number },
            { label: "Fecha de emisión", value: formatDate(note.issue_date) },
          ].map(({ label, value }) => (
            <Box key={label}>
              <Typography sx={{ fontSize: "0.72rem", letterSpacing: "0.08em", textTransform: "uppercase", color: "text.secondary", mb: 0.25 }}>
                {label}
              </Typography>
              {label === "Cotización" ? (
                <Typography
                  className="mono"
                  sx={{ fontWeight: 500, cursor: "pointer", textDecoration: "underline" }}
                  onClick={() => navigate(`/quotations/${note.quotation_id}`)}
                >
                  {value}
                </Typography>
              ) : (
                <Typography sx={{ fontWeight: 500 }}>{value}</Typography>
              )}
            </Box>
          ))}
        </Box>
        {note.notes && (
          <Typography variant="body2" color="text.secondary" mt={1.5}>Observaciones: {note.notes}</Typography>
        )}
      </Paper>

      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Pieza</TableCell>
              <TableCell>Descripción</TableCell>
              <TableCell align="right">Cantidad entregada</TableCell>
              <TableCell>Unidad</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {note.items.map((line) => (
              <TableRow key={line.id}>
                <TableCell sx={{ fontWeight: 500 }}>{line.piece_name}</TableCell>
                <TableCell sx={{ color: "text.secondary" }}>{line.piece_description ?? "—"}</TableCell>
                <TableCell align="right"><span className="mono">{line.quantity}</span></TableCell>
                <TableCell>{line.unit}</TableCell>
              </TableRow>
            ))}
            <TableRow>
              <TableCell sx={{ fontWeight: 600 }}>Total de unidades</TableCell>
              <TableCell />
              <TableCell align="right"><span className="mono" style={{ fontWeight: 600 }}>{note.total_units}</span></TableCell>
              <TableCell />
            </TableRow>
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={confirmIssue} onClose={() => !busy && setConfirmIssue(false)} fullWidth maxWidth="xs">
        <DialogTitle>Emitir remito</DialogTitle>
        <DialogContent>
          <Typography>
            Se le asignará el próximo número y pasará a contar como entrega de {note.total_units} unidad{note.total_units !== 1 ? "es" : ""}.
            Una vez emitido no se puede modificar, solo anular.
          </Typography>
          {dialogError && <Alert severity="error" sx={{ mt: 2 }}>{dialogError}</Alert>}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmIssue(false)} disabled={busy}>Cancelar</Button>
          <Button variant="contained" onClick={handleIssue} disabled={busy}>{busy ? "Emitiendo..." : "Emitir"}</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={confirmDelete} onClose={() => !busy && setConfirmDelete(false)} fullWidth maxWidth="xs">
        <DialogTitle>Eliminar borrador</DialogTitle>
        <DialogContent>
          <Typography>¿Confirmás que querés eliminar este borrador? No se consumió ningún número y no afecta las entregas.</Typography>
          {dialogError && <Alert severity="error" sx={{ mt: 2 }}>{dialogError}</Alert>}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDelete(false)} disabled={busy}>Cancelar</Button>
          <Button color="error" variant="contained" onClick={handleDelete} disabled={busy}>Eliminar</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={voidOpen} onClose={() => !busy && setVoidOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>Anular remito {note.number}</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <Typography>
            El remito no se borra: queda registrado como anulado y las {note.total_units} unidades vuelven a estar pendientes de entrega.
          </Typography>
          <TextField
            label="Motivo de la anulación"
            value={reason}
            onChange={(e) => { setReason(e.target.value); touch("reason"); }}
            onBlur={() => touch("reason")}
            error={isTouched("reason") && reasonInvalid}
            helperText={isTouched("reason") && reasonInvalid ? `Ingresá un motivo (mínimo ${MIN_REASON_LENGTH} caracteres).` : undefined}
            fullWidth
            required
            multiline
            rows={2}
            slotProps={{ htmlInput: { maxLength: 500 } }}
          />
          {dialogError && <Alert severity="error">{dialogError}</Alert>}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setVoidOpen(false)} disabled={busy}>Cancelar</Button>
          <Button color="error" variant="contained" onClick={handleVoid} disabled={busy || reasonInvalid}>
            {busy ? "Anulando..." : "Anular remito"}
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={!!toast} autoHideDuration={3500} onClose={() => setToast(null)} message={toast} />
    </Box>
  );
};

export default DeliveryNoteDetailPage;
