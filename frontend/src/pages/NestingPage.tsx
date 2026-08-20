import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControl,
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
import { calculateNesting, type NestingResult } from "../services/nesting";

const ACCENT = "#FF6B00";
const SHEET_COLOR = "#1A1C24";
const WASTE_COLOR = "#22242E";
const PIECE_FILL = "rgba(255, 107, 0, 0.18)";
const PIECE_STROKE = "#FF6B00";
const CANVAS_MAX_W = 720;
const CANVAS_MAX_H = 460;
const DENSE_THRESHOLD = 120;

function niceStep(total: number) {
  const target = total / 6;
  const steps = [10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000];
  return steps.reduce((best, s) => (Math.abs(s - target) < Math.abs(best - target) ? s : best), steps[0]);
}

function NestingSVG({ result }: { result: NestingResult }) {
  const { sheet_width_mm, sheet_height_mm, piece_width_mm, piece_height_mm, positions } = result;

  const scaleX = CANVAS_MAX_W / sheet_width_mm;
  const scaleY = CANVAS_MAX_H / sheet_height_mm;
  const scale = Math.min(scaleX, scaleY);

  const svgW = sheet_width_mm * scale;
  const svgH = sheet_height_mm * scale;

  const [hovered, setHovered] = useState<number | null>(null);

  const isDense = positions.length > DENSE_THRESHOLD;

  const usedMaxX = positions.length > 0 ? Math.max(...positions.map((p) => p.x + piece_width_mm)) : 0;
  const usedMaxY = positions.length > 0 ? Math.max(...positions.map((p) => p.y + piece_height_mm)) : 0;
  const usedW = Math.min(usedMaxX * scale, svgW);
  const usedH = Math.min(usedMaxY * scale, svgH);

  const stepX = niceStep(sheet_width_mm);
  const stepY = niceStep(sheet_height_mm);
  const ticksX: number[] = [];
  for (let v = 0; v <= sheet_width_mm + 0.01; v += stepX) ticksX.push(v);
  const ticksY: number[] = [];
  for (let v = 0; v <= sheet_height_mm + 0.01; v += stepY) ticksY.push(v);

  return (
    <Box sx={{ overflowX: "auto" }}>
      <Box display="flex" alignItems="center" gap={2} mb={1}>
        <Box display="flex" alignItems="center" gap={0.75}>
          <Box sx={{ width: 12, height: 12, borderRadius: 0.5, bgcolor: PIECE_FILL, border: `1px solid ${PIECE_STROKE}` }} />
          <Typography sx={{ fontSize: "0.72rem", color: "text.secondary" }}>Aprovechado</Typography>
        </Box>
        <Box display="flex" alignItems="center" gap={0.75}>
          <Box sx={{ width: 12, height: 12, borderRadius: 0.5, bgcolor: WASTE_COLOR, backgroundImage: "repeating-linear-gradient(45deg, rgba(255,255,255,0.08) 0, rgba(255,255,255,0.08) 1px, transparent 1px, transparent 5px)" }} />
          <Typography sx={{ fontSize: "0.72rem", color: "text.secondary" }}>Desperdicio ({(100 - result.utilization_pct).toFixed(1)}%)</Typography>
        </Box>
      </Box>
      <svg
        width={svgW + 34}
        height={svgH + 26}
        style={{ display: "block" }}
      >
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
          <rect
            x={0.5} y={0.5}
            width={svgW - 1} height={svgH - 1}
            fill="none"
            stroke="#3D4050"
            strokeWidth={1}
            rx={2}
          />

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
            {sheet_width_mm} mm
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
            {sheet_height_mm} mm
          </text>

          {/* Piezas */}
          {positions.map((pos, i) => {
            const px = pos.x * scale;
            const py = pos.y * scale;
            const pw = piece_width_mm * scale;
            const ph = piece_height_mm * scale;
            const isHov = hovered === i;
            return (
              <g key={i}>
                <rect
                  x={px} y={py}
                  width={pw} height={ph}
                  fill={isHov ? "rgba(255,107,0,0.35)" : PIECE_FILL}
                  stroke={PIECE_STROKE}
                  strokeWidth={isHov ? 1.5 : isDense ? 0.4 : 0.8}
                  strokeOpacity={isDense && !isHov ? 0.6 : 1}
                  rx={1}
                  style={{ cursor: "pointer", transition: "fill 0.1s" }}
                  onMouseEnter={() => setHovered(i)}
                  onMouseLeave={() => setHovered(null)}
                />
                {/* Número de pieza si hay espacio y no está saturado de piezas */}
                {!isDense && pw > 18 && ph > 10 && (
                  <text
                    x={px + pw / 2}
                    y={py + ph / 2 + 3}
                    textAnchor="middle"
                    fill={isHov ? "#fff" : "rgba(255,107,0,0.7)"}
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

const NestingPage = () => {
  const [pieces, setPieces] = useState<Piece[]>([]);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [loading, setLoading] = useState(true);
  const [calculating, setCalculating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<NestingResult | null>(null);

  const [pieceId, setPieceId] = useState<number | "">("");
  const [sheetW, setSheetW] = useState(1500);
  const [sheetH, setSheetH] = useState(3000);
  const [margin, setMargin] = useState(5);

  useEffect(() => {
    Promise.all([getPieces(), getMaterials()])
      .then(([p, m]) => { setPieces(p.filter((x) => x.has_dxf)); setMaterials(m); })
      .catch(() => setError("No se pudieron cargar los datos."))
      .finally(() => setLoading(false));
  }, []);

  function materialName(id: number | null) {
    if (!id) return null;
    return materials.find((m) => m.id === id)?.name ?? null;
  }

  function applyMaterialDimensions(matId: number | null) {
    if (!matId) return;
    const mat = materials.find((m) => m.id === matId);
    if (mat?.sheet_width_mm) setSheetW(mat.sheet_width_mm);
    if (mat?.sheet_height_mm) setSheetH(mat.sheet_height_mm);
  }

  async function handleCalculate() {
    if (pieceId === "") return;
    setCalculating(true);
    setError(null);
    try {
      const res = await calculateNesting({
        piece_id: pieceId as number,
        sheet_width_mm: sheetW,
        sheet_height_mm: sheetH,
        margin_mm: margin,
      });
      setResult(res);
    } catch (e: any) {
      setError(e.message ?? "Error al calcular.");
    } finally {
      setCalculating(false);
    }
  }

  const selectedPiece = pieces.find((p) => p.id === pieceId);
  const relevantMaterials = selectedPiece?.material_id
    ? materials.filter((m) => m.id === selectedPiece.material_id)
    : materials;

  if (loading) return <Box display="flex" justifyContent="center" mt={6}><CircularProgress /></Box>;

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
          Calculá cuántas piezas entran en una chapa y visualizá el layout
        </Typography>
      </Box>

      <Box display="flex" gap={3} flexWrap="wrap" alignItems="flex-start">
        {/* Panel de configuración */}
        <Paper variant="outlined" sx={{ p: 3, minWidth: 300, flexShrink: 0 }}>
          <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 600, fontSize: "0.75rem", letterSpacing: "0.1em", textTransform: "uppercase", color: "text.secondary", mb: 2 }}>
            Configuración
          </Typography>

          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

          <Box display="flex" flexDirection="column" gap={2}>
            {/* Pieza */}
            <FormControl fullWidth required>
              <InputLabel>Pieza (con DXF)</InputLabel>
              <Select
                label="Pieza (con DXF)"
                value={pieceId}
                onChange={(e) => {
                  const id = e.target.value as number | "";
                  setPieceId(id);
                  setResult(null);
                  if (id !== "") {
                    const piece = pieces.find((p) => p.id === id);
                    applyMaterialDimensions(piece?.material_id ?? null);
                  }
                }}
              >
                {pieces.map((p) => (
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

            <Button
              variant="contained"
              onClick={handleCalculate}
              disabled={calculating || pieceId === ""}
              fullWidth
              sx={{ mt: 1 }}
            >
              {calculating ? "Calculando..." : "Calcular nesting"}
            </Button>
          </Box>
        </Paper>

        {/* Resultado */}
        <Box flex={1} minWidth={300}>
          {result ? (
            <Box display="flex" flexDirection="column" gap={2.5}>
              {/* Stats */}
              <Box display="flex" gap={2} flexWrap="wrap">
                {[
                  { label: "Piezas en chapa", value: result.pieces_fit.toString(), color: ACCENT },
                  { label: "Distribución", value: `${result.pieces_per_row} × ${result.rows}` },
                  { label: "Utilización", value: `${result.utilization_pct}%` },
                  { label: "Pieza (bbox)", value: `${result.piece_width_mm.toFixed(1)} × ${result.piece_height_mm.toFixed(1)} mm` },
                ].map(({ label, value, color }) => (
                  <Paper key={label} variant="outlined" sx={{ px: 2, py: 1.5, minWidth: 130 }}>
                    <Typography sx={{ fontSize: "0.7rem", letterSpacing: "0.08em", textTransform: "uppercase", color: "text.secondary", mb: 0.25 }}>
                      {label}
                    </Typography>
                    <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 700, fontSize: "1.4rem", color: color ?? "text.primary", lineHeight: 1 }}>
                      {value}
                    </Typography>
                  </Paper>
                ))}
              </Box>

              {/* SVG */}
              <Paper variant="outlined" sx={{ p: 2, overflowX: "auto" }}>
                <Typography sx={{ fontSize: "0.72rem", letterSpacing: "0.08em", textTransform: "uppercase", color: "text.secondary", mb: 1.5 }}>
                  Vista de la chapa — {result.sheet_width_mm} × {result.sheet_height_mm} mm
                </Typography>
                <NestingSVG result={result} />
              </Paper>

              {result.pieces_fit === 0 && (
                <Alert severity="warning">
                  La pieza ({result.piece_width_mm.toFixed(0)}×{result.piece_height_mm.toFixed(0)} mm) no entra en la chapa con el margen configurado.
                </Alert>
              )}
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
                Seleccioná una pieza y calculá el nesting
              </Typography>
            </Paper>
          )}
        </Box>
      </Box>
    </Box>
  );
};

export default NestingPage;
