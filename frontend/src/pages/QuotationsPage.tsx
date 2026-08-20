import { Add, FilterList, PictureAsPdf, Visibility } from "@mui/icons-material";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { usePaginatedList } from "../hooks/usePaginatedList";

import { getClients, type Client } from "../services/clients";
import { getQuotationPdfUrl, getQuotations, type Quotation } from "../services/quotations";
import { openAuthedResource } from "../services/authedResource";

const STATUS_LABELS: Record<string, { label: string; color: "default" | "warning" | "success" | "error" | "info" }> = {
  draft:     { label: "Borrador",  color: "warning" },
  sent:      { label: "Enviado",   color: "info" },
  accepted:  { label: "Aceptado", color: "success" },
  cancelled: { label: "Cancelado", color: "error" },
};

const ALL_STATUSES = ["draft", "sent", "accepted", "cancelled"];

const QuotationsPage = () => {
  const navigate = useNavigate();
  const [quotations, setQuotations] = useState<Quotation[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filtros
  const [filterStatus, setFilterStatus] = useState<string>("");
  const [filterClientId, setFilterClientId] = useState<number | "">("");
  const [filterSearch, setFilterSearch] = useState("");

  useEffect(() => { load(); }, []);

  async function load() {
    try {
      setLoading(true);
      const [q, c] = await Promise.all([getQuotations(), getClients()]);
      setQuotations(q);
      setClients(c);
    } catch {
      setError("No se pudieron cargar las cotizaciones.");
    } finally {
      setLoading(false);
    }
  }

  function clientName(id: number): string {
    return clients.find((c) => c.id === id)?.name ?? `Cliente #${id}`;
  }

  function formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString("es-AR");
  }

  function formatARS(value: number): string {
    return value.toLocaleString("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 });
  }

  const filtered = useMemo(() => {
    return quotations.filter((q) => {
      if (filterStatus && q.status !== filterStatus) return false;
      if (filterClientId !== "" && q.client_id !== filterClientId) return false;
      if (filterSearch.trim() && !q.number.toLowerCase().includes(filterSearch.toLowerCase())) return false;
      return true;
    });
  }, [quotations, filterStatus, filterClientId, filterSearch]);

  const hasFilters = filterStatus || filterClientId !== "" || filterSearch.trim();

  function clearFilters() {
    setFilterStatus("");
    setFilterClientId("");
    setFilterSearch("");
  }

  const { paginatedItems, page, rowsPerPage, totalCount, handlePageChange, handleRowsPerPageChange } =
    usePaginatedList(filtered, 20);

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
            <Box sx={{ width: 3, height: 26, bgcolor: "primary.main", borderRadius: 1, boxShadow: "0 0 10px rgba(255,107,0,0.6)", flexShrink: 0 }} />
            <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 700, fontSize: "1.8rem", letterSpacing: "0.05em", textTransform: "uppercase", lineHeight: 1 }}>
              Cotizaciones
            </Typography>
          </Box>
          <Typography sx={{ color: "text.secondary", fontSize: "0.82rem", ml: "19px" }}>
            Gestioná y seguí tus presupuestos
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<Add />} onClick={() => navigate("/quotes/new-from-cad")}>
          Nueva cotización
        </Button>
      </Box>

      {/* Filtros */}
      <Box display="flex" gap={1.5} flexWrap="wrap" alignItems="center" mb={3}>
        <FilterList sx={{ color: "text.secondary", fontSize: 20 }} />
        <TextField
          label="Buscar número"
          size="small"
          value={filterSearch}
          onChange={(e) => setFilterSearch(e.target.value)}
          sx={{ width: 180 }}
        />
        <FormControl size="small" sx={{ minWidth: 140 }}>
          <InputLabel>Estado</InputLabel>
          <Select label="Estado" value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}>
            <MenuItem value="">Todos</MenuItem>
            {ALL_STATUSES.map((s) => (
              <MenuItem key={s} value={s}>{STATUS_LABELS[s]?.label ?? s}</MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel>Cliente</InputLabel>
          <Select label="Cliente" value={filterClientId} onChange={(e) => setFilterClientId(e.target.value as number | "")}>
            <MenuItem value="">Todos</MenuItem>
            {clients.map((c) => <MenuItem key={c.id} value={c.id}>{c.name}</MenuItem>)}
          </Select>
        </FormControl>
        {hasFilters && (
          <Button size="small" onClick={clearFilters} sx={{ ml: 0.5 }}>Limpiar filtros</Button>
        )}
        <Typography sx={{ ml: "auto", fontSize: "0.8rem", color: "text.secondary" }}>
          {filtered.length} resultado{filtered.length !== 1 ? "s" : ""}
        </Typography>
      </Box>

      {quotations.length === 0 ? (
        <Typography color="text.secondary">No hay cotizaciones registradas.</Typography>
      ) : filtered.length === 0 ? (
        <Typography color="text.secondary">Sin resultados para los filtros aplicados.</Typography>
      ) : (
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Número</TableCell>
                <TableCell>Cliente</TableCell>
                <TableCell>Fecha</TableCell>
                <TableCell>Estado</TableCell>
                <TableCell align="right">Total ARS</TableCell>
                <TableCell align="center">Acciones</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {paginatedItems.map((q) => {
                const status = STATUS_LABELS[q.status] ?? { label: q.status, color: "default" as const };
                return (
                  <TableRow key={q.id}>
                    <TableCell>
                      <span className="mono" style={{ color: "#E8E9EB", fontWeight: 500 }}>
                        {q.number}
                      </span>
                    </TableCell>
                    <TableCell sx={{ fontWeight: 500 }}>{clientName(q.client_id)}</TableCell>
                    <TableCell sx={{ color: "text.secondary" }}>{formatDate(q.issue_date)}</TableCell>
                    <TableCell>
                      <Chip label={status.label} color={status.color} size="small" />
                    </TableCell>
                    <TableCell align="right">
                      <span className="mono">{formatARS(q.total_ars)}</span>
                    </TableCell>
                    <TableCell align="center">
                      <Tooltip title="Ver detalle">
                        <IconButton size="small" onClick={() => navigate(`/quotations/${q.id}`)}>
                          <Visibility fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Descargar PDF">
                        <IconButton size="small" onClick={() => openAuthedResource(getQuotationPdfUrl(q.id))}>
                          <PictureAsPdf fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                );
              })}
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
    </Box>
  );
};

export default QuotationsPage;
