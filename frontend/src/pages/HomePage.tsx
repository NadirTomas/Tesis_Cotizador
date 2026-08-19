import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import AddCircleOutlineIcon from "@mui/icons-material/AddCircleOutline";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import CategoryOutlinedIcon from "@mui/icons-material/CategoryOutlined";
import GroupOutlinedIcon from "@mui/icons-material/GroupOutlined";
import PrecisionManufacturingOutlinedIcon from "@mui/icons-material/PrecisionManufacturingOutlined";
import RequestQuoteOutlinedIcon from "@mui/icons-material/RequestQuoteOutlined";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getClients, type Client } from "../services/clients";
import { getStats, type DashboardStats } from "../services/nesting";

const STATUS_CONFIG: Record<string, { label: string; color: "default" | "warning" | "success" | "error" | "info" }> = {
  draft:     { label: "Borrador",  color: "warning" },
  sent:      { label: "Enviado",   color: "info" },
  accepted:  { label: "Aceptado", color: "success" },
  cancelled: { label: "Cancelado", color: "error" },
};

const navCards = [
  { label: "Cotizaciones",  description: "Gestioná y seguí tus presupuestos",        icon: <RequestQuoteOutlinedIcon sx={{ fontSize: 24 }} />,         path: "/quotations",    accent: "#FF6B00" },
  { label: "Piezas",        description: "Cargá archivos DXF y administrá piezas",   icon: <PrecisionManufacturingOutlinedIcon sx={{ fontSize: 24 }} />, path: "/pieces",        accent: "#3D8BFF" },
  { label: "Clientes",      description: "Administrá tu cartera de clientes",        icon: <GroupOutlinedIcon sx={{ fontSize: 24 }} />,               path: "/clients",       accent: "#22C55E" },
  { label: "Materiales",    description: "Configurá materiales y costos de chapa",   icon: <CategoryOutlinedIcon sx={{ fontSize: 24 }} />,            path: "/materials",     accent: "#A78BFA" },
];

