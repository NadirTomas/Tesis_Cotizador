import {
  AddCircleOutline,
  ArrowBack,
  Delete,
  Edit,
  PictureAsPdf,
  PlaylistAdd,
  RemoveCircleOutline,
  SyncAlt,
  WarningAmber,
} from "@mui/icons-material";
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

import StockGeometryView from "../components/StockGeometryView";
import { getClients, type Client } from "../services/clients";
import { getMaterials, type Material } from "../services/materials";
import { getPieces, type Piece } from "../services/pieces";
import { openAuthedResource } from "../services/authedResource";
import {
  createQuotationItem,
  deleteQuotationItem,
  getQuotation,
  getQuotationEvents,
  getQuotationItems,
  getQuotationPdfUrl,
  updateQuotationStatus,
  type Quotation,
  type QuotationEvent,
  type QuotationItem,
} from "../services/quotations";
import { confirmCut, getStockSheet, listStockReservations, recommendStock, reserveStock, type StockRecommendation, type StockSheet } from "../services/stock";

const EVENT_ICONS: Record<string, React.ElementType> = {
  created: AddCircleOutline,
  status_changed: SyncAlt,
  item_added: PlaylistAdd,
  item_updated: Edit,
  item_removed: RemoveCircleOutline,
};

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
  const [events, setEvents] = useState<QuotationEvent[]>([]);
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

  // Recomendación de stock (informativa mientras la cotización no está aceptada)
  const [recommendations, setRecommendations] = useState<StockRecommendation[] | null>(null);
  const [recommendLoading, setRecommendLoading] = useState(false);
  const [recommendError, setRecommendError] = useState<string | null>(null);
  const [locationView, setLocationView] = useState<StockRecommendation | null>(null);
  const [locationStock, setLocationStock] = useState<StockSheet | null>(null);
  const [showAlternatives, setShowAlternatives] = useState(false);

  // Reserva de material por ítem (solo disponible con la cotización aceptada)
  const [reservingItemId, setReservingItemId] = useState<number | null>(null);
  const [itemReservations, setItemReservations] = useState<Record<number, { reservationId: number; stockCode: string; cut: boolean }>>({});
  const [confirmingItemId, setConfirmingItemId] = useState<number | null>(null);

  useEffect(() => { loadAll(); }, [quotationId]);

  useEffect(() => {
    setRecommendations(null);
    setRecommendError(null);
    setShowAlternatives(false);
    if (pieceId === "" || materialId === "") return;
    const piece = pieces.find((p) => p.id === pieceId);
    if (!piece || piece.length_cut_mm == null) return; // sin DXF, no hay geometría para recomendar

    setRecommendLoading(true);
    recommendStock(pieceId as number, materialId as number)
      .then(setRecommendations)
      .catch((e: Error) => setRecommendError(e.message))
      .finally(() => setRecommendLoading(false));
  }, [pieceId, materialId]);

  useEffect(() => {
    if (!locationView) { setLocationStock(null); return; }
    getStockSheet(locationView.stock_sheet_id).then(setLocationStock).catch(() => setLocationStock(null));
  }, [locationView]);

  async function loadAll() {
    try {
      setLoading(true);
      const [q, its, c, p, m, ev] = await Promise.all([
        getQuotation(quotationId),
        getQuotationItems(quotationId),
        getClients(),
        getPieces(),
        getMaterials(),
        getQuotationEvents(quotationId),
      ]);
      setQuotation(q);
      setItems(its);
      setClients(c);
      setPieces(p);
      setMaterials(m);
      setEvents(ev);

      if (q.status === "accepted") {
        // Reconstruye qué ítems ya tienen material reservado/cortado desde
        // el backend — itemReservations es solo estado de UI, no persiste
        // entre recargas, así que sin esto el flujo reservar→cortar se
        // "pierde" al volver a esta página.
        try {
          const reservations = await listStockReservations({ quotation_id: q.id });
          const byItem: Record<number, { reservationId: number; stockCode: string; cut: boolean }> = {};
          for (const r of reservations) {
            if (r.quotation_item_id == null) continue;
            if (r.status !== "ACTIVE" && r.status !== "CONSUMED") continue;
            if (byItem[r.quotation_item_id]) continue; // ya viene ordenado por id desc, nos quedamos con la más reciente
            byItem[r.quotation_item_id] = { reservationId: r.id, stockCode: r.stock_code, cut: r.status === "CONSUMED" };
          }
          setItemReservations(byItem);
        } catch {
          // no bloquea la carga de la cotización si esto falla
        }
      }
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

  async function handleReserveForItem(item: QuotationItem) {
    if (!quotation) return;
    setReservingItemId(item.id);
    try {
      const options = await recommendStock(item.piece_id, item.material_id);
      if (options.length === 0) throw new Error("No hay stock disponible para este ítem.");
      const best = options[0];
      const reservation = await reserveStock(best.stock_sheet_id, {
        piece_id: item.piece_id,
        material_id: item.material_id,
        quotation_id: quotation.id,
        quotation_item_id: item.id,
      });
      setItemReservations((prev) => ({ ...prev, [item.id]: { reservationId: reservation.id, stockCode: best.stock_code, cut: false } }));
      setToast(`Material reservado: ${best.stock_code}.`);
    } catch (e: any) {
      setToast(e.message ?? "Error al reservar material.");
    } finally {
      setReservingItemId(null);
    }
  }

  async function handleConfirmCutForItem(item: QuotationItem) {
    const reservation = itemReservations[item.id];
    if (!reservation) return;
    setConfirmingItemId(item.id);
    try {
      const result = await confirmCut(reservation.reservationId);
      setItemReservations((prev) => ({ ...prev, [item.id]: { ...prev[item.id], cut: true } }));
      const remnantMsg = result.remnants.length > 0
        ? ` Se generó ${result.remnants.length === 1 ? "el retazo" : "los retazos"}: ${result.remnants.map((r) => r.code).join(", ")}.`
        : "";
      setToast(`Corte confirmado sobre ${result.stock_code}.${remnantMsg}`);
    } catch (e: any) {
      setToast(e.message ?? "Error al confirmar el corte.");
    } finally {
      setConfirmingItemId(null);
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
      <Box display="flex" justifyContent="space-between" alignItems="flex-start" flexWrap="wrap" gap={2}>
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
        <Box display="flex" alignItems="center" flexWrap="wrap" gap={1.5}>
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
          <Button variant="contained" startIcon={<PictureAsPdf />} onClick={() => openAuthedResource(getQuotationPdfUrl(quotation.id))}>
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
                  {quotation.status === "accepted" && <TableCell>Material</TableCell>}
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
                    {quotation.status === "accepted" && (
                      <TableCell>
                        {(() => {
                          const reservation = itemReservations[item.id];
                          if (!reservation) {
                            return (
                              <Button
                                size="small"
                                variant="outlined"
                                disabled={reservingItemId === item.id}
                                onClick={() => handleReserveForItem(item)}
                              >
                                {reservingItemId === item.id ? "Reservando..." : "Reservar material"}
                              </Button>
                            );
                          }
                          if (reservation.cut) {
                            return <Chip label={`Cortado — ${reservation.stockCode}`} color="default" size="small" />;
                          }
                          return (
                            <Box display="flex" alignItems="center" gap={1}>
                              <Chip label={`Reservado — ${reservation.stockCode}`} color="success" size="small" />
                              <Button
                                size="small"
                                variant="contained"
                                disabled={confirmingItemId === item.id}
                                onClick={() => handleConfirmCutForItem(item)}
                              >
                                {confirmingItemId === item.id ? "Confirmando..." : "Confirmar corte"}
                              </Button>
                            </Box>
                          );
                        })()}
                      </TableCell>
                    )}
                    <TableCell align="center" sx={{ py: 0 }}>
                      {(quotation.status === "draft" || quotation.status === "accepted") && (
                        <Tooltip title="Eliminar ítem">
                          <IconButton size="small" color="error" onClick={() => setDeleteItemId(item.id)}>
                            <Delete fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      )}
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

      {/* Historial */}
      <Box>
        <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 600, fontSize: "0.78rem", letterSpacing: "0.1em", textTransform: "uppercase", color: "text.secondary", mb: 1.5 }}>
          Historial
        </Typography>
        {events.length === 0 ? (
          <Typography color="text.secondary" fontSize="0.875rem">Sin actividad registrada.</Typography>
        ) : (
          <Paper variant="outlined" sx={{ p: 0 }}>
            {events.map((ev, idx) => {
              const Icon = EVENT_ICONS[ev.event_type] ?? AddCircleOutline;
              return (
                <Box
                  key={ev.id}
                  display="flex"
                  alignItems="flex-start"
                  gap={1.5}
                  sx={{
                    p: 1.5,
                    borderBottom: idx < events.length - 1 ? "1px solid" : "none",
                    borderColor: "divider",
                  }}
                >
                  <Icon fontSize="small" sx={{ color: "text.secondary", mt: 0.25 }} />
                  <Box flex={1} minWidth={0}>
                    <Typography sx={{ fontSize: "0.85rem" }}>{ev.description}</Typography>
                    <Typography sx={{ fontSize: "0.72rem", color: "text.secondary" }}>
                      {ev.created_by_email ?? "Sistema"} · {new Date(ev.created_at).toLocaleString("es-AR")}
                    </Typography>
                  </Box>
                </Box>
              );
            })}
          </Paper>
        )}
      </Box>

      <Divider />

      {/* Agregar ítem — solo mientras la cotización sigue en borrador; una
          vez enviada/aceptada su contenido queda fijo (ver backend). */}
      {quotation.status === "draft" ? (
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

        {/* Recomendación de stock */}
        {recommendLoading && (
          <Box display="flex" alignItems="center" gap={1} mt={2}>
            <CircularProgress size={16} />
            <Typography sx={{ fontSize: "0.82rem", color: "text.secondary" }}>Buscando stock compatible...</Typography>
          </Box>
        )}
        {recommendError && (
          <Alert severity="info" sx={{ mt: 2 }}>{recommendError}</Alert>
        )}
        {recommendations && recommendations.length > 0 && (
          <Paper variant="outlined" sx={{ p: 2, mt: 2 }}>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={1.5}>
              <Typography sx={{ fontSize: "0.72rem", letterSpacing: "0.08em", textTransform: "uppercase", color: "text.secondary" }}>
                Material solicitado — Stock compatible: {recommendations.length}
              </Typography>
            </Box>
            {(() => {
              const top = recommendations[0];
              return (
                <Box display="flex" alignItems="center" justifyContent="space-between" flexWrap="wrap" gap={1.5}>
                  <Box>
                    <Chip label="RECOMENDADO" color="success" size="small" sx={{ mb: 0.5 }} />
                    <Typography sx={{ fontWeight: 700, fontFamily: '"Barlow Condensed", sans-serif', fontSize: "1.1rem" }}>
                      {top.stock_code}
                    </Typography>
                    <Typography sx={{ fontSize: "0.8rem", color: "text.secondary" }}>
                      Aprovechamiento estimado: {top.utilization_percent}%
                    </Typography>
                  </Box>
                  <Box display="flex" gap={1}>
                    <Button size="small" variant="outlined" onClick={() => setLocationView(top)}>Ver ubicación</Button>
                    {recommendations.length > 1 && (
                      <Button size="small" onClick={() => setShowAlternatives((v) => !v)}>
                        {showAlternatives ? "Ocultar alternativas" : `Ver ${recommendations.length - 1} alternativa(s)`}
                      </Button>
                    )}
                  </Box>
                </Box>
              );
            })()}
            {showAlternatives && (
              <Box mt={2} display="flex" flexDirection="column" gap={1}>
                {recommendations.slice(1).map((rec) => (
                  <Box key={rec.stock_sheet_id} display="flex" justifyContent="space-between" alignItems="center" sx={{ px: 1.5, py: 1, borderRadius: 1, bgcolor: "action.hover" }}>
                    <Typography sx={{ fontSize: "0.85rem" }}>
                      <span className="mono">{rec.stock_code}</span> — {rec.stock_type === "REMNANT" ? "Retazo" : "Chapa"} · {rec.utilization_percent}% aprovechamiento
                    </Typography>
                    <Button size="small" onClick={() => setLocationView(rec)}>Ver ubicación</Button>
                  </Box>
                ))}
              </Box>
            )}
            <Typography sx={{ fontSize: "0.72rem", color: "text.secondary", mt: 1.5 }}>
              Esto no reserva material todavía — la reserva se hace por ítem una vez que la cotización esté aceptada.
            </Typography>
          </Paper>
        )}
      </Box>
      ) : (
        <Typography sx={{ fontSize: "0.82rem", color: "text.secondary" }}>
          No se pueden agregar más ítems — la cotización ya no está en borrador.
        </Typography>
      )}

      {/* Ver ubicación de la recomendación */}
      <Dialog open={!!locationView} onClose={() => setLocationView(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Ubicación en {locationView?.stock_code}</DialogTitle>
        <DialogContent>
          {locationView && !locationStock && (
            <Box display="flex" justifyContent="center" py={4}><CircularProgress size={24} /></Box>
          )}
          {locationView && locationStock && (
            <StockGeometryView
              geometry={locationStock.geometry}
              piece={{
                x: locationView.x, y: locationView.y,
                width_mm: locationView.piece_width_mm, height_mm: locationView.piece_height_mm,
                rotation: locationView.rotation,
              }}
            />
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setLocationView(null)}>Cerrar</Button>
        </DialogActions>
      </Dialog>

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
