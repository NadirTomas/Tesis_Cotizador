import { Add, Delete, Edit, Search } from "@mui/icons-material";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  InputAdornment,
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
import { useMemo, useEffect, useState } from "react";
import { usePaginatedList } from "../hooks/usePaginatedList";

import {
  type Material,
  type MaterialCreate,
  createMaterial,
  deleteMaterial,
  getMaterials,
  updateMaterial,
} from "../services/materials";

const EMPTY_FORM: MaterialCreate = {
  name: "",
  material_type: "",
  alloy: "",
  thickness_mm: 0,
  sheet_width_mm: 0,
  sheet_height_mm: 0,
  sheet_cost_ars: 0,
};

const MaterialsPage = () => {
  const [materials, setMaterials] = useState<Material[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<MaterialCreate>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const [deleteId, setDeleteId] = useState<number | null>(null);

  const filtered = useMemo(() =>
    materials.filter(m => m.name.toLowerCase().includes(search.toLowerCase())),
    [materials, search]
  );

  const { paginatedItems, page, rowsPerPage, totalCount, handlePageChange, handleRowsPerPageChange } =
    usePaginatedList(filtered, 20);

  useEffect(() => { load(); }, []);

  async function load() {
    try {
      setLoading(true);
      setMaterials(await getMaterials());
    } catch {
      setError("No se pudieron cargar los materiales.");
    } finally {
      setLoading(false);
    }
  }

  function openCreate() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }

  function openEdit(m: Material) {
    setEditingId(m.id);
    setForm({
      name: m.name,
      material_type: m.material_type ?? "",
      alloy: m.alloy ?? "",
      thickness_mm: m.thickness_mm,
      sheet_width_mm: m.sheet_width_mm,
      sheet_height_mm: m.sheet_height_mm,
      sheet_cost_ars: m.sheet_cost_ars,
    });
    setDialogOpen(true);
  }

  const TEXT_FIELDS = new Set<keyof MaterialCreate>(["name", "material_type", "alloy"]);

  function handleField(field: keyof MaterialCreate, value: string) {
    setForm((prev) => ({
      ...prev,
      [field]: TEXT_FIELDS.has(field) ? value : parseFloat(value) || 0,
    }));
  }

  async function handleSave() {
    if (!form.name.trim() || !form.material_type.trim()) return;
    setSaving(true);
    try {
      if (editingId !== null) {
        await updateMaterial(editingId, form);
        setToast("Material actualizado.");
      } else {
        await createMaterial(form);
        setToast("Material creado.");
      }
      setDialogOpen(false);
      await load();
    } catch {
      setToast("Error al guardar el material.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (deleteId === null) return;
    try {
      await deleteMaterial(deleteId);
      setToast("Material eliminado.");
      setDeleteId(null);
      await load();
    } catch {
      setToast("Error al eliminar el material.");
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
            <Box sx={{ width: 3, height: 26, bgcolor: "primary.main", borderRadius: 1, boxShadow: "0 0 10px rgba(255,107,0,0.6)", flexShrink: 0 }} />
            <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 700, fontSize: "1.8rem", letterSpacing: "0.05em", textTransform: "uppercase", lineHeight: 1 }}>
              Materiales
            </Typography>
          </Box>
          <Typography sx={{ color: "text.secondary", fontSize: "0.82rem", ml: "19px" }}>
            Configurá materiales, espesores y costos de chapa
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<Add />} onClick={openCreate}>
          Crear material
        </Button>
      </Box>

      {/* Búsqueda */}
      {materials.length > 0 && (
        <TextField
          size="small"
          placeholder="Buscar por nombre..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <Search fontSize="small" />
              </InputAdornment>
            ),
          }}
          sx={{ mb: 2 }}
        />
      )}

      {filtered.length === 0 && materials.length === 0 ? (
        <Typography color="text.secondary">No hay materiales cargados.</Typography>
      ) : filtered.length === 0 ? (
        <Typography color="text.secondary">No hay materiales que coincidan con la búsqueda.</Typography>
      ) : (
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Nombre</TableCell>
                <TableCell>Tipo / calidad</TableCell>
                <TableCell align="right">Espesor (mm)</TableCell>
                <TableCell align="right">Chapa (mm)</TableCell>
                <TableCell align="right">Costo chapa (ARS)</TableCell>
                <TableCell align="center">Acciones</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {paginatedItems.map((m) => (
                <TableRow key={m.id}>
                  <TableCell>{m.name}</TableCell>
                  <TableCell sx={{ color: "text.secondary" }}>
                    {m.material_type ?? "—"}{m.alloy ? ` · ${m.alloy}` : ""}
                  </TableCell>
                  <TableCell align="right"><span className="mono">{m.thickness_mm}</span></TableCell>
                  <TableCell align="right">
                    <span className="mono">{m.sheet_width_mm} × {m.sheet_height_mm}</span>
                  </TableCell>
                  <TableCell align="right">
                    <span className="mono">
                      {m.sheet_cost_ars.toLocaleString("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 })}
                    </span>
                  </TableCell>
                  <TableCell align="center">
                    <IconButton size="small" onClick={() => openEdit(m)}>
                      <Edit fontSize="small" />
                    </IconButton>
                    <IconButton size="small" color="error" onClick={() => setDeleteId(m.id)}>
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
        <DialogTitle>{editingId ? "Editar material" : "Crear material"}</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <TextField label="Nombre" value={form.name} onChange={(e) => handleField("name", e.target.value)} fullWidth required />
          <TextField
            label="Tipo de material"
            value={form.material_type}
            onChange={(e) => handleField("material_type", e.target.value)}
            fullWidth required
            placeholder="Ej: Acero al carbono, Acero inoxidable, Aluminio"
          />
          <TextField
            label="Calidad / aleación (opcional)"
            value={form.alloy}
            onChange={(e) => handleField("alloy", e.target.value)}
            fullWidth
            placeholder="Ej: SAE 1010, AISI 304"
          />
          <TextField label="Espesor (mm)" type="number" value={form.thickness_mm} onChange={(e) => handleField("thickness_mm", e.target.value)} fullWidth required />
          <TextField label="Ancho de chapa (mm)" type="number" value={form.sheet_width_mm} onChange={(e) => handleField("sheet_width_mm", e.target.value)} fullWidth required />
          <TextField label="Alto de chapa (mm)" type="number" value={form.sheet_height_mm} onChange={(e) => handleField("sheet_height_mm", e.target.value)} fullWidth required />
          <TextField label="Costo de chapa (ARS)" type="number" value={form.sheet_cost_ars} onChange={(e) => handleField("sheet_cost_ars", e.target.value)} fullWidth required />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)} disabled={saving}>Cancelar</Button>
          <Button variant="contained" onClick={handleSave} disabled={saving || !form.name.trim() || !form.material_type.trim()}>
            {saving ? "Guardando..." : "Guardar"}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Confirmación de eliminación */}
      <Dialog open={deleteId !== null} onClose={() => setDeleteId(null)}>
        <DialogTitle>Eliminar material</DialogTitle>
        <DialogContent>
          <Typography>¿Confirmás que querés eliminar este material?</Typography>
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

export default MaterialsPage;
