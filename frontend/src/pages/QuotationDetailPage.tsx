import { ArrowBack, Delete, PictureAsPdf, WarningAmber } from "@mui/icons-material";
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
  Divider,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Snackbar,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { getClients, type Client } from "../services/clients";
import { getMaterials, type Material } from "../services/materials";
import { getPieces, type Piece } from "../services/pieces";
import {
  createQuotationItem,
  deleteQuotationItem,
  getQuotation,
  getQuotationItems,
  getQuotationPdfUrl,
  updateQuotationStatus,
  type Quotation,
  type QuotationItem,
} from "../services/quotations";

const STATUS_CONFIG: Record<string, { label: string; color: "default" | "warning" | "success" | "error" | "info" }> = {
  draft:     { label: "Borrador",  color: "warning" },
  sent:      { label: "Enviado",   color: "info" },
  accepted:  { label: "Aceptado", color: "success" },
  cancelled: { label: "Cancelado", color: "error" },
};

const STATUS_ACTIONS: Record<string, { label: string; next: string }[]> = {
  draft:    [{ label: "Marcar como enviado", next: "sent" }, { label: "Cancelar", next: "cancelled" }],
  sent:     [{ label: "Marcar como aceptado", next: "accepted" }, { label: "Cancelar", next: "cancelled" }],
  accepted: [],
  cancelled: [],
};

