import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  List,
  ListItemButton,
  ListItemText,
  Typography,
} from "@mui/material";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { getMyCompanies, type MyCompany } from "../services/companies";

export default function SelectCompanyPage() {
  const [companies, setCompanies] = useState<MyCompany[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const { selectCompany, logout } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    getMyCompanies()
      .then(setCompanies)
      .catch(() => setError("No se pudieron cargar tus empresas."))
      .finally(() => setLoading(false));
  }, []);

  function handleSelect(c: MyCompany) {
    selectCompany(c.id, c.role, c.company_name);
    navigate("/");
  }

  return (
    <Box
      sx={{
        minHeight: "100vh",
        bgcolor: "background.default",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        p: 3,
      }}
    >
      <Box
        sx={{
          width: "100%",
          maxWidth: 480,
          bgcolor: "#0F1117",
          border: "1px solid #1E2028",
          borderRadius: "12px",
          p: 4,
        }}
      >
        <Typography
          sx={{
            fontFamily: '"Barlow Condensed", sans-serif',
            fontWeight: 700,
            fontSize: "1.5rem",
            letterSpacing: "0.03em",
            textTransform: "uppercase",
            color: "#E8E9EB",
            mb: 0.5,
          }}
        >
          Elegí una empresa
        </Typography>
        <Typography sx={{ color: "#8B92A7", fontSize: "0.9rem", mb: 3 }}>
          Pertenecés a más de una empresa en CotizaLaser.
        </Typography>

        {loading && <Box display="flex" justifyContent="center" py={3}><CircularProgress size={28} /></Box>}
        {error && <Alert severity="error">{error}</Alert>}

        {!loading && !error && (
          <List sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
            {companies.map((c) => (
              <ListItemButton
                key={c.id}
                onClick={() => handleSelect(c)}
                sx={{ border: "1px solid", borderColor: "divider", borderRadius: 1.5, py: 1.5 }}
              >
                <ListItemText primary={c.company_name} />
                <Chip
                  label={c.role === "owner" ? "OWNER" : "EMPLOYEE"}
                  size="small"
                  color={c.role === "owner" ? "primary" : "default"}
                  variant="outlined"
                />
              </ListItemButton>
            ))}
          </List>
        )}

        <Button
          fullWidth
          variant="text"
          sx={{ mt: 3, color: "#6B7280" }}
          onClick={() => { logout(); navigate("/login"); }}
        >
          Cerrar sesión
        </Button>
      </Box>
    </Box>
  );
}
