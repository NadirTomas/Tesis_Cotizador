import { Add, Delete, Edit, UploadFile, Search } from "@mui/icons-material";
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
  TablePagination,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { useMemo, useEffect, useRef, useState } from "react";
import { usePaginatedList } from "../hooks/usePaginatedList";
import AuthedImage from "../components/AuthedImage";

import { getMaterials, type Material } from "../services/materials";
import {
  createPiece,
  deletePiece,
  getPieces,
  getPiecePreviewUrl,
  updatePiece,
  uploadDxf,
  type Piece,
  type PieceCreate,
} from "../services/pieces";

const PiecesPage = () => {
  const [pieces, setPieces] = useState<Piece[]>([]);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  // Modal importar DXF
  const [importOpen, setImportOpen] = useState(false);
  const [dxfFile, setDxfFile] = useState<File | null>(null);
  const [importName, setImportName] = useState("");
  const [importMaterialId, setImportMaterialId] = useState<number | "">("");
  const [importing, setImporting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Modal nueva pieza manual / editar
  const [manualOpen, setManualOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [manualName, setManualName] = useState("");
  const [manualDescription, setManualDescription] = useState("");
  const [manualMaterialId, setManualMaterialId] = useState<number | "">("");
  const [saving, setSaving] = useState(false);

  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [search, setSearch] = useState("");

  const filtered = useMemo(() =>
    pieces.filter(p => p.name.toLowerCase().includes(search.toLowerCase())),
    [pieces, search]
  );

  const { paginatedItems, page, rowsPerPage, totalCount, handlePageChange, handleRowsPerPageChange } =
    usePaginatedList(filtered, 20);

  useEffect(() => { loadAll(); }, []);

  async function loadAll() {
    try {
      setLoading(true);
      const [piecesData, materialsData] = await Promise.all([getPieces(), getMaterials()]);
      setPieces(piecesData);
      setMaterials(materialsData);
    } catch {
      setError("No se pudieron cargar los datos.");
    } finally {
      setLoading(false);
    }
  }

  function materialName(id: number | null): string {
    if (!id) return "—";
    return materials.find((m) => m.id === id)?.name ?? "—";
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    if (!file) return;
    setDxfFile(file);
    setImportName(file.name.replace(/\.dxf$/i, ""));
  }

  function openImport() {
    setDxfFile(null);
    setImportName("");
    setImportMaterialId("");
    setImportOpen(true);
  }

  async function handleImport() {
    if (!dxfFile || !importName.trim()) return;
    setImporting(true);
    try {
      const payload: PieceCreate = {
        name: importName.trim(),
        ...(importMaterialId !== "" && { material_id: importMaterialId as number }),
      };
      const created = await createPiece(payload);
      await uploadDxf(created.id, dxfFile);
      setToast("Pieza importada y DXF analizado.");
      setImportOpen(false);
      await loadAll();
    } catch {
      setToast("Error al importar la pieza.");
    } finally {
      setImporting(false);
    }
  }

  function openCreate() {
    setEditingId(null);
    setManualName("");
    setManualDescription("");
    setManualMaterialId("");
    setManualOpen(true);
  }

  function openEdit(p: Piece) {
    setEditingId(p.id);
    setManualName(p.name);
    setManualDescription(p.description ?? "");
    setManualMaterialId(p.material_id ?? "");
    setManualOpen(true);
  }

  async function handleSaveManual() {
    if (!manualName.trim()) return;
    setSaving(true);
    try {
      const payload = {
        name: manualName.trim(),
        ...(manualDescription.trim() && { description: manualDescription.trim() }),
        ...(manualMaterialId !== "" && { material_id: manualMaterialId as number }),
      };
      if (editingId !== null) {
        await updatePiece(editingId, payload);
        setToast("Pieza actualizada.");
      } else {
        await createPiece(payload);
        setToast("Pieza creada.");
      }
      setManualOpen(false);
      await loadAll();
    } catch {
      setToast("Error al guardar la pieza.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (deleteId === null) return;
    try {
      await deletePiece(deleteId);
      setToast("Pieza eliminada.");
      setDeleteId(null);
      await loadAll();
    } catch {
      setToast("Error al eliminar la pieza.");
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
      <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={4}>
        <Box>
          <Box display="flex" alignItems="center" gap={1.5} mb={0.75}>
            <Box sx={{ width: 3, height: 26, bgcolor: "#3D8BFF", borderRadius: 1, boxShadow: "0 0 10px rgba(61,139,255,0.5)", flexShrink: 0 }} />
            <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 700, fontSize: "1.8rem", letterSpacing: "0.05em", textTransform: "uppercase", lineHeight: 1 }}>
              Piezas
            </Typography>
          </Box>
          <Typography sx={{ color: "text.secondary", fontSize: "0.82rem", ml: "19px" }}>
            Cargá archivos DXF y administrá piezas
          </Typography>
        </Box>
        <Box display="flex" gap={1}>
          <Button variant="outlined" startIcon={<UploadFile />} onClick={openImport}>
            Importar DXF
          </Button>
          <Button variant="contained" startIcon={<Add />} onClick={openCreate}>
            Nueva pieza
          </Button>
        </Box>
      </Box>

      {/* Búsqueda */}
      {pieces.length > 0 && (
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

      {filtered.length === 0 && pieces.length === 0 ? (
        <Typography color="text.secondary">No hay piezas cargadas.</Typography>
      ) : filtered.length === 0 ? (
        <Typography color="text.secondary">No hay piezas que coincidan con la búsqueda.</Typography>
      ) : (
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ width: 56 }}>Preview</TableCell>
                <TableCell>Nombre</TableCell>
                <TableCell>Material</TableCell>
                <TableCell align="right">Largo corte (mm)</TableCell>
                <TableCell align="right">Área (mm²)</TableCell>
                <TableCell align="center">DXF</TableCell>
                <TableCell align="center">Acciones</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {paginatedItems.map((p) => (
                <TableRow key={p.id}>
                  <TableCell sx={{ py: 0.5 }}>
                    {p.has_preview ? (
                      <AuthedImage
                        src={getPiecePreviewUrl(p.id)}
                        alt={p.name}
                        sx={{
                          width: 44,
                          height: 44,
                          objectFit: "contain",
                          borderRadius: 1,
                          bgcolor: "white",
                          border: "1px solid",
                          borderColor: "divider",
                          display: "block",
                        }}
                        fallback={
                          <Box sx={{ width: 44, height: 44, borderRadius: 1, bgcolor: "#1A1C24", border: "1px solid", borderColor: "divider" }} />
                        }
                      />
                    ) : (
                      <Box sx={{ width: 44, height: 44, borderRadius: 1, bgcolor: "#1A1C24", border: "1px solid", borderColor: "divider", display: "flex", alignItems: "center", justifyContent: "center" }}>
                        <Typography sx={{ fontSize: "0.6rem", color: "text.secondary" }}>—</Typography>
                      </Box>
                    )}
                  </TableCell>
                  <TableCell sx={{ fontWeight: 500 }}>{p.name}</TableCell>
                  <TableCell>{materialName(p.material_id)}</TableCell>
                  <TableCell align="right">
                    <span className="mono">
                      {p.length_cut_mm != null ? p.length_cut_mm.toFixed(1) : "—"}
                    </span>
                  </TableCell>
                  <TableCell align="right">
                    <span className="mono">
                      {p.area_mm2 != null ? p.area_mm2.toFixed(1) : "—"}
                    </span>
                  </TableCell>
                  <TableCell align="center">
                    {p.has_dxf ? (
                      <Chip label="Cargado" size="small" color="success" variant="outlined" />
                    ) : (
                      <Chip label="Sin DXF" size="small" variant="outlined" />
                    )}
                  </TableCell>
                  <TableCell align="center">
                    <IconButton size="small" onClick={() => openEdit(p)}>
                      <Edit fontSize="small" />
                    </IconButton>
                    <IconButton size="small" color="error" onClick={() => setDeleteId(p.id)}>
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

      {/* Modal importar DXF */}
      <Dialog open={importOpen} onClose={() => setImportOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>Importar pieza desde DXF</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <Box>
            <Button variant="outlined" onClick={() => fileInputRef.current?.click()} fullWidth
              sx={{ justifyContent: "flex-start", color: dxfFile ? "text.primary" : "text.secondary" }}>
              {dxfFile ? dxfFile.name : "Seleccionar archivo .dxf"}
            </Button>
            <input ref={fileInputRef} type="file" accept=".dxf" hidden onChange={handleFileChange} />
          </Box>
          <TextField
            label="Nombre de la pieza"
            value={importName}
            onChange={(e) => setImportName(e.target.value)}
            fullWidth required disabled={!dxfFile}
          />
          <FormControl fullWidth>
            <InputLabel>Material (opcional)</InputLabel>
            <Select label="Material (opcional)" value={importMaterialId} onChange={(e) => setImportMaterialId(e.target.value as number | "")}>
              <MenuItem value="">Sin material</MenuItem>
              {materials.map((m) => (
                <MenuItem key={m.id} value={m.id}>{m.name} — {m.thickness_mm}mm</MenuItem>
              ))}
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setImportOpen(false)} disabled={importing}>Cancelar</Button>
          <Button variant="contained" onClick={handleImport} disabled={importing || !dxfFile || !importName.trim()}>
            {importing ? "Importando..." : "Importar"}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Modal nueva pieza / editar */}
      <Dialog open={manualOpen} onClose={() => setManualOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>{editingId ? "Editar pieza" : "Nueva pieza"}</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <TextField label="Nombre" value={manualName} onChange={(e) => setManualName(e.target.value)} fullWidth required />
          <TextField label="Descripción" value={manualDescription} onChange={(e) => setManualDescription(e.target.value)} fullWidth multiline rows={2} />
          <FormControl fullWidth>
            <InputLabel>Material (opcional)</InputLabel>
            <Select label="Material (opcional)" value={manualMaterialId} onChange={(e) => setManualMaterialId(e.target.value as number | "")}>
              <MenuItem value="">Sin material</MenuItem>
              {materials.map((m) => (
                <MenuItem key={m.id} value={m.id}>{m.name} — {m.thickness_mm}mm</MenuItem>
              ))}
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setManualOpen(false)} disabled={saving}>Cancelar</Button>
          <Button variant="contained" onClick={handleSaveManual} disabled={saving || !manualName.trim()}>
            {saving ? "Guardando..." : "Guardar"}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Confirmación eliminación */}
      <Dialog open={deleteId !== null} onClose={() => setDeleteId(null)}>
        <DialogTitle>Eliminar pieza</DialogTitle>
        <DialogContent>
          <Typography>¿Confirmás que querés eliminar esta pieza?</Typography>
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

export default PiecesPage;
