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

import { useAuth } from "../context/AuthContext";
import AuthedImage from "../components/AuthedImage";
import {
  getCompany,
  getCompanyLogoUrl,
  updateCompany,
  uploadLogo,
  type Company,
} from "../services/companies";

const CompanyPage = () => {
  const { companyId, companyRole } = useAuth();
  const isOwner = companyRole === "owner";

  const [data, setData] = useState<Company | null>(null);
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

  // retazos: área en string para poder editar libremente; ancho/alto en
  // string vacío = null (sin mínimo configurado para esa dimensión)
  const [remnantAreaMm2, setRemnantAreaMm2] = useState("2500");
  const [remnantWidthMm, setRemnantWidthMm] = useState("");
  const [remnantHeightMm, setRemnantHeightMm] = useState("");

  // logo
  const [logoKey, setLogoKey] = useState(0); // fuerza re-fetch de la img
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const logoInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    load();
  }, [companyId]);

  async function load() {
    if (!companyId) return;
    try {
      setLoading(true);
      const c = await getCompany(companyId);
      setData(c);
      setCompanyName(c.company_name);
      setLegalName(c.legal_name ?? "");
      setCuit(c.cuit ?? "");
      setAddress(c.address ?? "");
      setPhone(c.phone ?? "");
      setEmail(c.email ?? "");
      setRemnantAreaMm2(String(c.minimum_remnant_area_mm2 ?? 2500));
      setRemnantWidthMm(c.minimum_remnant_width_mm != null ? String(c.minimum_remnant_width_mm) : "");
      setRemnantHeightMm(c.minimum_remnant_height_mm != null ? String(c.minimum_remnant_height_mm) : "");
    } catch {
      setError("No se pudo cargar la configuración.");
    } finally {
      setLoading(false);
    }
  }

  async function handleLogoUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !companyId) return;
    setUploadingLogo(true);
    try {
      await uploadLogo(companyId, file);
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
    if (!companyName.trim() || !companyId) return;
    setSaving(true);
    try {
      await updateCompany(companyId, {
        company_name: companyName.trim(),
        ...(legalName.trim() && { legal_name: legalName.trim() }),
        ...(cuit.trim() && { cuit: cuit.trim() }),
        ...(address.trim() && { address: address.trim() }),
        ...(phone.trim() && { phone: phone.trim() }),
        ...(email.trim() && { email: email.trim() }),
        minimum_remnant_area_mm2: Math.max(0, parseFloat(remnantAreaMm2) || 0),
        minimum_remnant_width_mm: remnantWidthMm.trim() === "" ? null : Math.max(0, parseFloat(remnantWidthMm) || 0),
        minimum_remnant_height_mm: remnantHeightMm.trim() === "" ? null : Math.max(0, parseFloat(remnantHeightMm) || 0),
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
          {!isOwner && " · Solo el OWNER puede editarlos"}
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
              {data?.has_logo && companyId ? (
                <AuthedImage
                  key={logoKey}
                  src={getCompanyLogoUrl(companyId)}
                  alt="Logo"
                  sx={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }}
                />
              ) : (
                <Typography sx={{ fontSize: "0.75rem", color: "text.secondary" }}>Sin logo</Typography>
              )}
            </Box>
            {isOwner && (
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
            )}
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
              disabled={!isOwner}
              helperText="Nombre que aparece en el encabezado del PDF"
            />
            <TextField
              label="Razón social (opcional)"
              value={legalName}
              onChange={(e) => setLegalName(e.target.value)}
              fullWidth
              disabled={!isOwner}
            />
            <TextField
              label="CUIT (opcional)"
              value={cuit}
              onChange={(e) => setCuit(e.target.value)}
              fullWidth
              disabled={!isOwner}
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
              disabled={!isOwner}
            />
            <TextField
              label="Teléfono"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              fullWidth
              disabled={!isOwner}
            />
            <TextField
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              fullWidth
              disabled={!isOwner}
            />
          </Box>
        </Box>

        <Divider />

        <Box>
          <Typography sx={{ fontFamily: '"Barlow Condensed", sans-serif', fontWeight: 600, fontSize: "0.75rem", letterSpacing: "0.1em", textTransform: "uppercase", color: "text.secondary", mb: 1.5 }}>
            Retazos
          </Typography>
          <Typography sx={{ fontSize: "0.78rem", color: "text.secondary", mb: 2 }}>
            Umbrales mínimos para decidir si un fragmento de chapa se conserva como retazo o se descarta como scrap al confirmar un corte.
          </Typography>
          <Box display="flex" flexDirection="column" gap={2}>
            <TextField
              label="Área mínima (mm²)"
              type="number"
              value={remnantAreaMm2}
              onChange={(e) => setRemnantAreaMm2(e.target.value)}
              fullWidth
              required
              disabled={!isOwner}
              slotProps={{ htmlInput: { min: 0, step: "1" } }}
              helperText={
                (() => {
                  const n = parseFloat(remnantAreaMm2);
                  return Number.isFinite(n) && n > 0
                    ? `Retazos por debajo de esto se descartan · ≈ una chapa de ${Math.round(Math.sqrt(n))}×${Math.round(Math.sqrt(n))}mm`
                    : "Retazos por debajo de esto se descartan como scrap";
                })()
              }
            />
            <TextField
              label="Ancho mínimo (mm, opcional)"
              type="number"
              value={remnantWidthMm}
              onChange={(e) => setRemnantWidthMm(e.target.value)}
              fullWidth
              disabled={!isOwner}
              slotProps={{ htmlInput: { min: 0, step: "1" } }}
              helperText="Vacío = sin mínimo de ancho"
            />
            <TextField
              label="Alto mínimo (mm, opcional)"
              type="number"
              value={remnantHeightMm}
              onChange={(e) => setRemnantHeightMm(e.target.value)}
              fullWidth
              disabled={!isOwner}
              slotProps={{ htmlInput: { min: 0, step: "1" } }}
              helperText="Vacío = sin mínimo de alto"
            />
          </Box>
        </Box>

        {isOwner && (
          <Box display="flex" justifyContent="flex-end" mt={1}>
            <Button
              variant="contained"
              onClick={handleSave}
              disabled={saving || !companyName.trim()}
            >
              {saving ? "Guardando..." : "Guardar cambios"}
            </Button>
          </Box>
        )}
      </Box>

      <Snackbar open={!!toast} autoHideDuration={3000} onClose={() => setToast(null)} message={toast} />
    </Box>
  );
};

export default CompanyPage;
