import {
  Box,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Typography,
  Button,
  Divider,
} from "@mui/material";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import HomeOutlinedIcon from "@mui/icons-material/HomeOutlined";
import PeopleOutlinedIcon from "@mui/icons-material/PeopleOutlined";
import RequestQuoteOutlinedIcon from "@mui/icons-material/RequestQuoteOutlined";
import CategoryOutlinedIcon from "@mui/icons-material/CategoryOutlined";
import PrecisionManufacturingOutlinedIcon from "@mui/icons-material/PrecisionManufacturingOutlined";
import BusinessOutlinedIcon from "@mui/icons-material/BusinessOutlined";
import SettingsOutlinedIcon from "@mui/icons-material/SettingsOutlined";
import GridViewOutlinedIcon from "@mui/icons-material/GridViewOutlined";
import GroupOutlinedIcon from "@mui/icons-material/GroupOutlined";
import AddIcon from "@mui/icons-material/Add";
import LogoutIcon from "@mui/icons-material/Logout";
import SwapHorizIcon from "@mui/icons-material/SwapHoriz";
import { useAuth } from "../context/AuthContext";

const DRAWER_WIDTH = 232;

const navItems = [
  { label: "Inicio", path: "/", icon: <HomeOutlinedIcon fontSize="small" />, exact: true },
  {
    label: "Cotizaciones",
    path: "/quotations",
    icon: <RequestQuoteOutlinedIcon fontSize="small" />,
  },
  {
    label: "Piezas",
    path: "/pieces",
    icon: <PrecisionManufacturingOutlinedIcon fontSize="small" />,
  },
  { label: "Clientes", path: "/clients", icon: <PeopleOutlinedIcon fontSize="small" /> },
  { label: "Nesting", path: "/nesting", icon: <GridViewOutlinedIcon fontSize="small" /> },
  { label: "Materiales", path: "/materials", icon: <CategoryOutlinedIcon fontSize="small" /> },
  { label: "Máquina", path: "/machine-configs", icon: <SettingsOutlinedIcon fontSize="small" /> },
  { label: "Empresa", path: "/company", icon: <BusinessOutlinedIcon fontSize="small" /> },
];

