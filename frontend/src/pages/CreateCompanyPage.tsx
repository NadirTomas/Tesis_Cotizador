import { useState } from "react";
import { Alert, Box, Button, TextField, Typography } from "@mui/material";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { createCompany } from "../services/companies";

export default function CreateCompanyPage() {
  const [companyName, setCompanyName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { selectCompany, logout } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!companyName.trim()) return;
    setLoading(true);
    setError("");
    try {
      const company = await createCompany({ company_name: companyName.trim() });
      selectCompany(company.id, "owner", company.company_name);
      navigate("/");
    } catch {
      setError("No se pudo crear la empresa.");
    } finally {
      setLoading(false);
    }
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
        component="form"
        onSubmit={handleSubmit}
        sx={{
          width: "100%",
          maxWidth: 440,
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
          Creá tu empresa
        </Typography>
        <Typography sx={{ color: "#8B92A7", fontSize: "0.9rem", mb: 3 }}>
          Todavía no pertenecés a ninguna empresa. Vas a quedar como OWNER.
        </Typography>

        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        <TextField
          fullWidth
          label="Nombre de la empresa"
          value={companyName}
          onChange={(e) => setCompanyName(e.target.value)}
          required
          autoFocus
          sx={{ mb: 3 }}
        />

        <Button fullWidth type="submit" variant="contained" disabled={loading || !companyName.trim()}>
          {loading ? "Creando..." : "Crear empresa"}
        </Button>

        <Button
          fullWidth
          variant="text"
          sx={{ mt: 1.5, color: "#6B7280" }}
          onClick={() => { logout(); navigate("/login"); }}
        >
          Cerrar sesión
        </Button>
      </Box>
    </Box>
  );
}