function formatARS(value: number): string {
  return value.toLocaleString("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 });
}

const QuotationDetailPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const quotationId = parseInt(id ?? "0");

  const [quotation, setQuotation] = useState<Quotation | null>(null);
  const [items, setItems] = useState<QuotationItem[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [pieces, setPieces] = useState<Piece[]>([]);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  // Form agregar ítem
  const [pieceId, setPieceId] = useState<number | "">("");
  const [materialId, setMaterialId] = useState<number | "">("");
  const [quantity, setQuantity] = useState(1);
  const [margin, setMargin] = useState(20);
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [deleteItemId, setDeleteItemId] = useState<number | null>(null);
  const [changingStatus, setChangingStatus] = useState(false);

  useEffect(() => { loadAll(); }, [quotationId]);

  async function loadAll() {
    try {
      setLoading(true);
      const [q, its, c, p, m] = await Promise.all([
        getQuotation(quotationId),
        getQuotationItems(quotationId),
        getClients(),
        getPieces(),
        getMaterials(),
      ]);
      setQuotation(q);
      setItems(its);
      setClients(c);
      setPieces(p);
      setMaterials(m);
    } catch {
      setError("No se pudo cargar la cotización.");
    } finally {
      setLoading(false);
    }
  }

  function matName(mid: number) { return materials.find((m) => m.id === mid)?.name ?? `#${mid}`; }
  function pcName(pid: number) { return pieces.find((p) => p.id === pid)?.name ?? `#${pid}`; }
  function clName(cid: number) { return clients.find((c) => c.id === cid)?.name ?? `#${cid}`; }

  function handlePieceChange(pid: number | "") {
    setPieceId(pid);
    if (pid !== "") {
      const piece = pieces.find((p) => p.id === pid);
      if (piece?.material_id) setMaterialId(piece.material_id);
    }
  }

  async function handleDeleteItem() {
    if (deleteItemId === null) return;
    try {
      await deleteQuotationItem(deleteItemId);
      setDeleteItemId(null);
      setToast("Ítem eliminado.");
      await loadAll();
    } catch {
      setToast("Error al eliminar el ítem.");
    }
  }

  async function handleStatusChange(next: string) {
    if (!quotation) return;
    setChangingStatus(true);
    try {
      const updated = await updateQuotationStatus(quotation.id, next);
      setQuotation(updated);
      setToast("Estado actualizado.");
    } catch {
      setToast("Error al actualizar el estado.");
    } finally {
      setChangingStatus(false);
    }
  }

  async function handleAddItem() {
    if (!quotation || pieceId === "" || materialId === "") return;
    setAdding(true);
    setAddError(null);
    try {
      await createQuotationItem({
        quotation_id: quotation.id,
        piece_id: pieceId as number,
        material_id: materialId as number,
        quantity,
        margin_percent: margin,
      });
      setToast("Ítem agregado.");
      setPieceId("");
      setMaterialId("");
      setQuantity(1);
      setMargin(20);
      await loadAll();
    } catch {
      setAddError("Error al agregar ítem. Verificá que el material tenga configuración de máquina.");
    } finally {
      setAdding(false);
    }
  }

  const selectedPiece = pieces.find((p) => p.id === pieceId);

  if (loading) {
    return <Box display="flex" justifyContent="center" mt={6}><CircularProgress /></Box>;
  }

  if (error || !quotation) {
    return <Alert severity="error">{error ?? "Cotización no encontrada."}</Alert>;
  }

  return (
    <Box display="flex" flexDirection="column" gap={3}>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="flex-start">
        <Box>
          <Box display="flex" alignItems="center" gap={1.5} mb={0.75}>
            <Button startIcon={<ArrowBack />} onClick={() => navigate("/quotations")} size="small" sx={{ mr: 0.5 }}>
              Volver
            </Button>
            <Box sx={{ width: 3, height: 26, bgcolor: "primary.main", borderRadius: 1, boxShadow: "0 0 10px rgba(255,107,0,0.6)", flexShrink: 0 }} />
            <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 700, fontSize: "1.8rem", letterSpacing: "0.05em", textTransform: "uppercase", lineHeight: 1 }}>
              {quotation.number}
            </Typography>
          </Box>
          <Typography sx={{ color: "text.secondary", fontSize: "0.82rem", ml: "19px" }}>
            {clName(quotation.client_id)} · {new Date(quotation.issue_date).toLocaleDateString("es-AR")}
          </Typography>
        </Box>
        <Box display="flex" alignItems="center" gap={1.5}>
          {(() => {
            const s = STATUS_CONFIG[quotation.status] ?? { label: quotation.status, color: "default" as const };
            return <Chip label={s.label} color={s.color} size="small" />;
          })()}
          {(STATUS_ACTIONS[quotation.status] ?? []).map((action) => (
            <Button
              key={action.next}
              size="small"
              variant="outlined"
              color={action.next === "cancelled" ? "error" : "primary"}
              disabled={changingStatus}
              onClick={() => handleStatusChange(action.next)}
            >
              {action.label}
            </Button>
          ))}
          <Button variant="contained" startIcon={<PictureAsPdf />} onClick={() => window.open(getQuotationPdfUrl(quotation.id), "_blank")}>
            PDF
          </Button>
        </Box>
      </Box>

      {/* Info cotización */}
      <Paper variant="outlined" sx={{ p: 2.5 }}>
        <Box display="flex" gap={4} flexWrap="wrap">
          {[
            { label: "Cliente", value: clName(quotation.client_id) },
            { label: "Fecha emisión", value: new Date(quotation.issue_date).toLocaleDateString("es-AR") },
            ...(quotation.due_date ? [{ label: "Vencimiento", value: new Date(quotation.due_date).toLocaleDateString("es-AR") }] : []),
            { label: "Moneda", value: quotation.currency },
            ...(quotation.exchange_rate ? [{ label: "Tipo de cambio", value: quotation.exchange_rate.toLocaleString("es-AR") }] : []),
          ].map(({ label, value }) => (
            <Box key={label}>
              <Typography sx={{ fontSize: "0.72rem", letterSpacing: "0.08em", textTransform: "uppercase", color: "text.secondary", mb: 0.25 }}>
                {label}
              </Typography>
              <Typography sx={{ fontWeight: 500 }}>{value}</Typography>
            </Box>
          ))}
        </Box>
        {quotation.notes && (
          <Typography variant="body2" color="text.secondary" mt={1.5}>{quotation.notes}</Typography>
        )}
      </Paper>

      {/* Ítems */}
      <Box>
        <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 600, fontSize: "0.78rem", letterSpacing: "0.1em", textTransform: "uppercase", color: "text.secondary", mb: 1.5 }}>
          Ítems ({items.length})
        </Typography>
        {items.length === 0 ? (
          <Typography color="text.secondary" fontSize="0.875rem">Sin ítems todavía.</Typography>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Pieza</TableCell>
                  <TableCell>Material</TableCell>
                  <TableCell align="right">Cant.</TableCell>
                  <TableCell align="right">Margen</TableCell>
                  <TableCell align="right">Costo mat.</TableCell>
                  <TableCell align="right">Costo máq.</TableCell>
                  <TableCell align="right">Costo MO</TableCell>
                  <TableCell align="right">P. unitario</TableCell>
                  <TableCell align="right">Total</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell sx={{ fontWeight: 500 }}>{pcName(item.piece_id)}</TableCell>
                    <TableCell>{matName(item.material_id)}</TableCell>
                    <TableCell align="right"><span className="mono">{item.quantity}</span></TableCell>
                    <TableCell align="right"><span className="mono">{item.margin_percent}%</span></TableCell>
                    <TableCell align="right"><span className="mono">{formatARS(item.cost_material_ars)}</span></TableCell>
                    <TableCell align="right"><span className="mono">{formatARS(item.cost_machine_ars)}</span></TableCell>
                    <TableCell align="right"><span className="mono">{formatARS(item.cost_labor_ars)}</span></TableCell>
                    <TableCell align="right"><span className="mono">{formatARS(item.unit_price_ars)}</span></TableCell>
                    <TableCell align="right">
                      <span className="mono" style={{ fontWeight: 600, color: "#FF6B00" }}>
                        {formatARS(item.total_price_ars)}
                      </span>
                    </TableCell>
                    <TableCell align="center" sx={{ py: 0 }}>
                      <Tooltip title="Eliminar ítem">
                        <IconButton size="small" color="error" onClick={() => setDeleteItemId(item.id)}>
                          <Delete fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Box>

      {/* Total */}
      <Box display="flex" justifyContent="flex-end">
        <Paper variant="outlined" sx={{ p: 2, minWidth: 240 }}>
          <Box display="flex" justifyContent="space-between" alignItems="center">
            <Typography sx={{ color: "text.secondary", fontSize: "0.875rem" }}>Total ARS</Typography>
            <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 700, fontSize: "1.5rem", color: "primary.main" }}>
              {formatARS(quotation.total_ars)}
            </Typography>
          </Box>
          {quotation.total_usd > 0 && (
            <Box display="flex" justifyContent="space-between" alignItems="center" mt={0.5}>
              <Typography sx={{ color: "text.secondary", fontSize: "0.8rem" }}>Total USD</Typography>
              <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 600, fontSize: "1rem", color: "text.secondary" }}>
                {quotation.total_usd.toLocaleString("es-AR", { style: "currency", currency: "USD" })}
              </Typography>
            </Box>
          )}
        </Paper>
      </Box>

      <Divider />

      {/* Agregar ítem */}
      <Box>
        <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 600, fontSize: "0.78rem", letterSpacing: "0.1em", textTransform: "uppercase", color: "text.secondary", mb: 2 }}>
          Agregar ítem
        </Typography>

        {addError && <Alert severity="error" sx={{ mb: 2 }}>{addError}</Alert>}

        <Box display="flex" flexWrap="wrap" gap={2} alignItems="flex-start">
          <FormControl sx={{ minWidth: 220 }} required>
            <InputLabel>Pieza</InputLabel>
            <Select label="Pieza" value={pieceId} onChange={(e) => handlePieceChange(e.target.value as number | "")}>
              {pieces.map((p) => (
                <MenuItem key={p.id} value={p.id}>
                  <Box display="flex" alignItems="center" gap={1}>
                    {p.name}
                    {p.length_cut_mm == null && (
                      <Tooltip title="Sin DXF"><WarningAmber fontSize="small" color="warning" /></Tooltip>
                    )}
                  </Box>
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl sx={{ minWidth: 200 }} required>
            <InputLabel>Material</InputLabel>
            <Select label="Material" value={materialId} onChange={(e) => setMaterialId(e.target.value as number | "")}>
              {materials.map((m) => (
                <MenuItem key={m.id} value={m.id}>{m.name} — {m.thickness_mm}mm</MenuItem>
              ))}
            </Select>
          </FormControl>

          <TextField label="Cantidad" type="number" value={quantity} onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value) || 1))} sx={{ width: 100 }} inputProps={{ min: 1 }} />
          <TextField label="Margen %" type="number" value={margin} onChange={(e) => setMargin(parseFloat(e.target.value) || 0)} sx={{ width: 110 }} />

          <Button variant="contained" onClick={handleAddItem} disabled={adding || pieceId === "" || materialId === ""} sx={{ alignSelf: "center", mt: 0.5 }}>
            {adding ? "Agregando..." : "Agregar"}
          </Button>
        </Box>

        {selectedPiece && selectedPiece.length_cut_mm == null && (
          <Alert severity="warning" sx={{ mt: 2 }}>Esta pieza no tiene DXF cargado. Los costos serán 0.</Alert>
        )}
      </Box>

      {/* Confirmar eliminar ítem */}
      <Dialog open={deleteItemId !== null} onClose={() => setDeleteItemId(null)}>
        <DialogTitle>Eliminar ítem</DialogTitle>
        <DialogContent>
          <Typography>¿Confirmás que querés eliminar este ítem? Se recalcularán los totales.</Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteItemId(null)}>Cancelar</Button>
          <Button color="error" variant="contained" onClick={handleDeleteItem}>Eliminar</Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={!!toast} autoHideDuration={3000} onClose={() => setToast(null)} message={toast} />
    </Box>
  );
};

export default QuotationDetailPage;
