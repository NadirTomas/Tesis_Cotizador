import { Add, Block, CheckCircle } from "@mui/icons-material";
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
import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import {
  createMember,
  getMembers,
  updateMember,
  type CompanyMember,
  type CompanyMemberCreate,
} from "../services/companies";

const EMPTY_FORM: CompanyMemberCreate = { email: "", password: "", role: "employee" };

const EmployeesPage = () => {
  const { companyId } = useAuth();
  const [members, setMembers] = useState<CompanyMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState<CompanyMemberCreate>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [deactivateTarget, setDeactivateTarget] = useState<CompanyMember | null>(null);

  useEffect(() => { load(); }, [companyId]);

  async function load() {
    if (!companyId) return;
    try {
      setLoading(true);
      setMembers(await getMembers(companyId));
    } catch {
      setError("No se pudieron cargar los empleados.");
    } finally {
      setLoading(false);
    }
  }

  function openCreate() {
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }

  async function handleSave() {
    if (!companyId || !form.email.trim() || !form.password.trim()) return;
    setSaving(true);
    try {
      await createMember(companyId, form);
      setToast("Empleado creado.");
      setDialogOpen(false);
      await load();
    } catch (err) {
      setToast(err instanceof Error ? err.message : "Error al crear el empleado.");
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleActive(m: CompanyMember) {
    if (!companyId) return;
    if (m.is_active) {
      setDeactivateTarget(m);
      return;
    }
    try {
      await updateMember(companyId, m.id, { is_active: true });
      setToast("Empleado reactivado.");
      await load();
    } catch (err) {
      setToast(err instanceof Error ? err.message : "Error al actualizar el empleado.");
    }
  }

  async function confirmDeactivate() {
    if (!companyId || !deactivateTarget) return;
    try {
      await updateMember(companyId, deactivateTarget.id, { is_active: false });
      setToast("Empleado desactivado.");
      setDeactivateTarget(null);
      await load();
    } catch (err) {
      setToast(err instanceof Error ? err.message : "Error al actualizar el empleado.");
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
      <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={4}>
        <Box>
          <Box display="flex" alignItems="center" gap={1.5} mb={0.75}>
            <Box sx={{ width: 3, height: 26, bgcolor: "#3D8BFF", borderRadius: 1, boxShadow: "0 0 10px rgba(61,139,255,0.5)", flexShrink: 0 }} />
            <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 700, fontSize: "1.8rem", letterSpacing: "0.05em", textTransform: "uppercase", lineHeight: 1 }}>
              Empleados
            </Typography>
          </Box>
          <Typography sx={{ color: "text.secondary", fontSize: "0.82rem", ml: "19px" }}>
            Administrá quién puede trabajar en esta empresa
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<Add />} onClick={openCreate}>
          Nuevo empleado
        </Button>
      </Box>

      {members.length === 0 ? (
        <Typography color="text.secondary">No hay empleados cargados todavía.</Typography>
      ) : (
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Email</TableCell>
                <TableCell>Rol</TableCell>
                <TableCell>Estado</TableCell>
                <TableCell align="center">Acciones</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {members.map((m) => (
                <TableRow key={m.id}>
                  <TableCell sx={{ fontWeight: 500 }}>{m.email}</TableCell>
                  <TableCell>
                    <Chip label={m.role === "owner" ? "OWNER" : "EMPLOYEE"} size="small" color={m.role === "owner" ? "primary" : "default"} variant="outlined" />
                  </TableCell>
                  <TableCell>
                    <Chip label={m.is_active ? "Activo" : "Inactivo"} size="small" color={m.is_active ? "success" : "default"} variant="outlined" />
                  </TableCell>
                  <TableCell align="center">
                    <IconButton size="small" color={m.is_active ? "error" : "success"} onClick={() => handleToggleActive(m)}>
                      {m.is_active ? <Block fontSize="small" /> : <CheckCircle fontSize="small" />}
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>Nuevo empleado</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <TextField
            label="Email"
            type="email"
            value={form.email}
            onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
            fullWidth
            required
          />
          <TextField
            label="Contraseña"
            type="password"
            value={form.password}
            onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
            fullWidth
            required
            helperText="Si el email ya tiene cuenta, se ignora y se vincula la existente."
          />
          <FormControl fullWidth>
            <InputLabel>Rol</InputLabel>
            <Select
              label="Rol"
              value={form.role}
              onChange={(e) => setForm((f) => ({ ...f, role: e.target.value as "owner" | "employee" }))}
            >
              <MenuItem value="employee">EMPLOYEE</MenuItem>
              <MenuItem value="owner">OWNER</MenuItem>
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)} disabled={saving}>Cancelar</Button>
          <Button variant="contained" onClick={handleSave} disabled={saving || !form.email.trim() || !form.password.trim()}>
            {saving ? "Guardando..." : "Guardar"}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={!!deactivateTarget} onClose={() => setDeactivateTarget(null)}>
        <DialogTitle>Desactivar empleado</DialogTitle>
        <DialogContent>
          <Typography>
            ¿Confirmás que querés desactivar a <b>{deactivateTarget?.email}</b>? Pierde acceso a la empresa hasta que lo reactives.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeactivateTarget(null)}>Cancelar</Button>
          <Button color="error" variant="contained" onClick={confirmDeactivate}>Desactivar</Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={!!toast} autoHideDuration={3000} onClose={() => setToast(null)} message={toast} />
    </Box>
  );
};

export default EmployeesPage;
