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
  type Client,
  type ClientCreate,
  createClient,
  deleteClient,
  getClients,
  updateClient,
} from "../services/clients";

const EMPTY_FORM: ClientCreate = {
  name: "",
  cuit_cuil: "",
  phone: "",
  email: "",
  address: "",
  notes: "",
};

const ClientsPage = () => {
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<ClientCreate>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const [deleteId, setDeleteId] = useState<number | null>(null);

  const filtered = useMemo(() =>
    clients.filter(c =>
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      (c.cuit_cuil && c.cuit_cuil.toLowerCase().includes(search.toLowerCase()))
    ),
    [clients, search]
  );

  const { paginatedItems, page, rowsPerPage, totalCount, handlePageChange, handleRowsPerPageChange } =
    usePaginatedList(filtered, 20);

  useEffect(() => { load(); }, []);

  async function load() {
    try {
      setLoading(true);
      setClients(await getClients());
    } catch {
      setError("No se pudieron cargar los clientes.");
    } finally {
      setLoading(false);
    }
  }

  function openCreate() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }

  function openEdit(c: Client) {
    setEditingId(c.id);
    setForm({
      name: c.name,
      cuit_cuil: c.cuit_cuil ?? "",
      phone: c.phone ?? "",
      email: c.email ?? "",
      address: c.address ?? "",
      notes: c.notes ?? "",
    });
    setDialogOpen(true);
  }

  function handleField(field: keyof ClientCreate, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSave() {
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      const payload: ClientCreate = {
        name: form.name,
        ...(form.cuit_cuil?.trim() && { cuit_cuil: form.cuit_cuil }),
        ...(form.phone?.trim() && { phone: form.phone }),
        ...(form.email?.trim() && { email: form.email }),
        ...(form.address?.trim() && { address: form.address }),
        ...(form.notes?.trim() && { notes: form.notes }),
      };
      if (editingId !== null) {
        await updateClient(editingId, payload);
        setToast("Cliente actualizado.");
      } else {
        await createClient(payload);
        setToast("Cliente creado.");
      }
      setDialogOpen(false);
      await load();
    } catch {
      setToast("Error al guardar el cliente.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (deleteId === null) return;
    try {
      await deleteClient(deleteId);
      setToast("Cliente eliminado.");
      setDeleteId(null);
      await load();
    } catch {
      setToast("Error al eliminar el cliente.");
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
            <Box sx={{ width: 3, height: 26, bgcolor: "#22C55E", borderRadius: 1, boxShadow: "0 0 10px rgba(34,197,94,0.5)", flexShrink: 0 }} />
            <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 700, fontSize: "1.8rem", letterSpacing: "0.05em", textTransform: "uppercase", lineHeight: 1 }}>
              Clientes
            </Typography>
          </Box>
          <Typography sx={{ color: "text.secondary", fontSize: "0.82rem", ml: "19px" }}>
            Administrá tu cartera de clientes
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<Add />} onClick={openCreate}>
          Nuevo cliente
        </Button>
      </Box>

      {/* Búsqueda */}
      {clients.length > 0 && (
        <TextField
          size="small"
          placeholder="Buscar por nombre o CUIT..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <Search fontSize="small" />
              </InputAdornment>
            ),
          }}
          sx={{ mb: 2, minWidth: 280 }}
        />
      )}

      {filtered.length === 0 && clients.length === 0 ? (
        <Typography color="text.secondary">No hay clientes cargados.</Typography>
      ) : filtered.length === 0 ? (
        <Typography color="text.secondary">No hay clientes que coincidan con la búsqueda.</Typography>
      ) : (
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Nombre</TableCell>
                <TableCell>CUIT/CUIL</TableCell>
                <TableCell>Teléfono</TableCell>
                <TableCell>Email</TableCell>
                <TableCell>Dirección</TableCell>
                <TableCell align="center">Acciones</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {paginatedItems.map((c) => (
                <TableRow key={c.id}>
                  <TableCell sx={{ fontWeight: 500 }}>{c.name}</TableCell>
                  <TableCell><span className="mono">{c.cuit_cuil ?? "—"}</span></TableCell>
                  <TableCell>{c.phone ?? "—"}</TableCell>
                  <TableCell sx={{ color: "text.secondary" }}>{c.email ?? "—"}</TableCell>
                  <TableCell sx={{ color: "text.secondary" }}>{c.address ?? "—"}</TableCell>
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
        <DialogTitle>{editingId ? "Editar cliente" : "Nuevo cliente"}</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <TextField label="Nombre" value={form.name} onChange={(e) => handleField("name", e.target.value)} fullWidth required />
          <TextField label="CUIT / CUIL" value={form.cuit_cuil} onChange={(e) => handleField("cuit_cuil", e.target.value)} fullWidth />
          <TextField label="Teléfono" value={form.phone} onChange={(e) => handleField("phone", e.target.value)} fullWidth />
          <TextField label="Email" type="email" value={form.email} onChange={(e) => handleField("email", e.target.value)} fullWidth />
          <TextField label="Dirección" value={form.address} onChange={(e) => handleField("address", e.target.value)} fullWidth />
          <TextField label="Notas" value={form.notes} onChange={(e) => handleField("notes", e.target.value)} fullWidth multiline rows={2} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)} disabled={saving}>Cancelar</Button>
          <Button variant="contained" onClick={handleSave} disabled={saving || !form.name.trim()}>
            {saving ? "Guardando..." : "Guardar"}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Confirmación eliminación */}
      <Dialog open={deleteId !== null} onClose={() => setDeleteId(null)}>
        <DialogTitle>Eliminar cliente</DialogTitle>
        <DialogContent>
          <Typography>¿Confirmás que querés eliminar este cliente?</Typography>
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

export default ClientsPage;