const MainLayout = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { logout, clearCompany, companyName, companyRole } = useAuth();
  const items = companyRole === "owner"
    ? [...navItems, { label: "Empleados", path: "/employees", icon: <GroupOutlinedIcon fontSize="small" /> }]
    : navItems;

  const isActive = (path: string, exact?: boolean) => {
    if (exact) return location.pathname === path;
    return location.pathname.startsWith(path);
  };

  return (
    <Box sx={{ display: "flex", minHeight: "100vh", bgcolor: "background.default" }}>
      {/* Sidebar */}
      <Drawer
        variant="permanent"
        sx={{
          width: DRAWER_WIDTH,
          flexShrink: 0,
          "& .MuiDrawer-paper": {
            width: DRAWER_WIDTH,
            boxSizing: "border-box",
            bgcolor: "#0A0B0E",
            borderRight: "1px solid #1A1C24",
            display: "flex",
            flexDirection: "column",
          },
        }}
      >
        {/* Logo */}
        <Box sx={{ px: 2.5, py: 3, borderBottom: "1px solid #1A1C24" }}>
          <Box
            sx={{ display: "flex", alignItems: "center", gap: 1.5, cursor: "pointer" }}
            onClick={() => navigate("/")}
          >
            {/* Ícono marca */}
            <Box
              sx={{
                width: 34,
                height: 34,
                borderRadius: "8px",
                background: "linear-gradient(135deg, #FF6B00 0%, #FF8800 100%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow: "0 0 20px rgba(255, 107, 0, 0.35)",
                flexShrink: 0,
                position: "relative",
                overflow: "hidden",
              }}
            >
              {/* Símbolo láser: punto central con línea */}
              <Box
                sx={{
                  position: "absolute",
                  width: "100%",
                  height: "1.5px",
                  bgcolor: "rgba(255,255,255,0.35)",
                  top: "50%",
                  transform: "translateY(-50%)",
                }}
              />
              <Box
                sx={{
                  width: 7,
                  height: 7,
                  borderRadius: "50%",
                  bgcolor: "#fff",
                  boxShadow: "0 0 6px 2px rgba(255,255,255,0.7)",
                  zIndex: 1,
                }}
              />
            </Box>

            <Box>
              <Typography
                sx={{
                  fontFamily: '"Barlow Condensed", sans-serif',
                  fontWeight: 700,
                  fontSize: "1.1rem",
                  letterSpacing: "0.08em",
                  color: "#E8E9EB",
                  lineHeight: 1,
                  textTransform: "uppercase",
                }}
              >
                Cotiza
                <Box component="span" sx={{ color: "primary.main" }}>
                  Laser
                </Box>
              </Typography>
              <Typography
                sx={{
                  fontSize: "0.58rem",
                  color: "#3D4050",
                  letterSpacing: "0.12em",
                  textTransform: "uppercase",
                  fontFamily: '"DM Sans", sans-serif',
                  lineHeight: 1,
                  mt: 0.4,
                }}
              >
                Corte de fibra
              </Typography>
            </Box>
          </Box>
        </Box>

        {/* Empresa activa */}
        {companyName && (
          <Box sx={{ px: 2.5, py: 1.5, borderBottom: "1px solid #1A1C24", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 1 }}>
            <Typography noWrap sx={{ fontSize: "0.78rem", color: "#8B92A7", fontWeight: 500 }}>
              {companyName}
            </Typography>
            <IconButton
              size="small"
              title="Cambiar empresa"
              onClick={() => { clearCompany(); navigate("/select-company"); }}
              sx={{ color: "#6B7280", "&:hover": { color: "#E8E9EB" } }}
            >
              <SwapHorizIcon fontSize="small" />
            </IconButton>
          </Box>
        )}

        {/* Nav items */}
        <List sx={{ px: 1.5, py: 2, flex: 1, gap: 0.25, display: "flex", flexDirection: "column" }}>
          {items.map((item) => {
            const active = isActive(item.path, item.exact);
            return (
              <ListItemButton
                key={item.path}
                onClick={() => navigate(item.path)}
                sx={{
                  borderRadius: "7px",
                  px: 1.5,
                  py: 0.9,
                  position: "relative",
                  color: active ? "#E8E9EB" : "#6B7280",
                  bgcolor: active ? "rgba(255, 107, 0, 0.1)" : "transparent",
                  borderLeft: active ? "2px solid #FF6B00" : "2px solid transparent",
                  "&:hover": {
                    bgcolor: active
                      ? "rgba(255, 107, 0, 0.12)"
                      : "rgba(255,255,255,0.04)",
                    color: "#C8C9CB",
                  },
                  transition: "all 0.15s ease",
                }}
              >
                <ListItemIcon
                  sx={{
                    minWidth: 34,
                    color: active ? "primary.main" : "inherit",
                  }}
                >
                  {item.icon}
                </ListItemIcon>
                <ListItemText
                  primary={item.label}
                  primaryTypographyProps={{
                    fontSize: "0.875rem",
                    fontWeight: active ? 600 : 400,
                    fontFamily: '"DM Sans", sans-serif',
                    letterSpacing: "0.01em",
                  }}
                />
              </ListItemButton>
            );
          })}
        </List>

        <Divider />

        {/* CTA nueva cotización */}
        <Box sx={{ px: 2, py: 2.5, display: "flex", flexDirection: "column", gap: 1 }}>
          <Button
            fullWidth
            variant="contained"
            startIcon={<AddIcon fontSize="small" />}
            onClick={() => navigate("/quotes/new-from-cad")}
            sx={{ py: 1.1 }}
          >
            Nueva Cotización
          </Button>
          <Button
            fullWidth
            variant="text"
            startIcon={<LogoutIcon fontSize="small" />}
            onClick={() => { logout(); navigate("/login"); }}
            sx={{ py: 0.8, color: "#6B7280", fontSize: "0.8rem", "&:hover": { color: "#E8E9EB", bgcolor: "rgba(255,255,255,0.04)" } }}
          >
            Cerrar sesión
          </Button>
        </Box>
      </Drawer>

      {/* Contenido principal */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          minHeight: "100vh",
          bgcolor: "background.default",
          overflow: "auto",
        }}
      >
        <Box sx={{ p: { xs: 3, md: 4 } }}>
          <Outlet />
        </Box>
      </Box>
    </Box>
  );
};

export default MainLayout;
