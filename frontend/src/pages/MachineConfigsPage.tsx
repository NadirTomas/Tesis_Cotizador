import { Add, Delete, Edit } from "@mui/icons-material";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Snackbar,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { usePaginatedList } from "../hooks/usePaginatedList";

import { getMaterials, type Material } from "../services/materials";
import {
  createMachineConfig,
  deleteMachineConfig,
  getMachineConfigs,
  updateMachineConfig,
  type MachineConfig,
  type MachineConfigCreate,
} from "../services/machineConfigs";

const EMPTY_FORM: MachineConfigCreate = {
  material_id: 0,
  cut_speed_mm_min: 0,
  machine_cost_per_hour_ars: 0,
  setup_time_min: 0,
  labor_percent: 30,
  kerf_mm: 0,
  minimum_spacing_mm: 0,
};

const MachineConfigsPage = () => {
  const [configs, setConfigs] = useState<MachineConfig[]>([]);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<MachineConfigCreate>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const [deleteId, setDeleteId] = useState<number | null>(null);

  const { paginatedItems, page, rowsPerPage, totalCount, handlePageChange, handleRowsPerPageChange } =
    usePaginatedList(configs, 20);

  useEffect(() => { loadAll(); }, []);

  async function loadAll() {
    try {
      setLoading(true);
      const [c, m] = await Promise.all([getMachineConfigs(), getMaterials()]);
      setConfigs(c);
      setMaterials(m);
    } catch {
      setError("No se pudieron cargar las configuraciones.");
    } finally {
      setLoading(false);
    }
  }

  function materialName(id: number): string {
    return materials.find((m) => m.id === id)?.name ?? `#${id}`;
  }

  function materialThickness(id: number): number | null {
    return materials.find((m) => m.id === id)?.thickness_mm ?? null;
  }

  function openCreate() {
    setEditingId(null);
    setForm({ ...EMPTY_FORM, material_id: materials[0]?.id ?? 0 });
    setDialogOpen(true);
  }

  function openEdit(c: MachineConfig) {
    setEditingId(c.id);
    setForm({
      material_id: c.material_id,
      cut_speed_mm_min: c.cut_speed_mm_min,
      machine_cost_per_hour_ars: c.machine_cost_per_hour_ars,
      setup_time_min: c.setup_time_min,
      labor_percent: c.labor_percent,
      kerf_mm: c.kerf_mm,
      minimum_spacing_mm: c.minimum_spacing_mm,
    });
    setDialogOpen(true);
  }

  function handleNum(field: keyof MachineConfigCreate, value: string, min = -Infinity) {
    const parsed = parseFloat(value);
    const safe = Number.isNaN(parsed) ? 0 : parsed;
    setForm((prev) => ({ ...prev, [field]: Math.max(min, safe) }));
  }

  async function handleSave() {
    if (!form.material_id) return;
    setSaving(true);
    try {
      if (editingId !== null) {
        await updateMachineConfig(editingId, form);
        setToast("Configuración actualizada.");
      } else {
        await createMachineConfig(form);
        setToast("Configuración creada.");
      }
      setDialogOpen(false);
      await loadAll();
    } catch {
      setToast("Error al guardar la configuración.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (deleteId === null) return;
    try {
      await deleteMachineConfig(deleteId);
      setToast("Configuración eliminada.");
      setDeleteId(null);
      await loadAll();
    } catch {
      setToast("Error al eliminar la configuración.");
    }
  }

  if (loading) {
    return <Box display="flex" justifyContent="center" mt={6}><CircularProgress /></Box>;
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="flex-start" flexWrap="wrap" gap={2} mb={4}>
        <Box>
          <Box display="flex" alignItems="center" gap={1.5} mb={0.75}>
            <Box sx={{ width: 3, height: 26, bgcolor: "#A78BFA", borderRadius: 1, boxShadow: "0 0 10px rgba(167,139,250,0.5)", flexShrink: 0 }} />
            <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 700, fontSize: "1.8rem", letterSpacing: "0.05em", textTransform: "uppercase", lineHeight: 1 }}>
              Configuración de máquina
            </Typography>
          </Box>
          <Typography sx={{ color: "text.secondary", fontSize: "0.82rem", ml: "19px" }}>
            Velocidad de corte, costo por hora y mano de obra por material
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={<Add />}
          onClick={openCreate}
          disabled={materials.length === 0}
        >
          Nueva configuración
        </Button>
      </Box>

      {materials.length === 0 && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          Primero creá al menos un material antes de configurar la máquina.
        </Alert>
      )}

      {configs.length === 0 && materials.length > 0 ? (
        <Typography color="text.secondary">No hay configuraciones de máquina.</Typography>
      ) : configs.length > 0 && (
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Material</TableCell>
                <TableCell align="right">Espesor (mm)</TableCell>
                <TableCell align="right">Vel. corte (mm/min)</TableCell>
                <TableCell align="right">Costo/hora (ARS)</TableCell>
                <TableCell align="right">Setup (min)</TableCell>
                <TableCell align="right">MO (%)</TableCell>
                <TableCell align="right">Kerf (mm)</TableCell>
                <TableCell align="right">Sep. mín. (mm)</TableCell>
                <TableCell align="center">Acciones</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {paginatedItems.map((c) => (
                <TableRow key={c.id}>
                  <TableCell sx={{ fontWeight: 500 }}>{materialName(c.material_id)}</TableCell>
                  <TableCell align="right">
                    <span className="mono">{materialThickness(c.material_id) ?? "—"}</span>
                  </TableCell>
                  <TableCell align="right">
                    <span className="mono">{c.cut_speed_mm_min.toLocaleString("es-AR")}</span>
                  </TableCell>
                  <TableCell align="right">
                    <span className="mono">
                      {c.machine_cost_per_hour_ars.toLocaleString("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 })}
                    </span>
                  </TableCell>
                  <TableCell align="right">
                    <span className="mono">{c.setup_time_min}</span>
                  </TableCell>
                  <TableCell align="right">
                    <span className="mono" style={{ color: "#FF6B00" }}>{c.labor_percent}%</span>
                  </TableCell>
                  <TableCell align="right">
                    <span className="mono">{c.kerf_mm}</span>
                  </TableCell>
                  <TableCell align="right">
                    <span className="mono">{c.minimum_spacing_mm}</span>
                  </TableCell>
                  <TableCell align="center">
                    <IconButton size="small" onClick={() => openEdit(c)}>
                      <Edit fontSize="small" />
                    </IconButton>
                    <IconButton size="small" color="error" onClick={() => setDeleteId(c.id)}>
                      <Delete fontSize="small" />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <TablePagination
            component="div"
            count={totalCount}
            page={page}
            rowsPerPage={rowsPerPage}
            onPageChange={handlePageChange}
            onRowsPerPageChange={handleRowsPerPageChange}
            rowsPerPageOptions={[10, 20, 50]}
            labelRowsPerPage="Filas:"
            labelDisplayedRows={({ from, to, count }) => `${from}-${to} de ${count}`}
          />
        </TableContainer>
      )}

      {/* Modal crear / editar */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>{editingId ? "Editar configuración" : "Nueva configuración"}</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <FormControl fullWidth required>
            <InputLabel>Material</InputLabel>
            <Select
              label="Material"
              value={form.material_id}
              onChange={(e) => setForm((prev) => ({ ...prev, material_id: e.target.value as number }))}
              disabled={editingId !== null}
            >
              {materials.map((m) => (
                <MenuItem key={m.id} value={m.id}>
                  {m.name} — {m.thickness_mm}mm
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            label="Velocidad de corte (mm/min)"
            type="number"
            value={form.cut_speed_mm_min}
            onChange={(e) => handleNum("cut_speed_mm_min", e.target.value)}
            fullWidth required
            helperText="Velocidad típica: acero 3mm ≈ 3000 mm/min"
          />
          <TextField
            label="Costo por hora de máquina (ARS)"
            type="number"
            value={form.machine_cost_per_hour_ars}
            onChange={(e) => handleNum("machine_cost_per_hour_ars", e.target.value)}
            fullWidth required
          />
          <TextField
            label="Tiempo de setup (min)"
            type="number"
            value={form.setup_time_min}
            onChange={(e) => handleNum("setup_time_min", e.target.value)}
            fullWidth required
            helperText="Tiempo de preparación por trabajo"
          />
          <TextField
            label="Mano de obra (%)"
            type="number"
            value={form.labor_percent}
            onChange={(e) => handleNum("labor_percent", e.target.value)}
            fullWidth required
            helperText="Porcentaje sobre el costo de máquina"
          />
          <TextField
            label="Kerf (mm)"
            type="number"
            value={form.kerf_mm}
            onChange={(e) => handleNum("kerf_mm", e.target.value, 0)}
            slotProps={{ htmlInput: { min: 0, step: "0.1" } }}
            fullWidth
            helperText="Ancho aproximado de material removido por el láser."
          />
          <TextField
            label="Separación mínima (mm)"
            type="number"
            value={form.minimum_spacing_mm}
            onChange={(e) => handleNum("minimum_spacing_mm", e.target.value, 0)}
            slotProps={{ htmlInput: { min: 0, step: "0.1" } }}
            fullWidth
            helperText="Distancia de seguridad entre piezas/contornos usada en colocación y stock."
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)} disabled={saving}>Cancelar</Button>
          <Button variant="contained" onClick={handleSave} disabled={saving || !form.material_id}>
            {saving ? "Guardando..." : "Guardar"}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Confirmación eliminación */}
      <Dialog open={deleteId !== null} onClose={() => setDeleteId(null)}>
        <DialogTitle>Eliminar configuración</DialogTitle>
        <DialogContent>
          <Typography>¿Confirmás que querés eliminar esta configuración?</Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteId(null)}>Cancelar</Button>
          <Button color="error" variant="contained" onClick={handleDelete}>Eliminar</Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={!!toast} autoHideDuration={3000} onClose={() => setToast(null)} message={toast} />
    </Box>
  );
};

export default MachineConfigsPage;
