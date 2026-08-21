import { Add, ChevronRight } from "@mui/icons-material";
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
  FormControl,
  IconButton,
  InputAdornment,
  InputLabel,
  MenuItem,
  Select,
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
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { getMaterials, type Material } from "../services/materials";
import { createStockSheet, getStock, type StockSheet, type StockStatus, type StockType } from "../services/stock";

const STATUS_CONFIG: Record<StockStatus, { label: string; color: "default" | "warning" | "success" | "error" | "info" }> = {
  AVAILABLE: { label: "Disponible", color: "success" },
  RESERVED: { label: "Reservado", color: "warning" },
  CONSUMED: { label: "Consumido", color: "default" },
  DISCARDED: { label: "Descartado", color: "error" },
};

function m2(areaMm2: number): string {
  return (areaMm2 / 1_000_000).toFixed(2);
}

const StockPage = () => {
  const navigate = useNavigate();
  const { companyRole } = useAuth();
  const isOwner = companyRole === "owner";

  const [stock, setStock] = useState<StockSheet[]>([]);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const [materialFilter, setMaterialFilter] = useState<number | "">("");
  const [statusFilter, setStatusFilter] = useState<StockStatus | "">("");
  const [typeFilter, setTypeFilter] = useState<StockType | "">("");

  const [dialogOpen, setDialogOpen] = useState(false);
  const [newMaterialId, setNewMaterialId] = useState<number | "">("");
  const [newWidth, setNewWidth] = useState(1500);
  const [newHeight, setNewHeight] = useState(3000);
  const [saving, setSaving] = useState(false);

  useEffect(() => { load(); }, [materialFilter, statusFilter, typeFilter]);
  useEffect(() => { getMaterials().then(setMaterials).catch(() => {}); }, []);

  async function load() {
    try {
      setLoading(true);
      const data = await getStock({
        material_id: materialFilter || undefined,
        status: statusFilter || undefined,
        stock_type: typeFilter || undefined,
      });
      setStock(data);
    } catch {
      setError("No se pudo cargar el stock.");
    } finally {
      setLoading(false);
    }
  }

  function materialLabel(id: number) {
    const m = materials.find((mm) => mm.id === id);
    if (!m) return `#${id}`;
    return `${m.material_type ?? m.name}${m.alloy ? ` · ${m.alloy}` : ""} · ${m.thickness_mm}mm`;
  }

  async function handleCreate() {
    if (newMaterialId === "") return;
    setSaving(true);
    try {
      await createStockSheet({
        material_id: newMaterialId, stock_type: "FULL_SHEET", width_mm: newWidth, height_mm: newHeight,
      });
      setToast("Chapa creada.");
      setDialogOpen(false);
      await load();
    } catch (e: any) {
      setToast(e.message ?? "Error al crear la chapa.");
    } finally {
      setSaving(false);
    }
  }

  const availableM2 = useMemo(
    () => stock.filter((s) => s.status === "AVAILABLE").reduce((sum, s) => sum + s.remaining_area_mm2, 0) / 1_000_000,
    [stock]
  );

  if (loading && stock.length === 0) {
    return <Box display="flex" justifyContent="center" mt={6}><CircularProgress /></Box>;
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="flex-start" flexWrap="wrap" gap={2} mb={4}>
        <Box>
          <Box display="flex" alignItems="center" gap={1.5} mb={0.75}>
            <Box sx={{ width: 3, height: 26, bgcolor: "#3D8BFF", borderRadius: 1, boxShadow: "0 0 10px rgba(61,139,255,0.5)", flexShrink: 0 }} />
            <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 700, fontSize: "1.8rem", letterSpacing: "0.05em", textTransform: "uppercase", lineHeight: 1 }}>
              Stock
            </Typography>
          </Box>
          <Typography sx={{ color: "text.secondary", fontSize: "0.82rem", ml: "19px" }}>
            Chapas y retazos disponibles · {availableM2.toFixed(2)} m² disponibles en esta vista
          </Typography>
        </Box>
        {isOwner && (
          <Button variant="contained" startIcon={<Add />} onClick={() => setDialogOpen(true)}>
            Nueva chapa
          </Button>
        )}
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Box display="flex" gap={1.5} flexWrap="wrap" mb={3}>
        <FormControl size="small" sx={{ minWidth: 220 }}>
          <InputLabel>Material</InputLabel>
          <Select label="Material" value={materialFilter} onChange={(e) => setMaterialFilter(e.target.value as number | "")}>
            <MenuItem value="">Todos</MenuItem>
            {materials.map((m) => (
              <MenuItem key={m.id} value={m.id}>{materialLabel(m.id)}</MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel>Estado</InputLabel>
          <Select label="Estado" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as StockStatus | "")}>
            <MenuItem value="">Todos</MenuItem>
            {(Object.keys(STATUS_CONFIG) as StockStatus[]).map((s) => (
              <MenuItem key={s} value={s}>{STATUS_CONFIG[s].label}</MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel>Tipo</InputLabel>
          <Select label="Tipo" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value as StockType | "")}>
            <MenuItem value="">Todos</MenuItem>
            <MenuItem value="FULL_SHEET">Chapa completa</MenuItem>
            <MenuItem value="REMNANT">Retazo</MenuItem>
          </Select>
        </FormControl>
      </Box>

      {stock.length === 0 ? (
        <Typography color="text.secondary">No hay stock que coincida con los filtros.</Typography>
      ) : (
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Código</TableCell>
                <TableCell>Material</TableCell>
                <TableCell>Tipo</TableCell>
                <TableCell>Estado</TableCell>
                <TableCell align="right">Área disp.</TableCell>
                <TableCell align="center" />
              </TableRow>
            </TableHead>
            <TableBody>
              {stock.map((s) => {
                const st = STATUS_CONFIG[s.status];
                return (
                  <TableRow key={s.id} hover sx={{ cursor: "pointer" }} onClick={() => navigate(`/stock/${s.id}`)}>
                    <TableCell sx={{ fontWeight: 600 }}><span className="mono">{s.code}</span></TableCell>
                    <TableCell sx={{ color: "text.secondary" }}>{materialLabel(s.material_id)}</TableCell>
                    <TableCell>{s.stock_type === "FULL_SHEET" ? "Chapa" : "Retazo"}</TableCell>
                    <TableCell><Chip label={st.label} color={st.color} size="small" /></TableCell>
                    <TableCell align="right">
                      <span className="mono">
                        {s.status === "AVAILABLE" || s.status === "RESERVED" ? `${m2(s.remaining_area_mm2)} m²` : "—"}
                      </span>
                    </TableCell>
                    <TableCell align="center" sx={{ py: 0 }}>
                      <IconButton size="small"><ChevronRight fontSize="small" /></IconButton>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>Nueva chapa completa</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <FormControl fullWidth required>
            <InputLabel>Material</InputLabel>
            <Select label="Material" value={newMaterialId} onChange={(e) => setNewMaterialId(e.target.value as number | "")}>
              {materials.map((m) => (
                <MenuItem key={m.id} value={m.id}>{materialLabel(m.id)}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            label="Ancho" type="number" value={newWidth} onChange={(e) => setNewWidth(Number(e.target.value))}
            fullWidth required InputProps={{ endAdornment: <InputAdornment position="end">mm</InputAdornment> }}
          />
          <TextField
            label="Alto" type="number" value={newHeight} onChange={(e) => setNewHeight(Number(e.target.value))}
            fullWidth required InputProps={{ endAdornment: <InputAdornment position="end">mm</InputAdornment> }}
          />
          <Typography sx={{ fontSize: "0.75rem", color: "text.secondary" }}>
            Se representa como un rectángulo simple. Para retazos irregulares, cargalos a partir de un corte confirmado.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)} disabled={saving}>Cancelar</Button>
          <Button variant="contained" onClick={handleCreate} disabled={saving || newMaterialId === ""}>
            {saving ? "Creando..." : "Crear"}
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={!!toast} autoHideDuration={3000} onClose={() => setToast(null)} message={toast} />
    </Box>
  );
};

export default StockPage;
