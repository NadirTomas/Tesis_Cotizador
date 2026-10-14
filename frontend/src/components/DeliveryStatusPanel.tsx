import { Add } from "@mui/icons-material";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  getQuotationDeliveryNotes,
  getQuotationDeliveryStatus,
  type DeliveryNoteSummary,
  type DeliveryStatus,
} from "../services/deliveryNotes";
import { DELIVERY_STATE, formatDate, NOTE_STATUS } from "../utils/deliveryNotes";

interface Props {
  quotationId: number;
  quotationStatus: string;
  /** Cambia cuando se confirma un corte en la misma pantalla, para recargar el estado. */
  refreshKey?: number;
}

/**
 * Estado de entrega de una cotización (cotizado / entregado / pendiente), acceso
 * a "Generar remito" y el historial de remitos. Solo informa: las cantidades las
 * calcula el backend.
 */
const DeliveryStatusPanel = ({ quotationId, quotationStatus, refreshKey = 0 }: Props) => {
  const navigate = useNavigate();
  const [status, setStatus] = useState<DeliveryStatus | null>(null);
  const [notes, setNotes] = useState<DeliveryNoteSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getQuotationDeliveryStatus(quotationId), getQuotationDeliveryNotes(quotationId)])
      .then(([s, n]) => {
        if (cancelled) return;
        setStatus(s);
        setNotes(n);
        setError(null);
      })
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : "No se pudo cargar el estado de entrega."))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [quotationId, quotationStatus, refreshKey]);

  if (loading) return <CircularProgress size={20} />;
  if (error) return <Alert severity="error">{error}</Alert>;
  if (!status) return null;
  // Una cotización que todavía no se aceptó (y nunca tuvo remitos) no tiene nada que mostrar.
  if (!status.eligible && notes.length === 0) return null;

  const state = DELIVERY_STATE[status.state];

  return (
    <Paper variant="outlined" sx={{ p: 2.5 }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={2} mb={2}>
        <Box display="flex" alignItems="center" gap={1.5}>
          <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 600, fontSize: "0.78rem", letterSpacing: "0.1em", textTransform: "uppercase", color: "text.secondary" }}>
            Entregas
          </Typography>
          <Chip label={state.label} color={state.color} size="small" />
        </Box>
        {status.eligible && (
          <Button
            variant="contained"
            size="small"
            startIcon={<Add />}
            disabled={status.total_pending === 0}
            onClick={() => navigate(`/delivery-notes/new?quotation=${quotationId}`)}
          >
            Generar remito
          </Button>
        )}
      </Box>

      <Box display="flex" gap={4} flexWrap="wrap" mb={2}>
        {[
          { label: "Cantidad total", value: status.total_quoted },
          { label: "Entregada", value: status.total_delivered },
          { label: "Pendiente", value: status.total_pending },
        ].map(({ label, value }) => (
          <Box key={label}>
            <Typography sx={{ fontSize: "0.72rem", letterSpacing: "0.08em", textTransform: "uppercase", color: "text.secondary", mb: 0.25 }}>
              {label}
            </Typography>
            <Typography className="mono" sx={{ fontWeight: 600, fontSize: "1.1rem" }}>{value}</Typography>
          </Box>
        ))}
      </Box>

      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Pieza</TableCell>
            <TableCell align="right">Cotizado</TableCell>
            <TableCell align="right">Entregado</TableCell>
            <TableCell align="right">Pendiente</TableCell>
            <TableCell align="center">Corte</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {status.items.map((line) => (
            <TableRow key={line.quotation_item_id}>
              <TableCell sx={{ fontWeight: 500 }}>{line.piece_name}</TableCell>
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
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {status.eligible && !status.cut_confirmed && (
        <Alert severity="info" sx={{ mt: 2 }}>
          Un remito solo se puede emitir cuando el corte de sus piezas está confirmado (reservá material y confirmá el corte más abajo). Los borradores se pueden preparar antes.
        </Alert>
      )}

      {notes.length > 0 && (
        <Box mt={2.5}>
          <Typography sx={{ fontSize: "0.72rem", letterSpacing: "0.08em", textTransform: "uppercase", color: "text.secondary", mb: 1 }}>
            Historial de remitos
          </Typography>
          <Table size="small">
            <TableBody>
              {notes.map((n) => (
                <TableRow key={n.id} hover sx={{ cursor: "pointer" }} onClick={() => navigate(`/delivery-notes/${n.id}`)}>
                  <TableCell>
                    <span className="mono" style={{ fontWeight: 500 }}>{n.number ?? "Sin número"}</span>
                  </TableCell>
                  <TableCell sx={{ color: "text.secondary" }}>{formatDate(n.issue_date ?? n.created_at)}</TableCell>
                  <TableCell align="right"><span className="mono">{n.total_units}</span> u.</TableCell>
                  <TableCell align="right">
                    <Chip label={NOTE_STATUS[n.status].label} color={NOTE_STATUS[n.status].color} size="small" />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      )}
    </Paper>
  );
};

export default DeliveryStatusPanel;
