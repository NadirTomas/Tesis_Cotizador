import { FilterList, PictureAsPdf, Visibility } from "@mui/icons-material";
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
  Snackbar,
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
import { openAuthedResource } from "../services/authedResource";
import {
  getDeliveryNotePdfUrl,
  getDeliveryNotes,
  type DeliveryNoteStatus,
  type DeliveryNoteSummary,
} from "../services/deliveryNotes";
import { formatDate, NOTE_STATUS } from "../utils/deliveryNotes";

const ALL_STATUSES: DeliveryNoteStatus[] = ["DRAFT", "ISSUED", "VOIDED"];

const DeliveryNotesPage = () => {
  const navigate = useNavigate();
  const [notes, setNotes] = useState<DeliveryNoteSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const [filterStatus, setFilterStatus] = useState<string>("");
  const [filterSearch, setFilterSearch] = useState("");

  useEffect(() => {
    getDeliveryNotes()
      .then(setNotes)
      .catch(() => setError("No se pudieron cargar los remitos."))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    const term = filterSearch.trim().toLowerCase();
    return notes.filter((n) => {
      if (filterStatus && n.status !== filterStatus) return false;
      if (term) {
        const haystack = `${n.number ?? ""} ${n.client_name} ${n.quotation_number}`.toLowerCase();
        if (!haystack.includes(term)) return false;
      }
      return true;
    });
  }, [notes, filterStatus, filterSearch]);

  const hasFilters = filterStatus !== "" || filterSearch.trim() !== "";

  const { paginatedItems, page, rowsPerPage, totalCount, handlePageChange, handleRowsPerPageChange } =
    usePaginatedList(filtered, 20);

  async function handlePdf(id: number) {
    try {
      await openAuthedResource(getDeliveryNotePdfUrl(id));
    } catch {
      setToast("No se pudo abrir el PDF del remito.");
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
      <Box mb={4}>
        <Box display="flex" alignItems="center" gap={1.5} mb={0.75}>
          <Box sx={{ width: 3, height: 26, bgcolor: "primary.main", borderRadius: 1, boxShadow: "0 0 10px rgba(255,107,0,0.6)", flexShrink: 0 }} />
          <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 700, fontSize: "1.8rem", letterSpacing: "0.05em", textTransform: "uppercase", lineHeight: 1 }}>
            Remitos
          </Typography>
        </Box>
        <Typography sx={{ color: "text.secondary", fontSize: "0.82rem", ml: "19px" }}>
          Entregas totales y parciales de cotizaciones aceptadas. Para generar uno, abrí la cotización y usá “Generar remito”.
        </Typography>
      </Box>

      <Box display="flex" gap={1.5} flexWrap="wrap" alignItems="center" mb={3}>
        <FilterList sx={{ color: "text.secondary", fontSize: 20 }} />
        <TextField
          label="Buscar número, cliente o cotización"
          size="small"
          value={filterSearch}
          onChange={(e) => setFilterSearch(e.target.value)}
          sx={{ width: 280 }}
        />
        <FormControl size="small" sx={{ minWidth: 150 }}>
          <InputLabel>Estado</InputLabel>
          <Select label="Estado" value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}>
            <MenuItem value="">Todos</MenuItem>
            {ALL_STATUSES.map((s) => (
              <MenuItem key={s} value={s}>{NOTE_STATUS[s].label}</MenuItem>
            ))}
          </Select>
        </FormControl>
        {hasFilters && (
          <Button size="small" onClick={() => { setFilterStatus(""); setFilterSearch(""); }}>Limpiar filtros</Button>
        )}
        <Typography sx={{ ml: "auto", fontSize: "0.8rem", color: "text.secondary" }}>
          {filtered.length} resultado{filtered.length !== 1 ? "s" : ""}
        </Typography>
      </Box>

      {notes.length === 0 ? (
        <Typography color="text.secondary">Todavía no hay remitos. Se generan desde una cotización aceptada.</Typography>
      ) : filtered.length === 0 ? (
        <Typography color="text.secondary">Sin resultados para los filtros aplicados.</Typography>
      ) : (
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Número</TableCell>
                <TableCell>Fecha</TableCell>
                <TableCell>Cliente</TableCell>
                <TableCell>Cotización</TableCell>
                <TableCell align="right">Unidades</TableCell>
                <TableCell>Estado</TableCell>
                <TableCell align="center">Acciones</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {paginatedItems.map((n) => (
                <TableRow key={n.id} hover>
                  <TableCell>
                    {n.number ? (
                      <Box component="span" className="mono" sx={{ color: "text.primary", fontWeight: 500 }}>{n.number}</Box>
                    ) : (
                      <Typography component="span" sx={{ color: "text.secondary", fontSize: "0.85rem" }}>Sin número</Typography>
                    )}
                  </TableCell>
                  <TableCell sx={{ color: "text.secondary" }}>{formatDate(n.issue_date ?? n.created_at)}</TableCell>
                  <TableCell sx={{ fontWeight: 500 }}>{n.client_name}</TableCell>
                  <TableCell>
                    <Box
                      component="span"
                      className="mono"
                      sx={{ color: "text.primary", cursor: "pointer", textDecoration: "underline" }}
                      onClick={() => navigate(`/quotations/${n.quotation_id}`)}
                    >
                      {n.quotation_number}
                    </Box>
                  </TableCell>
                  <TableCell align="right"><span className="mono">{n.total_units}</span></TableCell>
                  <TableCell>
                    <Chip label={NOTE_STATUS[n.status].label} color={NOTE_STATUS[n.status].color} size="small" />
                  </TableCell>
                  <TableCell align="center">
                    <Tooltip title="Ver detalle">
                      <IconButton size="small" aria-label="Ver detalle" onClick={() => navigate(`/delivery-notes/${n.id}`)}>
                        <Visibility fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Descargar PDF">
                      <IconButton size="small" aria-label="Descargar PDF" onClick={() => handlePdf(n.id)}>
                        <PictureAsPdf fontSize="small" />
                      </IconButton>
                    </Tooltip>
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

      <Snackbar open={!!toast} autoHideDuration={3000} onClose={() => setToast(null)} message={toast} />
    </Box>
  );
};

export default DeliveryNotesPage;
