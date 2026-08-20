import { Box, Typography } from "@mui/material";
import type { GeoJSONPolygon } from "../services/stock";

const ACCENT = "#FF6B00";
const CANVAS_BG = "#0B0C10";
const SHEET_COLOR = "#262A34";
const SHEET_STROKE = "#5A6270";
const CANVAS_MAX_W = 520;
const CANVAS_MAX_H = 380;

export interface PieceOverlay {
  x: number;
  y: number;
  width_mm: number;
  height_mm: number;
  rotation: number;
}

export default function StockGeometryView({
  geometry,
  piece,
  label,
}: {
  geometry: GeoJSONPolygon;
  piece?: PieceOverlay;
  label?: string;
}) {
  const rings = geometry.coordinates;
  const allPoints = rings.flat();
  const xs = allPoints.map((p) => p[0]);
  const ys = allPoints.map((p) => p[1]);
  const minX = Math.min(...xs);
  const minY = Math.min(...ys);
  const maxX = Math.max(...xs);
  const maxY = Math.max(...ys);
  const geomW = maxX - minX || 1;
  const geomH = maxY - minY || 1;

  const scale = Math.min(CANVAS_MAX_W / geomW, CANVAS_MAX_H / geomH);
  const svgW = geomW * scale;
  const svgH = geomH * scale;

  // SVG y crece hacia abajo; invertimos para que el origen (0,0) del stock
  // quede abajo-izquierda, como es habitual al pensar una chapa física.
  const toSvgY = (yMm: number) => svgH - (yMm - minY) * scale;
  const toSvgX = (xMm: number) => (xMm - minX) * scale;

  const pathD = rings
    .map((ring) => {
      const pts = ring.map(([x, y]) => `${toSvgX(x)},${toSvgY(y)}`).join(" L ");
      return `M ${pts} Z`;
    })
    .join(" ");

  return (
    <Box>
      {label && (
        <Typography sx={{ fontSize: "0.72rem", letterSpacing: "0.08em", textTransform: "uppercase", color: "text.secondary", mb: 1 }}>
          {label}
        </Typography>
      )}
      <Box sx={{ overflowX: "auto" }}>
        <svg width={svgW + 4} height={svgH + 24} style={{ display: "block", background: CANVAS_BG, borderRadius: 6 }}>
          <g transform="translate(2, 2)">
            <path d={pathD} fill={SHEET_COLOR} stroke={SHEET_STROKE} strokeWidth={1.5} fillRule="evenodd" />
            <text x={svgW / 2} y={svgH + 16} textAnchor="middle" fill="#6B7280" fontSize={10.5}>
              {geomW.toFixed(0)} × {geomH.toFixed(0)} mm
            </text>
            {piece && (
              <g>
                <title>{`Pieza — ${piece.width_mm.toFixed(0)}×${piece.height_mm.toFixed(0)} mm${piece.rotation ? ` · girada ${piece.rotation}°` : ""}`}</title>
                <rect
                  x={toSvgX(piece.x)}
                  y={toSvgY(piece.y + piece.height_mm)}
                  width={piece.width_mm * scale}
                  height={piece.height_mm * scale}
                  fill="rgba(255, 107, 0, 0.2)"
                  stroke={ACCENT}
                  strokeWidth={1.5}
                  rx={1}
                />
              </g>
            )}
          </g>
        </svg>
      </Box>
    </Box>
  );
}
