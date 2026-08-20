import { Add, ChevronLeft, ChevronRight, Delete } from "@mui/icons-material";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  FormControl,
  FormControlLabel,
  IconButton,
  InputAdornment,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Slider,
  TextField,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";

import { getMaterials, type Material } from "../services/materials";
import { getPieces, type Piece } from "../services/pieces";
import { calculateNesting, type NestingResult, type NestingSheet } from "../services/nesting";

const ACCENT = "#FF6B00";
const SHEET_COLOR = "#1A1C24";
const WASTE_COLOR = "#22242E";
const CANVAS_MAX_W = 720;
const CANVAS_MAX_H = 460;
const DENSE_THRESHOLD = 120;
const PALETTE = ["#FF6B00", "#3D8BFF", "#22C55E", "#EAB308", "#EC4899", "#8B5CF6", "#14B8A6"];

function colorForPiece(pieceId: number): string {
  return PALETTE[pieceId % PALETTE.length];
}

function niceStep(total: number) {
  const target = total / 6;
  const steps = [10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000];
  return steps.reduce((best, s) => (Math.abs(s - target) < Math.abs(best - target) ? s : best), steps[0]);
}

function NestingSVG({
  sheet,
  sheetWidthMm,
  sheetHeightMm,
}: {
  sheet: NestingSheet;
  sheetWidthMm: number;
  sheetHeightMm: number;
}) {
  const scaleX = CANVAS_MAX_W / sheetWidthMm;
  const scaleY = CANVAS_MAX_H / sheetHeightMm;
  const scale = Math.min(scaleX, scaleY);

  const svgW = sheetWidthMm * scale;
  const svgH = sheetHeightMm * scale;

  const [hovered, setHovered] = useState<number | null>(null);

  const isDense = sheet.placements.length > DENSE_THRESHOLD;

  const usedMaxX = sheet.placements.length > 0 ? Math.max(...sheet.placements.map((p) => p.x + p.width_mm)) : 0;
  const usedMaxY = sheet.placements.length > 0 ? Math.max(...sheet.placements.map((p) => p.y + p.height_mm)) : 0;
  const usedW = Math.min(usedMaxX * scale, svgW);
  const usedH = Math.min(usedMaxY * scale, svgH);

  const stepX = niceStep(sheetWidthMm);
  const stepY = niceStep(sheetHeightMm);
  const ticksX: number[] = [];
  for (let v = 0; v <= sheetWidthMm + 0.01; v += stepX) ticksX.push(v);
  const ticksY: number[] = [];
  for (let v = 0; v <= sheetHeightMm + 0.01; v += stepY) ticksY.push(v);

  return (
    <Box sx={{ overflowX: "auto" }}>
      <svg width={svgW + 34} height={svgH + 26} style={{ display: "block" }}>
        <defs>
          <pattern id="wasteHatch" width={6} height={6} patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
            <rect width={6} height={6} fill={WASTE_COLOR} />
            <line x1={0} y1={0} x2={0} y2={6} stroke="rgba(255,255,255,0.07)" strokeWidth={1.5} />
          </pattern>
        </defs>

        <g transform="translate(28, 4)">
          {/* Chapa completa = desperdicio de fondo */}
          <rect x={0} y={0} width={svgW} height={svgH} fill="url(#wasteHatch)" rx={2} />
          {/* Área efectivamente ocupada por el layout de piezas */}
          <rect x={0} y={0} width={usedW} height={usedH} fill={SHEET_COLOR} rx={2} />

          {/* Borde de la chapa */}
          <rect x={0.5} y={0.5} width={svgW - 1} height={svgH - 1} fill="none" stroke="#3D4050" strokeWidth={1} rx={2} />

          {/* Marcas de escala — eje X */}
          {ticksX.map((v) => (
            <g key={`tx-${v}`}>
              <line x1={v * scale} y1={svgH} x2={v * scale} y2={svgH + 4} stroke="#555" strokeWidth={1} />
              <text x={v * scale} y={svgH + 15} textAnchor="middle" fill="#666" fontSize={8.5}>
                {v}
              </text>
            </g>
          ))}
          <text x={svgW / 2} y={svgH + 26} textAnchor="middle" fill="#888" fontSize={9.5}>
            {sheetWidthMm} mm
          </text>

          {/* Marcas de escala — eje Y */}
          {ticksY.map((v) => (
            <g key={`ty-${v}`}>
              <line x1={-4} y1={v * scale} x2={0} y2={v * scale} stroke="#555" strokeWidth={1} />
              <text x={-7} y={v * scale + 3} textAnchor="end" fill="#666" fontSize={8.5}>
                {v}
              </text>
            </g>
          ))}
          <text
            x={-24} y={svgH / 2}
            textAnchor="middle"
            fill="#888"
            fontSize={9.5}
            transform={`rotate(-90, -24, ${svgH / 2})`}
          >
            {sheetHeightMm} mm
          </text>

          {/* Piezas */}
          {sheet.placements.map((pos, i) => {
            const px = pos.x * scale;
            const py = pos.y * scale;
            const pw = pos.width_mm * scale;
            const ph = pos.height_mm * scale;
            const isHov = hovered === i;
            const color = colorForPiece(pos.piece_id);
            return (
              <g key={i}>
                <title>{`${pos.piece_label}${pos.rotated ? " (girada 90°)" : ""} — ${pos.width_mm.toFixed(0)}×${pos.height_mm.toFixed(0)} mm`}</title>
                <rect
                  x={px} y={py}
                  width={pw} height={ph}
                  fill={isHov ? `${color}59` : `${color}2E`}
                  stroke={color}
                  strokeWidth={isHov ? 1.5 : isDense ? 0.4 : 0.8}
                  strokeOpacity={isDense && !isHov ? 0.6 : 1}
                  strokeDasharray={pos.rotated ? "3,2" : undefined}
                  rx={1}
                  style={{ cursor: "pointer", transition: "fill 0.1s" }}
                  onMouseEnter={() => setHovered(i)}
                  onMouseLeave={() => setHovered(null)}
                />
                {!isDense && pw > 18 && ph > 10 && (
                  <text
                    x={px + pw / 2}
                    y={py + ph / 2 + 3}
                    textAnchor="middle"
                    fill={isHov ? "#fff" : `${color}B3`}
                    fontSize={Math.min(pw * 0.35, ph * 0.55, 9)}
                    style={{ pointerEvents: "none", userSelect: "none" }}
                  >
                    {i + 1}
                  </text>
                )}
              </g>
            );
          })}
        </g>
      </svg>
    </Box>
  );
}

