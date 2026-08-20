import { PictureAsPdf, WarningAmber } from "@mui/icons-material";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Divider,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Snackbar,
  Step,
  StepLabel,
  Stepper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getClients, type Client } from "../services/clients";
import { getMaterials, type Material } from "../services/materials";
import { getPieces, type Piece } from "../services/pieces";
import { openAuthedResource } from "../services/authedResource";
import {
  createQuotation,
  createQuotationItem,
  getQuotation,
  getQuotationItems,
  getQuotationPdfUrl,
  type Quotation,
  type QuotationItem,
} from "../services/quotations";

const STEPS = ["Datos de la cotización", "Agregar piezas", "Resumen"];

function today(): string {
  return new Date().toISOString().split("T")[0];
}

function formatARS(value: number): string {
  return value.toLocaleString("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 });
}

// ─── Paso 1 ───────────────────────────────────────────────────────────────────
function Step1({ clients, onCreated }: { clients: Client[]; onCreated: (q: Quotation) => void }) {
  const [clientId, setClientId] = useState<number | "">("");
  const [issueDate, setIssueDate] = useState(today());
  const [dueDate, setDueDate] = useState("");
  const [currency, setCurrency] = useState("ARS");
  const [exchangeRate, setExchangeRate] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleCreate() {
    if (!clientId || !issueDate) return;
    setSaving(true);
    setError(null);
    try {
      const q = await createQuotation({
        client_id: clientId as number,
        issue_date: issueDate + "T00:00:00",
        ...(dueDate && { due_date: dueDate + "T00:00:00" }),
        currency,
        ...(exchangeRate && { exchange_rate: parseFloat(exchangeRate) }),
        ...(notes.trim() && { notes: notes.trim() }),
      });
      onCreated(q);
    } catch {
      setError("Error al crear la cotización.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Box display="flex" flexDirection="column" gap={2} maxWidth={480}>
      {error && <Alert severity="error">{error}</Alert>}
      <FormControl fullWidth required>
        <InputLabel>Cliente</InputLabel>
        <Select label="Cliente" value={clientId} onChange={(e) => setClientId(e.target.value as number)}>
          {clients.map((c) => <MenuItem key={c.id} value={c.id}>{c.name}</MenuItem>)}
        </Select>
      </FormControl>
      <TextField label="Fecha de emisión" type="date" value={issueDate} onChange={(e) => setIssueDate(e.target.value)} fullWidth required InputLabelProps={{ shrink: true }} />
      <TextField label="Fecha de vencimiento (opcional)" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} fullWidth InputLabelProps={{ shrink: true }} />
      <FormControl fullWidth>
        <InputLabel>Moneda</InputLabel>
        <Select label="Moneda" value={currency} onChange={(e) => setCurrency(e.target.value)}>
          <MenuItem value="ARS">ARS</MenuItem>
          <MenuItem value="USD">USD</MenuItem>
        </Select>
      </FormControl>
      <TextField label="Tipo de cambio (opcional)" type="number" value={exchangeRate} onChange={(e) => setExchangeRate(e.target.value)} fullWidth placeholder="Ej: 1050" />
      <TextField label="Notas (opcional)" value={notes} onChange={(e) => setNotes(e.target.value)} fullWidth multiline rows={2} />
      <Box display="flex" justifyContent="flex-end" mt={1}>
        <Button variant="contained" onClick={handleCreate} disabled={saving || !clientId || !issueDate}>
          {saving ? "Creando..." : "Crear cotización →"}
        </Button>
      </Box>
    </Box>
  );
}

// ─── Paso 2 ───────────────────────────────────────────────────────────────────
interface Step2Props {
  quotation: Quotation;
  pieces: Piece[];
  materials: Material[];
  items: QuotationItem[];
  onItemAdded: () => void;
  onNext: () => void;
}

function Step2({ quotation, pieces, materials, items, onItemAdded, onNext }: Step2Props) {
  const [pieceId, setPieceId] = useState<number | "">("");
  const [materialId, setMaterialId] = useState<number | "">("");
  const [quantity, setQuantity] = useState(1);
  const [margin, setMargin] = useState(20);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function matName(id: number) { return materials.find((m) => m.id === id)?.name ?? `#${id}`; }
  function pcName(id: number) { return pieces.find((p) => p.id === id)?.name ?? `#${id}`; }

  function handlePieceChange(id: number | "") {
    setPieceId(id);
    if (id !== "") {
      const piece = pieces.find((p) => p.id === id);
      if (piece?.material_id) setMaterialId(piece.material_id);
    }
  }

  async function handleAdd() {
    if (pieceId === "" || materialId === "") return;
    setAdding(true);
    setError(null);
    try {
      await createQuotationItem({
        quotation_id: quotation.id,
        piece_id: pieceId as number,
        material_id: materialId as number,
        quantity,
        margin_percent: margin,
      });
      onItemAdded();
      setPieceId("");
      setMaterialId("");
      setQuantity(1);
      setMargin(20);
    } catch {
      setError("Error al agregar la pieza. Verificá que el material tenga configuración de máquina.");
    } finally {
      setAdding(false);
    }
  }

  const selectedPiece = pieces.find((p) => p.id === pieceId);

  return (
    <Box display="flex" flexDirection="column" gap={3}>
      {/* Formulario */}
      <Paper variant="outlined" sx={{ p: 2.5 }}>
        <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 600, fontSize: "0.8rem", letterSpacing: "0.1em", textTransform: "uppercase", color: "text.secondary", mb: 2 }}>
          Agregar pieza
        </Typography>

        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        <Box display="flex" flexWrap="wrap" gap={2} alignItems="flex-start">
          <FormControl sx={{ minWidth: 220 }} required>
            <InputLabel>Pieza</InputLabel>
            <Select label="Pieza" value={pieceId} onChange={(e) => handlePieceChange(e.target.value as number | "")}>
              {pieces.map((p) => (
                <MenuItem key={p.id} value={p.id}>
                  <Box display="flex" alignItems="center" gap={1}>
                    {p.name}
                    {p.length_cut_mm == null && (
                      <Tooltip title="Sin DXF — costos serán 0">
                        <WarningAmber fontSize="small" color="warning" />
                      </Tooltip>
                    )}
                  </Box>
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl sx={{ minWidth: 200 }} required>
            <InputLabel>Material</InputLabel>
            <Select label="Material" value={materialId} onChange={(e) => setMaterialId(e.target.value as number | "")}>
              {materials.map((m) => (
                <MenuItem key={m.id} value={m.id}>{m.name} — {m.thickness_mm}mm</MenuItem>
              ))}
            </Select>
          </FormControl>

          <TextField label="Cantidad" type="number" value={quantity} onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value) || 1))} sx={{ width: 100 }} inputProps={{ min: 1 }} />
          <TextField label="Margen %" type="number" value={margin} onChange={(e) => setMargin(parseFloat(e.target.value) || 0)} sx={{ width: 110 }} />

          <Button variant="contained" onClick={handleAdd} disabled={adding || pieceId === "" || materialId === ""} sx={{ alignSelf: "center", mt: 0.5 }}>
            {adding ? "Agregando..." : "Agregar"}
          </Button>
        </Box>

        {selectedPiece && selectedPiece.length_cut_mm == null && (
          <Alert severity="warning" sx={{ mt: 2 }}>
            Esta pieza no tiene DXF cargado. Los costos serán 0.
          </Alert>
        )}
      </Paper>

      {/* Tabla de ítems */}
      {items.length > 0 && (
        <Box>
          <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 600, fontSize: "0.78rem", letterSpacing: "0.1em", textTransform: "uppercase", color: "text.secondary", mb: 1 }}>
            Ítems ({items.length})
          </Typography>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Pieza</TableCell>
                  <TableCell>Material</TableCell>
                  <TableCell align="right">Cant.</TableCell>
                  <TableCell align="right">Margen</TableCell>
                  <TableCell align="right">Costo mat.</TableCell>
                  <TableCell align="right">Costo máq.</TableCell>
                  <TableCell align="right">Costo MO</TableCell>
                  <TableCell align="right">P. unitario</TableCell>
                  <TableCell align="right">Total</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell sx={{ fontWeight: 500 }}>{pcName(item.piece_id)}</TableCell>
                    <TableCell>{matName(item.material_id)}</TableCell>
                    <TableCell align="right"><span className="mono">{item.quantity}</span></TableCell>
                    <TableCell align="right"><span className="mono">{item.margin_percent}%</span></TableCell>
                    <TableCell align="right"><span className="mono">{formatARS(item.cost_material_ars)}</span></TableCell>
                    <TableCell align="right"><span className="mono">{formatARS(item.cost_machine_ars)}</span></TableCell>
                    <TableCell align="right"><span className="mono">{formatARS(item.cost_labor_ars)}</span></TableCell>
                    <TableCell align="right"><span className="mono">{formatARS(item.unit_price_ars)}</span></TableCell>
                    <TableCell align="right">
                      <span className="mono" style={{ fontWeight: 600, color: "#FF6B00" }}>
                        {formatARS(item.total_price_ars)}
                      </span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}

      <Box display="flex" justifyContent="flex-end">
        <Button variant="contained" onClick={onNext} disabled={items.length === 0}>
          Ver resumen →
        </Button>
      </Box>
    </Box>
  );
}

