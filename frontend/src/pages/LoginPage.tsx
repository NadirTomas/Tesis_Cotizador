import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  TextField,
  Typography,
} from "@mui/material";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { loginRequest } from "../services/auth";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await loginRequest(email, password);
      login(res.access_token);
      navigate("/");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al iniciar sesión");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box
      sx={{
        minHeight: "100vh",
        bgcolor: "background.default",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        position: "relative",
        overflow: "hidden",
        p: { xs: 2, sm: 3 },

        // Decorative gradient orbs
        "&::before": {
          content: '""',
          position: "absolute",
          width: 300,
          height: 300,
          background: "radial-gradient(circle, rgba(255, 107, 0, 0.08) 0%, rgba(255, 107, 0, 0) 70%)",
          borderRadius: "50%",
          top: -80,
          right: -100,
          zIndex: 0,
          pointerEvents: "none",
        },
        "&::after": {
          content: '""',
          position: "absolute",
          width: 250,
          height: 250,
          background: "radial-gradient(circle, rgba(61, 139, 255, 0.05) 0%, rgba(61, 139, 255, 0) 70%)",
          borderRadius: "50%",
          bottom: -50,
          left: -120,
          zIndex: 0,
          pointerEvents: "none",
        },
      }}
    >
      {/* Container relativo para z-index */}
      <Box
        component="form"
        onSubmit={handleSubmit}
        sx={{
          position: "relative",
          zIndex: 1,
          width: "100%",
          maxWidth: 420,
          bgcolor: "#0F1117",
          border: "1px solid #1E2028",
          borderRadius: "12px",
          p: { xs: 3.5, sm: 5 },
          background: "linear-gradient(135deg, rgba(17, 19, 24, 0.95) 0%, rgba(15, 17, 23, 0.98) 100%)",
          backdropFilter: "blur(4px)",
          boxShadow: "0 8px 32px rgba(0, 0, 0, 0.6), inset 0 1px 0 rgba(255, 107, 0, 0.1)",
          transition: "all 0.3s ease",

          "&:hover": {
            boxShadow: "0 16px 48px rgba(0, 0, 0, 0.7), inset 0 1px 0 rgba(255, 107, 0, 0.15)",
          },
        }}
      >
        {/* Decorative laser effect top-right */}
        <Box
          sx={{
            position: "absolute",
            top: 0,
            right: 0,
            width: 2,
            height: 80,
            background: "linear-gradient(to bottom, #FF6B00, transparent)",
            borderRadius: "2px 2px 0 0",
            opacity: 0.3,
          }}
        />

        {/* Logo Section */}
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 2,
            mb: 5,
            pb: 4,
            borderBottom: "1px solid rgba(30, 32, 40, 0.5)",
          }}
        >
          <Box
            sx={{
              width: 48,
              height: 48,
              borderRadius: "10px",
              background: "linear-gradient(135deg, #FF6B00 0%, #FF8800 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 0 24px rgba(255, 107, 0, 0.4), inset 0 1px 2px rgba(255,255,255,0.2)",
              flexShrink: 0,
              position: "relative",
              overflow: "hidden",
              animation: "pulse 3s ease-in-out infinite",

              "@keyframes pulse": {
                "0%, 100%": {
                  boxShadow: "0 0 24px rgba(255, 107, 0, 0.4), inset 0 1px 2px rgba(255,255,255,0.2)",
                },
                "50%": {
                  boxShadow: "0 0 32px rgba(255, 107, 0, 0.6), inset 0 1px 2px rgba(255,255,255,0.3)",
                },
              },
            }}
          >
            {/* Laser line */}
            <Box
              sx={{
                position: "absolute",
                width: "100%",
                height: "2px",
                bgcolor: "rgba(255,255,255,0.4)",
                top: "50%",
                transform: "translateY(-50%)",
              }}
            />
            {/* Laser dot */}
            <Box
              sx={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                bgcolor: "#fff",
                boxShadow: "0 0 8px 2px rgba(255,255,255,0.8)",
                zIndex: 1,
              }}
            />
          </Box>
          <Box>
            <Typography
              sx={{
                fontFamily: '"Barlow Condensed", sans-serif',
                fontWeight: 700,
                fontSize: "1.3rem",
                letterSpacing: "0.08em",
                color: "#E8E9EB",
                lineHeight: 1.2,
                textTransform: "uppercase",
                mb: 0.5,
              }}
            >
              Cotiza
              <Box component="span" sx={{ color: "primary.main", ml: 0.3 }}>
                Laser
              </Box>
            </Typography>
            <Typography
              sx={{
                fontSize: "0.65rem",
                color: "#6B7280",
                letterSpacing: "0.14em",
                textTransform: "uppercase",
                fontFamily: '"DM Sans", sans-serif',
                fontWeight: 500,
              }}
            >
              Cotizador de Corte por Fibra
            </Typography>
          </Box>
        </Box>

        {/* Title & Subtitle */}
        <Box sx={{ mb: 4 }}>
          <Typography
            sx={{
              fontFamily: '"Barlow Condensed", sans-serif',
              fontWeight: 700,
              fontSize: "1.75rem",
              letterSpacing: "0.02em",
              color: "#E8E9EB",
              mb: 1,
              textTransform: "uppercase",
            }}
          >
            Bienvenido
          </Typography>
          <Typography
            variant="body2"
            sx={{
              color: "#8B92A7",
              fontSize: "0.95rem",
              lineHeight: 1.5,
              fontWeight: 400,
            }}
          >
            Accedé a tu cuenta para generar cotizaciones
          </Typography>
        </Box>

        {/* Error Alert */}
        {error && (
          <Alert
            severity="error"
            sx={{
              mb: 3,
              borderRadius: "8px",
              fontSize: "0.875rem",
              "& .MuiAlert-icon": {
                color: "#EF4444",
              },
              backgroundColor: "rgba(239, 68, 68, 0.1)",
              borderLeft: "3px solid #EF4444",
              color: "#FECACA",
              animation: "slideIn 0.3s ease-out",

              "@keyframes slideIn": {
                "0%": {
                  opacity: 0,
                  transform: "translateY(-8px)",
                },
                "100%": {
                  opacity: 1,
                  transform: "translateY(0)",
                },
              },
            }}
          >
            {error}
          </Alert>
        )}

        {/* Form Fields */}
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2.5, mb: 3.5 }}>
          <TextField
            fullWidth
            label="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            placeholder="tu@email.com"
            autoComplete="email"
            autoFocus
            slotProps={{
              input: {
                sx: {
                  transition: "all 0.2s ease",
                  "&::placeholder": {
                    color: "#6B7280",
                    opacity: 0.6,
                  },
                },
              },
            }}
            sx={{
              "& .MuiOutlinedInput-root": {
                fontSize: "0.95rem",
              },
              "& .MuiInputLabel-root": {
                fontSize: "0.875rem",
                fontWeight: 500,
              },
            }}
          />
          <TextField
            fullWidth
            label="Contraseña"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            placeholder="••••••••"
            autoComplete="current-password"
            slotProps={{
              input: {
                sx: {
                  transition: "all 0.2s ease",
                  "&::placeholder": {
                    color: "#6B7280",
                    opacity: 0.6,
                  },
                },
              },
            }}
            sx={{
              "& .MuiOutlinedInput-root": {
                fontSize: "0.95rem",
              },
              "& .MuiInputLabel-root": {
                fontSize: "0.875rem",
                fontWeight: 500,
              },
            }}
          />
        </Box>

        {/* Submit Button */}
        <Button
          fullWidth
          type="submit"
          variant="contained"
          disabled={loading}
          sx={{
            py: 1.4,
            fontSize: "1rem",
            fontWeight: 600,
            letterSpacing: "0.02em",
            textTransform: "uppercase",
            position: "relative",
            overflow: "hidden",

            "&::before": {
              content: '""',
              position: "absolute",
              top: 0,
              left: "-100%",
              width: "100%",
              height: "100%",
              background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.15), transparent)",
              transition: "left 0.5s",
            },

            "&:hover:not(:disabled)": {
              "&::before": {
                left: "100%",
              },
            },

            "&:disabled": {
              opacity: 0.7,
            },

            transition: "all 0.3s ease",
          }}
        >
          {loading ? (
            <CircularProgress size={20} color="inherit" />
          ) : (
            "Ingresar a tu cuenta"
          )}
        </Button>

        {/* Footer hint */}
        <Typography
          sx={{
            fontSize: "0.75rem",
            color: "#6B7280",
            textAlign: "center",
            mt: 3,
            letterSpacing: "0.01em",
          }}
        >
          Sistema seguro con autenticación JWT
        </Typography>
      </Box>
    </Box>
  );
}