interface CartItem {
  piece_id: number;
  quantity: number;
}

const NestingPage = () => {
  const [pieces, setPieces] = useState<Piece[]>([]);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [loading, setLoading] = useState(true);
  const [calculating, setCalculating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<NestingResult | null>(null);
  const [activeSheet, setActiveSheet] = useState(0);

  const [cart, setCart] = useState<CartItem[]>([]);
  const [addPieceId, setAddPieceId] = useState<number | "">("");
  const [sheetW, setSheetW] = useState(1500);
  const [sheetH, setSheetH] = useState(3000);
  const [margin, setMargin] = useState(5);
  const [allowRotation, setAllowRotation] = useState(true);

  useEffect(() => {
    Promise.all([getPieces(), getMaterials()])
      .then(([p, m]) => { setPieces(p.filter((x) => x.has_dxf)); setMaterials(m); })
      .catch(() => setError("No se pudieron cargar los datos."))
      .finally(() => setLoading(false));
  }, []);

  function pieceById(id: number) {
    return pieces.find((p) => p.id === id);
  }

  function materialName(id: number | null) {
    if (!id) return null;
    return materials.find((m) => m.id === id)?.name ?? null;
  }

  const cartMaterialId = cart.length > 0 ? pieceById(cart[0].piece_id)?.material_id ?? null : null;

  const selectablePieces = pieces.filter(
    (p) => !cart.some((c) => c.piece_id === p.id) && (cartMaterialId == null || p.material_id === cartMaterialId)
  );

  const relevantMaterials = cartMaterialId != null ? materials.filter((m) => m.id === cartMaterialId) : materials;

  function applyMaterialDimensions(matId: number | null) {
    if (!matId) return;
    const mat = materials.find((m) => m.id === matId);
    if (mat?.sheet_width_mm) setSheetW(mat.sheet_width_mm);
    if (mat?.sheet_height_mm) setSheetH(mat.sheet_height_mm);
  }

  function addPiece() {
    if (addPieceId === "") return;
    setCart((c) => [...c, { piece_id: addPieceId as number, quantity: 1 }]);
    const piece = pieceById(addPieceId as number);
    if (cart.length === 0) applyMaterialDimensions(piece?.material_id ?? null);
    setAddPieceId("");
    setResult(null);
  }

  function updateQuantity(pieceId: number, qty: number) {
    setCart((c) => c.map((item) => (item.piece_id === pieceId ? { ...item, quantity: Math.max(1, qty) } : item)));
    setResult(null);
  }

  function removeFromCart(pieceId: number) {
    setCart((c) => c.filter((item) => item.piece_id !== pieceId));
    setResult(null);
  }

  async function handleCalculate() {
    if (cart.length === 0) return;
    setCalculating(true);
    setError(null);
    try {
      const res = await calculateNesting({
        items: cart,
        sheet_width_mm: sheetW,
        sheet_height_mm: sheetH,
        margin_mm: margin,
        allow_rotation: allowRotation,
      });
      setResult(res);
      setActiveSheet(0);
    } catch (e: any) {
      setError(e.message ?? "Error al calcular.");
    } finally {
      setCalculating(false);
    }
  }

  if (loading) return <Box display="flex" justifyContent="center" mt={6}><CircularProgress /></Box>;

  const currentSheet = result?.sheets[activeSheet];

  return (
    <Box>
      {/* Header */}
      <Box mb={4}>
        <Box display="flex" alignItems="center" gap={1.5} mb={0.75}>
          <Box sx={{ width: 3, height: 26, bgcolor: "#22C55E", borderRadius: 1, boxShadow: "0 0 10px rgba(34,197,94,0.5)", flexShrink: 0 }} />
          <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 700, fontSize: "1.8rem", letterSpacing: "0.05em", textTransform: "uppercase", lineHeight: 1 }}>
            Nesting
          </Typography>
        </Box>
        <Typography sx={{ color: "text.secondary", fontSize: "0.82rem", ml: "19px" }}>
          Combiná piezas y cantidades y calculá cómo distribuirlas en la menor cantidad de chapas
        </Typography>
      </Box>

      <Box display="flex" gap={3} flexWrap="wrap" alignItems="flex-start">
        {/* Panel de configuración */}
        <Paper variant="outlined" sx={{ p: 3, minWidth: 320, flexShrink: 0 }}>
          <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 600, fontSize: "0.75rem", letterSpacing: "0.1em", textTransform: "uppercase", color: "text.secondary", mb: 2 }}>
            Configuración
          </Typography>

          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

          <Box display="flex" flexDirection="column" gap={2}>
            {/* Agregar pieza */}
            <Box display="flex" gap={1}>
              <FormControl fullWidth size="small">
                <InputLabel>Agregar pieza</InputLabel>
                <Select label="Agregar pieza" value={addPieceId} onChange={(e) => setAddPieceId(e.target.value as number | "")}>
                  {selectablePieces.map((p) => (
                    <MenuItem key={p.id} value={p.id}>
                      <Box>
                        <Typography fontSize="0.875rem">{p.name}</Typography>
                        {materialName(p.material_id) && (
                          <Typography fontSize="0.72rem" color="text.secondary">
                            {materialName(p.material_id)}
                          </Typography>
                        )}
                      </Box>
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <IconButton color="primary" onClick={addPiece} disabled={addPieceId === ""} sx={{ flexShrink: 0 }}>
                <Add />
              </IconButton>
            </Box>

            {/* Carrito de piezas */}
            {cart.length > 0 && (
              <Box display="flex" flexDirection="column" gap={1}>
                {cart.map((item) => {
                  const piece = pieceById(item.piece_id);
                  return (
                    <Box key={item.piece_id} display="flex" alignItems="center" gap={1} sx={{ bgcolor: "action.hover", borderRadius: 1, px: 1, py: 0.5 }}>
                      <Box flex={1} minWidth={0}>
                        <Typography fontSize="0.82rem" noWrap sx={{ fontWeight: 500 }}>
                          {piece?.name ?? `Pieza ${item.piece_id}`}
                        </Typography>
                      </Box>
                      <TextField
                        type="number"
                        size="small"
                        value={item.quantity}
                        onChange={(e) => updateQuantity(item.piece_id, Number(e.target.value))}
                        sx={{ width: 72 }}
                        slotProps={{ htmlInput: { min: 1, style: { textAlign: "center" } } }}
                      />
                      <IconButton size="small" color="error" onClick={() => removeFromCart(item.piece_id)}>
                        <Delete fontSize="small" />
                      </IconButton>
                    </Box>
                  );
                })}
              </Box>
            )}

            {cart.length === 0 && (
              <Typography sx={{ fontSize: "0.78rem", color: "text.secondary" }}>
                Agregá una o más piezas (con DXF cargado) para armar el nesting.
              </Typography>
            )}

            {/* Cargar dimensiones desde material */}
            {relevantMaterials.length > 0 && (
              <Box>
                <Typography sx={{ fontSize: "0.72rem", color: "text.secondary", mb: 0.75 }}>
                  Cargar dimensiones de chapa desde material:
                </Typography>
                <Box display="flex" flexWrap="wrap" gap={0.75}>
                  {relevantMaterials.map((m) => (
                    <Chip
                      key={m.id}
                      label={`${m.name} (${m.sheet_width_mm}×${m.sheet_height_mm})`}
                      size="small"
                      variant="outlined"
                      onClick={() => applyMaterialDimensions(m.id)}
                      sx={{ fontSize: "0.7rem", cursor: "pointer" }}
                    />
                  ))}
                </Box>
              </Box>
            )}

            {/* Dimensiones de chapa */}
            <Box display="flex" gap={1.5}>
              <TextField
                label="Ancho chapa"
                type="number"
                value={sheetW}
                onChange={(e) => { setSheetW(Number(e.target.value)); setResult(null); }}
                InputProps={{ endAdornment: <InputAdornment position="end">mm</InputAdornment> }}
                fullWidth
              />
              <TextField
                label="Alto chapa"
                type="number"
                value={sheetH}
                onChange={(e) => { setSheetH(Number(e.target.value)); setResult(null); }}
                InputProps={{ endAdornment: <InputAdornment position="end">mm</InputAdornment> }}
                fullWidth
              />
            </Box>

            {/* Margen */}
            <Box>
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={0.5}>
                <Typography sx={{ fontSize: "0.8rem", color: "text.secondary" }}>
                  Margen entre piezas
                </Typography>
                <Typography sx={{ fontSize: "0.8rem", fontWeight: 600 }}>{margin} mm</Typography>
              </Box>
              <Slider
                value={margin}
                onChange={(_, v) => { setMargin(v as number); setResult(null); }}
                min={0} max={30} step={1}
                sx={{ color: ACCENT }}
              />
            </Box>

            <FormControlLabel
              control={
                <Checkbox
                  checked={allowRotation}
                  onChange={(e) => { setAllowRotation(e.target.checked); setResult(null); }}
                  size="small"
                />
              }
              label={<Typography sx={{ fontSize: "0.8rem" }}>Permitir rotación 90°</Typography>}
            />

            <Button
              variant="contained"
              onClick={handleCalculate}
              disabled={calculating || cart.length === 0}
              fullWidth
              sx={{ mt: 1 }}
            >
              {calculating ? "Calculando..." : "Calcular nesting"}
            </Button>
          </Box>
        </Paper>

        {/* Resultado */}
        <Box flex={1} minWidth={300}>
          {result && currentSheet ? (
            <Box display="flex" flexDirection="column" gap={2.5}>
              {/* Stats */}
              <Box display="flex" gap={2} flexWrap="wrap">
                {[
                  {
                    label: "Piezas ubicadas",
                    value: `${result.total_pieces_placed} / ${result.total_pieces_requested}`,
                    color: result.total_pieces_placed < result.total_pieces_requested ? "#F59E0B" : ACCENT,
                  },
                  { label: "Chapas necesarias", value: result.total_sheets.toString() },
                  { label: "Utilización promedio", value: `${result.overall_utilization_pct}%` },
                  { label: "Esta chapa", value: `${currentSheet.utilization_pct}% · ${currentSheet.placements.length} pzs` },
                ].map(({ label, value, color }) => (
                  <Paper key={label} variant="outlined" sx={{ px: 2, py: 1.5, minWidth: 140 }}>
                    <Typography sx={{ fontSize: "0.7rem", letterSpacing: "0.08em", textTransform: "uppercase", color: "text.secondary", mb: 0.25 }}>
                      {label}
                    </Typography>
                    <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 700, fontSize: "1.4rem", color: color ?? "text.primary", lineHeight: 1 }}>
                      {value}
                    </Typography>
                  </Paper>
                ))}
              </Box>

              {result.total_pieces_placed < result.total_pieces_requested && (
                <Alert severity="warning">
                  {result.total_pieces_requested - result.total_pieces_placed} pieza(s) no entran en la chapa ni siquiera solas — revisá las dimensiones de la chapa.
                </Alert>
              )}

              {/* Leyenda de colores por pieza */}
              <Box display="flex" flexWrap="wrap" gap={1.5}>
                {cart.map((item) => {
                  const piece = pieceById(item.piece_id);
                  return (
                    <Box key={item.piece_id} display="flex" alignItems="center" gap={0.75}>
                      <Box sx={{ width: 12, height: 12, borderRadius: 0.5, bgcolor: `${colorForPiece(item.piece_id)}33`, border: `1.5px solid ${colorForPiece(item.piece_id)}` }} />
                      <Typography sx={{ fontSize: "0.72rem", color: "text.secondary" }}>{piece?.name ?? item.piece_id}</Typography>
                    </Box>
                  );
                })}
                <Box display="flex" alignItems="center" gap={0.75}>
                  <Box sx={{ width: 12, height: 12, borderRadius: 0.5, border: "1.5px dashed #888" }} />
                  <Typography sx={{ fontSize: "0.72rem", color: "text.secondary" }}>Girada 90°</Typography>
                </Box>
              </Box>

              {/* SVG */}
              <Paper variant="outlined" sx={{ p: 2, overflowX: "auto" }}>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={1.5}>
                  <Typography sx={{ fontSize: "0.72rem", letterSpacing: "0.08em", textTransform: "uppercase", color: "text.secondary" }}>
                    Vista de la chapa — {result.sheet_width_mm} × {result.sheet_height_mm} mm
                  </Typography>
                  {result.total_sheets > 1 && (
                    <Box display="flex" alignItems="center" gap={0.5}>
                      <IconButton size="small" disabled={activeSheet === 0} onClick={() => setActiveSheet((i) => i - 1)}>
                        <ChevronLeft fontSize="small" />
                      </IconButton>
                      <Typography sx={{ fontSize: "0.78rem", minWidth: 90, textAlign: "center" }}>
                        Chapa {activeSheet + 1} de {result.total_sheets}
                      </Typography>
                      <IconButton size="small" disabled={activeSheet === result.total_sheets - 1} onClick={() => setActiveSheet((i) => i + 1)}>
                        <ChevronRight fontSize="small" />
                      </IconButton>
                    </Box>
                  )}
                </Box>
                <NestingSVG sheet={currentSheet} sheetWidthMm={result.sheet_width_mm} sheetHeightMm={result.sheet_height_mm} />
              </Paper>
            </Box>
          ) : (
            <Paper
              variant="outlined"
              sx={{
                height: 300,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexDirection: "column",
                gap: 1,
                color: "text.secondary",
              }}
            >
              <Typography fontSize="2rem">⬚</Typography>
              <Typography fontSize="0.875rem">
                Agregá piezas y calculá el nesting
              </Typography>
            </Paper>
          )}
        </Box>
      </Box>
    </Box>
  );
};

export default NestingPage;