function formatARS(v: number) {
  return v.toLocaleString("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 });
}

const HomePage = () => {
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [clients, setClients] = useState<Client[]>([]);
  const [loadingStats, setLoadingStats] = useState(true);
  const [statsError, setStatsError] = useState(false);

  useEffect(() => {
    Promise.all([getStats(), getClients()])
      .then(([s, c]) => { setStats(s); setClients(c); })
      .catch(() => setStatsError(true))
      .finally(() => setLoadingStats(false));
  }, []);

  function clientName(id: number) {
    return clients.find((c) => c.id === id)?.name ?? `#${id}`;
  }

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, mb: 0.75 }}>
          <Box sx={{ width: 3, height: 28, bgcolor: "primary.main", borderRadius: 1, boxShadow: "0 0 10px rgba(255,107,0,0.6)", flexShrink: 0 }} />
          <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 700, fontSize: "2rem", letterSpacing: "0.05em", color: "text.primary", lineHeight: 1, textTransform: "uppercase" }}>
            Panel Principal
          </Typography>
        </Box>
        <Typography sx={{ color: "text.secondary", fontSize: "0.875rem", ml: "19px" }}>
          Sistema de cotización para corte láser de fibra
        </Typography>
      </Box>

      {/* ── Métricas ── */}
      {loadingStats ? (
        <Box display="flex" justifyContent="center" py={4}><CircularProgress size={28} /></Box>
      ) : statsError ? (
        <Alert severity="warning" sx={{ mb: 3 }}>No se pudieron cargar las estadísticas.</Alert>
      ) : stats && (
        <>
          {/* Alerta de vencimientos */}
          {stats.expiring_soon > 0 && (
            <Box
              display="flex" alignItems="center" gap={1.5}
              sx={{ mb: 3, p: 1.5, px: 2, border: "1px solid", borderColor: "warning.dark", borderRadius: 1, bgcolor: "rgba(245,158,11,0.07)", cursor: "pointer" }}
              onClick={() => navigate("/quotations")}
            >
              <WarningAmberIcon sx={{ color: "warning.main", fontSize: 18, flexShrink: 0 }} />
              <Typography sx={{ fontSize: "0.85rem", color: "warning.light" }}>
                <b>{stats.expiring_soon}</b> cotización{stats.expiring_soon > 1 ? "es vencen" : " vence"} en los próximos 7 días
              </Typography>
            </Box>
          )}

          {/* Cards de métricas */}
          <Grid container spacing={2} sx={{ mb: 4 }}>
            {[
              { label: "Cotizaciones este mes", value: stats.this_month.toString(), sub: `${stats.total} en total`, accent: "#FF6B00" },
              { label: "Facturado este mes", value: formatARS(stats.total_ars_this_month), sub: "Cotizaciones emitidas", accent: "#3D8BFF" },
              { label: "Borradores",   value: (stats.by_status["draft"] ?? 0).toString(),    sub: "Sin enviar", accent: "#F59E0B" },
              { label: "Aceptadas",    value: (stats.by_status["accepted"] ?? 0).toString(), sub: "Confirmadas", accent: "#22C55E" },
            ].map(({ label, value, sub, accent }) => (
              <Grid size={{ xs: 12, sm: 6, md: 3 }} key={label}>
                <Card variant="outlined" sx={{ height: "100%" }}>
                  <CardContent sx={{ p: "20px !important" }}>
                    <Typography sx={{ fontSize: "0.7rem", letterSpacing: "0.1em", textTransform: "uppercase", color: "text.secondary", mb: 1 }}>
                      {label}
                    </Typography>
                    <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 700, fontSize: "1.7rem", color: accent, lineHeight: 1, mb: 0.5 }}>
                      {value}
                    </Typography>
                    <Typography sx={{ fontSize: "0.75rem", color: "text.secondary" }}>{sub}</Typography>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>

          {/* Últimas cotizaciones */}
          {stats.recent.length > 0 && (
            <Box sx={{ mb: 4 }}>
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={1.5}>
                <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 600, fontSize: "0.78rem", letterSpacing: "0.1em", textTransform: "uppercase", color: "text.secondary" }}>
                  Últimas cotizaciones
                </Typography>
                <Typography
                  sx={{ fontSize: "0.75rem", color: "primary.main", cursor: "pointer", "&:hover": { textDecoration: "underline" } }}
                  onClick={() => navigate("/quotations")}
                >
                  Ver todas →
                </Typography>
              </Box>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Número</TableCell>
                      <TableCell>Cliente</TableCell>
                      <TableCell>Estado</TableCell>
                      <TableCell align="right">Total ARS</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {stats.recent.map((q) => {
                      const sc = STATUS_CONFIG[q.status] ?? { label: q.status, color: "default" as const };
                      return (
                        <TableRow
                          key={q.id}
                          hover
                          sx={{ cursor: "pointer" }}
                          onClick={() => navigate(`/quotations/${q.id}`)}
                        >
                          <TableCell>
                            <span className="mono" style={{ color: "#E8E9EB", fontWeight: 500 }}>{q.number}</span>
                          </TableCell>
                          <TableCell sx={{ fontWeight: 500 }}>{clientName(q.client_id)}</TableCell>
                          <TableCell><Chip label={sc.label} color={sc.color} size="small" /></TableCell>
                          <TableCell align="right">
                            <span className="mono">{formatARS(q.total_ars)}</span>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>
          )}

          <Divider sx={{ mb: 4 }} />
        </>
      )}

      {/* CTA */}
      <Card
        onClick={() => navigate("/quotes/new-from-cad")}
        sx={{ mb: 3, cursor: "pointer", background: "linear-gradient(135deg, rgba(255,107,0,0.1) 0%, rgba(255,107,0,0.03) 100%)", border: "1px solid rgba(255,107,0,0.25)", "&:hover": { border: "1px solid rgba(255,107,0,0.55)", background: "linear-gradient(135deg, rgba(255,107,0,0.15) 0%, rgba(255,107,0,0.06) 100%)" }, transition: "all 0.2s ease" }}
      >
        <CardContent sx={{ p: "18px 24px !important", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <Box display="flex" alignItems="center" gap={2}>
            <Box sx={{ width: 42, height: 42, borderRadius: "10px", background: "linear-gradient(135deg, #FF6B00 0%, #FF8800 100%)", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 0 18px rgba(255,107,0,0.35)", flexShrink: 0 }}>
              <AddCircleOutlineIcon sx={{ color: "#fff", fontSize: 22 }} />
            </Box>
            <Box>
              <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 700, fontSize: "1.1rem", letterSpacing: "0.05em", color: "text.primary", textTransform: "uppercase", lineHeight: 1.1 }}>
                Nueva Cotización
              </Typography>
              <Typography sx={{ fontSize: "0.82rem", color: "text.secondary", mt: 0.25 }}>
                Cargá un DXF y generá un presupuesto completo
              </Typography>
            </Box>
          </Box>
          <ArrowForwardIcon sx={{ color: "primary.main", fontSize: 20, flexShrink: 0 }} />
        </CardContent>
      </Card>

      {/* Nav cards */}
      <Grid container spacing={2}>
        {navCards.map((card) => (
          <Grid size={{ xs: 12, sm: 6, md: 3 }} key={card.label}>
            <Card
              onClick={() => navigate(card.path)}
              sx={{ height: "100%", cursor: "pointer", "&:hover": { border: `1px solid ${card.accent}50`, transform: "translateY(-2px)", boxShadow: `0 8px 24px ${card.accent}12` }, transition: "all 0.2s ease" }}
            >
              <CardContent sx={{ p: "20px !important" }}>
                <Box sx={{ width: 40, height: 40, borderRadius: "10px", bgcolor: `${card.accent}18`, display: "flex", alignItems: "center", justifyContent: "center", color: card.accent, mb: 2 }}>
                  {card.icon}
                </Box>
                <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 700, fontSize: "1rem", letterSpacing: "0.05em", color: "text.primary", textTransform: "uppercase", mb: 0.5, lineHeight: 1.1 }}>
                  {card.label}
                </Typography>
                <Typography sx={{ fontSize: "0.8rem", color: "text.secondary", lineHeight: 1.45 }}>
                  {card.description}
                </Typography>
                <Box sx={{ mt: 2, display: "flex", alignItems: "center", gap: 0.5, color: card.accent }}>
                  <Typography sx={{ fontSize: "0.72rem", fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase" }}>Abrir</Typography>
                  <ArrowForwardIcon sx={{ fontSize: 12 }} />
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};

export default HomePage;
