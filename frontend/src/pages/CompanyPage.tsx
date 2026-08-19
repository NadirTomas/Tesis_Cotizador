import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Divider,
  Snackbar,
  TextField,
  Typography,
} from "@mui/material";
import { useEffect, useRef, useState } from "react";

import {
  getCompany,
  getCompanyLogoUrl,
  updateCompany,
  uploadLogo,
  type CompanyConfig,
} from "../services/company";

const CompanyPage = () => {
  const [data, setData] = useState<CompanyConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  // form fields
  const [companyName, setCompanyName] = useState("");
  const [legalName, setLegalName] = useState("");
  const [cuit, setCuit] = useState("");
  const [address, setAddress] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");

  // logo
  const [logoKey, setLogoKey] = useState(0); // fuerza re-render de la img
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const logoInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    try {
      setLoading(true);
      const c = await getCompany();
      setData(c);
      setCompanyName(c.company_name);
      setLegalName(c.legal_name ?? "");
      setCuit(c.cuit ?? "");
      setAddress(c.address ?? "");
      setPhone(c.phone ?? "");
      setEmail(c.email ?? "");
    } catch {
      setError("No se pudo cargar la configuración.");
    } finally {
      setLoading(false);
    }
  }

  async function handleLogoUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingLogo(true);
    try {
      await uploadLogo(file);
      setLogoKey((k) => k + 1);
      setToast("Logo actualizado.");
    } catch {
      setToast("Error al subir el logo.");
    } finally {
      setUploadingLogo(false);
      if (logoInputRef.current) logoInputRef.current.value = "";
    }
  }

  async function handleSave() {
    if (!companyName.trim()) return;
    setSaving(true);
    try {
      await updateCompany({
        company_name: companyName.trim(),
        ...(legalName.trim() && { legal_name: legalName.trim() }),
        ...(cuit.trim() && { cuit: cuit.trim() }),
        ...(address.trim() && { address: address.trim() }),
        ...(phone.trim() && { phone: phone.trim() }),
        ...(email.trim() && { email: email.trim() }),
      });
      setToast("Configuración guardada.");
    } catch {
      setToast("Error al guardar.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <Box display="flex" justifyContent="center" mt={6}><CircularProgress /></Box>;
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  return (
    <Box maxWidth={560}>
      {/* Header */}
      <Box mb={4}>
        <Box display="flex" alignItems="center" gap={1.5} mb={0.75}>
          <Box sx={{ width: 3, height: 26, bgcolor: "#A78BFA", borderRadius: 1, boxShadow: "0 0 10px rgba(167,139,250,0.5)", flexShrink: 0 }} />
          <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 700, fontSize: "1.8rem", letterSpacing: "0.05em", textTransform: "uppercase", lineHeight: 1 }}>
            Datos de la empresa
          </Typography>
        </Box>
        <Typography sx={{ color: "text.secondary", fontSize: "0.82rem", ml: "19px" }}>
          Estos datos aparecen en el encabezado del PDF de cotización
        </Typography>
      </Box>

      <Box display="flex" flexDirection="column" gap={2.5}>
        {/* Logo */}
        <Box>
          <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 600, fontSize: "0.75rem", letterSpacing: "0.1em", textTransform: "uppercase", color: "text.secondary", mb: 1.5 }}>
            Logo
          </Typography>
          <Box display="flex" alignItems="center" gap={2}>
            <Box
              sx={{
                width: 160, height: 64, border: "1px solid", borderColor: "divider",
                borderRadius: 1, display: "flex", alignItems: "center", justifyContent: "center",
                bgcolor: "background.paper", overflow: "hidden", flexShrink: 0,
              }}
            >
              {data?.has_logo ? (
                <Box
                  component="img"
                  key={logoKey}
                  src={`${getCompanyLogoUrl()}?v=${logoKey}`}
                  alt="Logo"
                  sx={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }}
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                />
              ) : (
                <Typography sx={{ fontSize: "0.75rem", color: "text.secondary" }}>Sin logo</Typography>
              )}
            </Box>
            <Box>
              <Button
                variant="outlined"
                size="small"
                disabled={uploadingLogo}
                onClick={() => logoInputRef.current?.click()}
              >
                {uploadingLogo ? "Subiendo..." : "Subir logo"}
              </Button>
              <Typography sx={{ fontSize: "0.7rem", color: "text.secondary", mt: 0.5 }}>
                PNG, JPG, SVG o WEBP. Aparece en el PDF.
              </Typography>
              <input ref={logoInputRef} type="file" accept=".png,.jpg,.jpeg,.svg,.webp" hidden onChange={handleLogoUpload} />
            </Box>
          </Box>
        </Box>

        <Divider />

        <Box>
          <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 600, fontSize: "0.75rem", letterSpacing: "0.1em", textTransform: "uppercase", color: "text.secondary", mb: 1.5 }}>
            Identificación
          </Typography>
          <Box display="flex" flexDirection="column" gap={2}>
            <TextField
              label="Nombre comercial"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              fullWidth
              required
              helperText="Nombre que aparece en el encabezado del PDF"
            />
            <TextField
              label="Razón social (opcional)"
              value={legalName}
              onChange={(e) => setLegalName(e.target.value)}
              fullWidth
            />
            <TextField
              label="CUIT (opcional)"
              value={cuit}
              onChange={(e) => setCuit(e.target.value)}
              fullWidth
            />
          </Box>
        </Box>

        <Divider />

        <Box>
          <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 600, fontSize: "0.75rem", letterSpacing: "0.1em", textTransform: "uppercase", color: "text.secondary", mb: 1.5 }}>
            Contacto
          </Typography>
          <Box display="flex" flexDirection="column" gap={2}>
            <TextField
              label="Dirección"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              fullWidth
            />
            <TextField
              label="Teléfono"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              fullWidth
            />
            <TextField
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              fullWidth
            />
          </Box>
        </Box>

        <Box display="flex" justifyContent="flex-end" mt={1}>
          <Button
            variant="contained"
            onClick={handleSave}
            disabled={saving || !companyName.trim()}
          >
            {saving ? "Guardando..." : "Guardar cambios"}
          </Button>
        </Box>
      </Box>

      <Snackbar open={!!toast} autoHideDuration={3000} onClose={() => setToast(null)} message={toast} />
    </Box>
  );
};

export default CompanyPage;
