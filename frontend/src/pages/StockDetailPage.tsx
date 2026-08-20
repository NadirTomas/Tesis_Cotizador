import { ArrowBack, Block } from "@mui/icons-material";
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
  Paper,
  Snackbar,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import StockGeometryView from "../components/StockGeometryView";
import { useAuth } from "../context/AuthContext";
import { getMaterials, type Material } from "../services/materials";
import { getQuotation, type Quotation } from "../services/quotations";
import {
  discardStockSheet,
  getStockMovements,
  getStockSheet,
  type StockMovement,
  type StockSheet,
} from "../services/stock";

const STATUS_CONFIG: Record<string, { label: string; color: "default" | "warning" | "success" | "error" }> = {
  AVAILABLE: { label: "Disponible", color: "success" },
  RESERVED: { label: "Reservado", color: "warning" },
  CONSUMED: { label: "Consumido", color: "default" },
  DISCARDED: { label: "Descartado", color: "error" },
};

const MOVEMENT_LABELS: Record<string, string> = {
  CREATED: "Creado",
  RESERVED: "Reservado",
  RELEASED: "Liberado",
  CONSUMED: "Consumido (corte confirmado)",
  REMNANT_CREATED: "Generado como retazo",
  DISCARDED: "Descartado",
  ADJUSTED: "Ajustado",
};

const StockDetailPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { companyRole } = useAuth();
  const isOwner = companyRole === "owner";
  const stockId = parseInt(id ?? "0");

  const [stock, setStock] = useState<StockSheet | null>(null);
  const [material, setMaterial] = useState<Material | null>(null);
  const [sourceSheet, setSourceSheet] = useState<StockSheet | null>(null);
  const [sourceQuotation, setSourceQuotation] = useState<Quotation | null>(null);
  const [movements, setMovements] = useState<StockMovement[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [confirmDiscard, setConfirmDiscard] = useState(false);

  useEffect(() => { load(); }, [stockId]);

  async function load() {
    try {
      setLoading(true);
      const s = await getStockSheet(stockId);
      setStock(s);

      const materials = await getMaterials();
      setMaterial(materials.find((m) => m.id === s.material_id) ?? null);

      if (s.source_sheet_id) {
        getStockSheet(s.source_sheet_id).then(setSourceSheet).catch(() => {});
      }
      if (s.source_quotation_id) {
        getQuotation(s.source_quotation_id).then(setSourceQuotation).catch(() => {});
      }
      if (isOwner) {
        getStockMovements(stockId).then(setMovements).catch(() => setMovements([]));
      }
    } catch {
      setError("No se pudo cargar el stock.");
    } finally {
      setLoading(false);
    }
  }

  async function handleDiscard() {
    if (!stock) return;
    try {
      const updated = await discardStockSheet(stock.id);
      setStock(updated);
      setToast("Stock descartado.");
      setConfirmDiscard(false);
    } catch (e: any) {
      setToast(e.message ?? "Error al descartar.");
    }
  }

  if (loading) return <Box display="flex" justifyContent="center" mt={6}><CircularProgress /></Box>;
  if (error || !stock) return <Alert severity="error">{error ?? "Stock no encontrado."}</Alert>;

  const st = STATUS_CONFIG[stock.status] ?? { label: stock.status, color: "default" as const };

  return (
    <Box display="flex" flexDirection="column" gap={3}>
      <Box display="flex" justifyContent="space-between" alignItems="flex-start">
        <Box>
          <Box display="flex" alignItems="center" gap={1.5} mb={0.75}>
            <Button startIcon={<ArrowBack />} onClick={() => navigate("/stock")} size="small" sx={{ mr: 0.5 }}>
              Volver
            </Button>
            <Box sx={{ width: 3, height: 26, bgcolor: "primary.main", borderRadius: 1, boxShadow: "0 0 10px rgba(255,107,0,0.6)", flexShrink: 0 }} />
            <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 700, fontSize: "1.8rem", letterSpacing: "0.05em", textTransform: "uppercase", lineHeight: 1 }}>
              {stock.code}
            </Typography>
          </Box>
          <Typography sx={{ color: "text.secondary", fontSize: "0.82rem", ml: "19px" }}>
            {stock.stock_type === "FULL_SHEET" ? "Chapa completa" : "Retazo"} · creado el {new Date(stock.created_at).toLocaleDateString("es-AR")}
          </Typography>
        </Box>
        <Box display="flex" alignItems="center" gap={1.5}>
          <Chip label={st.label} color={st.color} size="small" />
          {isOwner && stock.status !== "DISCARDED" && stock.status !== "CONSUMED" && (
            <Button size="small" variant="outlined" color="error" startIcon={<Block />} onClick={() => setConfirmDiscard(true)}>
              Descartar
            </Button>
          )}
        </Box>
      </Box>

      <Box display="flex" gap={3} flexWrap="wrap" alignItems="flex-start">
        <Paper variant="outlined" sx={{ p: 2, flex: "0 0 auto" }}>
          <StockGeometryView geometry={stock.geometry} label="Geometría" />
        </Paper>

        <Box flex={1} minWidth={260} display="flex" flexDirection="column" gap={2}>
          <Paper variant="outlined" sx={{ p: 2.5 }}>
            <Typography sx={{ fontSize: "0.72rem", letterSpacing: "0.08em", textTransform: "uppercase", color: "text.secondary", mb: 1.5 }}>
              Datos
            </Typography>
            <Box display="flex" flexDirection="column" gap={1}>
              <Row label="Material" value={material ? `${material.material_type ?? material.name}` : "—"} />
              <Row label="Calidad / aleación" value={material?.alloy ?? "—"} />
              <Row label="Espesor" value={material ? `${material.thickness_mm} mm` : "—"} />
              <Row label="Área original" value={`${(stock.original_area_mm2 / 1_000_000).toFixed(2)} m²`} />
              <Row
                label="Área disponible"
                value={
                  stock.status === "AVAILABLE" || stock.status === "RESERVED"
                    ? `${(stock.remaining_area_mm2 / 1_000_000).toFixed(2)} m²`
                    : "—"
                }
              />
              {stock.original_width_mm && stock.original_height_mm && (
                <Row label="Dimensiones (bbox)" value={`${stock.original_width_mm.toFixed(0)} × ${stock.original_height_mm.toFixed(0)} mm`} />
              )}
            </Box>
          </Paper>

          <Paper variant="outlined" sx={{ p: 2.5 }}>
            <Typography sx={{ fontSize: "0.72rem", letterSpacing: "0.08em", textTransform: "uppercase", color: "text.secondary", mb: 1.5 }}>
              Procedencia
            </Typography>
            {sourceSheet ? (
              <Typography sx={{ fontSize: "0.85rem" }}>
                Retazo de{" "}
                <Box component="span" sx={{ color: "primary.main", cursor: "pointer", fontWeight: 600 }} onClick={() => navigate(`/stock/${sourceSheet.id}`)}>
                  {sourceSheet.code}
                </Box>
              </Typography>
            ) : (
              <Typography sx={{ fontSize: "0.85rem", color: "text.secondary" }}>Chapa de origen (sin retazo previo).</Typography>
            )}
            {sourceQuotation && (
              <Typography sx={{ fontSize: "0.85rem", mt: 0.5 }}>
                Cortada para la cotización{" "}
                <Box component="span" sx={{ color: "primary.main", cursor: "pointer", fontWeight: 600 }} onClick={() => navigate(`/quotations/${sourceQuotation.id}`)}>
                  {sourceQuotation.number}
                </Box>
              </Typography>
            )}
          </Paper>

          {isOwner && movements && (
            <Paper variant="outlined" sx={{ p: 0 }}>
              <Typography sx={{ fontSize: "0.72rem", letterSpacing: "0.08em", textTransform: "uppercase", color: "text.secondary", p: 2.5, pb: 1.5 }}>
                Movimientos
              </Typography>
              {movements.length === 0 ? (
                <Typography sx={{ fontSize: "0.85rem", color: "text.secondary", px: 2.5, pb: 2.5 }}>Sin movimientos.</Typography>
              ) : (
                movements.map((mv, idx) => (
                  <Box key={mv.id}>
                    {idx > 0 && <Divider />}
                    <Box sx={{ px: 2.5, py: 1.25, display: "flex", justifyContent: "space-between" }}>
                      <Typography sx={{ fontSize: "0.82rem" }}>{MOVEMENT_LABELS[mv.movement_type] ?? mv.movement_type}</Typography>
                      <Typography sx={{ fontSize: "0.72rem", color: "text.secondary" }}>
                        {new Date(mv.created_at).toLocaleString("es-AR")}
                      </Typography>
                    </Box>
                  </Box>
                ))
              )}
            </Paper>
          )}
        </Box>
      </Box>

      <Dialog open={confirmDiscard} onClose={() => setConfirmDiscard(false)}>
        <DialogTitle>Descartar stock</DialogTitle>
        <DialogContent>
          <Typography>¿Confirmás que querés descartar <b>{stock.code}</b>? No va a poder usarse en futuras reservas.</Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDiscard(false)}>Cancelar</Button>
          <Button color="error" variant="contained" onClick={handleDiscard}>Descartar</Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={!!toast} autoHideDuration={3000} onClose={() => setToast(null)} message={toast} />
    </Box>
  );
};

function Row({ label, value }: { label: string; value: string }) {
  return (
    <Box display="flex" justifyContent="space-between">
      <Typography sx={{ fontSize: "0.82rem", color: "text.secondary" }}>{label}</Typography>
      <Typography sx={{ fontSize: "0.82rem", fontWeight: 500 }}>{value}</Typography>
    </Box>
  );
}

export default StockDetailPage;