// ─── Paso 3 ───────────────────────────────────────────────────────────────────
interface Step3Props {
  quotation: Quotation;
  items: QuotationItem[];
  pieces: Piece[];
  materials: Material[];
  clients: Client[];
}

function Step3({ quotation, items, pieces, materials, clients }: Step3Props) {
  const navigate = useNavigate();

  function matName(id: number) { return materials.find((m) => m.id === id)?.name ?? `#${id}`; }
  function pcName(id: number) { return pieces.find((p) => p.id === id)?.name ?? `#${id}`; }
  function clName(id: number) { return clients.find((c) => c.id === id)?.name ?? `#${id}`; }

  return (
    <Box display="flex" flexDirection="column" gap={3}>
      {/* Info */}
      <Paper variant="outlined" sx={{ p: 2.5 }}>
        <Box display="flex" gap={4} flexWrap="wrap">
          <Box>
            <Typography sx={{ fontSize: "0.72rem", letterSpacing: "0.08em", textTransform: "uppercase", color: "text.secondary", mb: 0.25 }}>Cotización</Typography>
            <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 600, fontSize: "1.1rem" }}>{quotation.number}</Typography>
          </Box>
          <Box>
            <Typography sx={{ fontSize: "0.72rem", letterSpacing: "0.08em", textTransform: "uppercase", color: "text.secondary", mb: 0.25 }}>Cliente</Typography>
            <Typography sx={{ fontWeight: 500 }}>{clName(quotation.client_id)}</Typography>
          </Box>
          <Box>
            <Typography sx={{ fontSize: "0.72rem", letterSpacing: "0.08em", textTransform: "uppercase", color: "text.secondary", mb: 0.25 }}>Fecha</Typography>
            <Typography>{new Date(quotation.issue_date).toLocaleDateString("es-AR")}</Typography>
          </Box>
        </Box>
        {quotation.notes && (
          <Typography variant="body2" color="text.secondary" mt={1.5}>{quotation.notes}</Typography>
        )}
      </Paper>

      {/* Tabla */}
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Pieza</TableCell>
              <TableCell>Material</TableCell>
              <TableCell align="right">Cant.</TableCell>
              <TableCell align="right">P. unitario</TableCell>
              <TableCell align="right">Total</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {items.map((item) => (
              <TableRow key={item.id}>
                <TableCell sx={{ fontWeight: 500 }}>{pcName(item.piece_id)}</TableCell>
                <TableCell>{matName(item.material_id)}</TableCell>
                <TableCell align="right"><span className="mono">{item.quantity}</span></TableCell>
                <TableCell align="right"><span className="mono">{formatARS(item.unit_price_ars)}</span></TableCell>
                <TableCell align="right">
                  <span className="mono" style={{ fontWeight: 600 }}>{formatARS(item.total_price_ars)}</span>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Total */}
      <Box display="flex" justifyContent="flex-end">
        <Paper variant="outlined" sx={{ p: 2, minWidth: 240 }}>
          <Box display="flex" justifyContent="space-between" alignItems="center">
            <Typography sx={{ color: "text.secondary", fontSize: "0.875rem" }}>Total ARS</Typography>
            <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 700, fontSize: "1.5rem", color: "primary.main" }}>
              {formatARS(quotation.total_ars)}
            </Typography>
          </Box>
          {quotation.total_usd > 0 && (
            <Box display="flex" justifyContent="space-between" alignItems="center" mt={0.5}>
              <Typography sx={{ color: "text.secondary", fontSize: "0.8rem" }}>Total USD</Typography>
              <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 600, fontSize: "1rem", color: "text.secondary" }}>
                {quotation.total_usd.toLocaleString("es-AR", { style: "currency", currency: "USD" })}
              </Typography>
            </Box>
          )}
        </Paper>
      </Box>

      <Divider />

      <Box display="flex" justifyContent="space-between">
        <Button onClick={() => navigate("/quotations")}>← Ir a cotizaciones</Button>
        <Button variant="contained" startIcon={<PictureAsPdf />} onClick={() => openAuthedResource(getQuotationPdfUrl(quotation.id))}>
          Descargar PDF
        </Button>
      </Box>
    </Box>
  );
}

// ─── Página principal ──────────────────────────────────────────────────────────
const QuoteFromCadWizardPage = () => {
  const [activeStep, setActiveStep] = useState(0);
  const [quotation, setQuotation] = useState<Quotation | null>(null);
  const [items, setItems] = useState<QuotationItem[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [pieces, setPieces] = useState<Piece[]>([]);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [c, p, m] = await Promise.all([getClients(), getPieces(), getMaterials()]);
        setClients(c);
        setPieces(p);
        setMaterials(m);
      } catch {
        setToast("Error al cargar datos iniciales.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  async function handleQuotationCreated(q: Quotation) {
    setQuotation(q);
    setActiveStep(1);
  }

  async function refreshItems() {
    if (!quotation) return;
    try {
      const [updatedItems, updatedQuotation] = await Promise.all([
        getQuotationItems(quotation.id),
        getQuotation(quotation.id),
      ]);
      setItems(updatedItems);
      setQuotation(updatedQuotation);
    } catch {
      setToast("Error al actualizar los ítems.");
    }
  }

  if (loading) {
    return <Box display="flex" justifyContent="center" mt={6}><CircularProgress /></Box>;
  }

  return (
    <Box>
      {/* Header */}
      <Box mb={4}>
        <Box display="flex" alignItems="center" gap={1.5} mb={0.75}>
          <Box sx={{ width: 3, height: 26, bgcolor: "primary.main", borderRadius: 1, boxShadow: "0 0 10px rgba(255,107,0,0.6)", flexShrink: 0 }} />
          <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 700, fontSize: "1.8rem", letterSpacing: "0.05em", textTransform: "uppercase", lineHeight: 1 }}>
            Nueva cotización
          </Typography>
        </Box>
        <Typography sx={{ color: "text.secondary", fontSize: "0.82rem", ml: "19px" }}>
          Cargá piezas DXF y generá un presupuesto completo
        </Typography>
      </Box>

      {/* Stepper */}
      <Stepper activeStep={activeStep} sx={{ mb: 4, maxWidth: 600 }}>
        {STEPS.map((label, i) => (
          <Step key={label} completed={i < activeStep}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>

      {activeStep === 0 && <Step1 clients={clients} onCreated={handleQuotationCreated} />}
      {activeStep === 1 && quotation && (
        <Step2
          quotation={quotation}
          pieces={pieces}
          materials={materials}
          items={items}
          onItemAdded={refreshItems}
          onNext={() => setActiveStep(2)}
        />
      )}
      {activeStep === 2 && quotation && (
        <Step3 quotation={quotation} items={items} pieces={pieces} materials={materials} clients={clients} />
      )}

      <Snackbar open={!!toast} autoHideDuration={4000} onClose={() => setToast(null)} message={toast} />
    </Box>
  );
};

export default QuoteFromCadWizardPage;
