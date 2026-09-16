import { createTheme, type PaletteMode, type Theme } from "@mui/material/styles";

/**
 * Theme central de CotizaLaser. Antes era un único objeto dark-only con
 * colores hardcodeados en cada styleOverride; ahora es una factory por modo
 * para soportar light/dark sin duplicar la app. Los styleOverrides que
 * necesitan un tono que no es un token estándar de MUI (fondo de header de
 * tabla, bordes de input, thumb del scrollbar) resuelven el valor con
 * `theme.palette.mode` inline, en vez de agregar tokens custom nuevos al
 * palette — mantiene el diff acotado a este archivo.
 */
export function getTheme(mode: PaletteMode): Theme {
  const isDark = mode === "dark";

  return createTheme({
    palette: {
      mode,
      primary: {
        main: "#FF6B00",
        light: "#FF8C00",
        dark: "#E05500",
        contrastText: "#FFFFFF",
      },
      secondary: {
        main: "#3D8BFF",
        light: "#6AACFF",
        dark: "#1A6AE0",
        contrastText: "#FFFFFF",
      },
      background: {
        default: isDark ? "#0A0B0E" : "#F5F6F8",
        paper: isDark ? "#111318" : "#FFFFFF",
      },
      text: {
        primary: isDark ? "#E8E9EB" : "#14161C",
        secondary: isDark ? "#6B7280" : "#5B6472",
      },
      divider: isDark ? "#1E2028" : "#E3E5EA",
      error: { main: "#EF4444", contrastText: "#fff" },
      success: { main: "#22C55E", contrastText: "#fff" },
      warning: { main: "#F59E0B", contrastText: "#fff" },
      info: { main: "#3D8BFF", contrastText: "#fff" },
    },
    typography: {
      fontFamily: '"DM Sans", sans-serif',
      h1: {
        fontFamily: '"Barlow Condensed", sans-serif',
        fontWeight: 700,
        letterSpacing: "-0.01em",
      },
      h2: {
        fontFamily: '"Barlow Condensed", sans-serif',
        fontWeight: 700,
        letterSpacing: "-0.01em",
      },
      h3: {
        fontFamily: '"Barlow Condensed", sans-serif',
        fontWeight: 600,
      },
      h4: {
        fontFamily: '"Barlow Condensed", sans-serif',
        fontWeight: 600,
      },
      h5: {
        fontFamily: '"Barlow Condensed", sans-serif',
        fontWeight: 600,
        letterSpacing: "0.02em",
      },
      h6: {
        fontFamily: '"Barlow Condensed", sans-serif',
        fontWeight: 600,
        letterSpacing: "0.02em",
      },
      button: {
        fontFamily: '"DM Sans", sans-serif',
        fontWeight: 600,
        textTransform: "none",
        letterSpacing: "0.02em",
      },
    },
    shape: {
      borderRadius: 8,
    },
    components: {
      MuiCssBaseline: {
        styleOverrides: (theme) => ({
          body: {
            scrollbarWidth: "thin",
            scrollbarColor: `${theme.palette.mode === "dark" ? "#2A2C36" : "#C9CCD3"} transparent`,
            "&::-webkit-scrollbar": { width: 6 },
            "&::-webkit-scrollbar-track": { background: "transparent" },
            "&::-webkit-scrollbar-thumb": {
              background: theme.palette.mode === "dark" ? "#2A2C36" : "#C9CCD3",
              borderRadius: 3,
            },
          },
        }),
      },
      MuiButton: {
        defaultProps: { disableElevation: true },
        styleOverrides: {
          root: {
            borderRadius: 7,
            padding: "8px 18px",
            fontSize: "0.875rem",
            textTransform: "none",
          },
          containedPrimary: {
            background: "linear-gradient(135deg, #FF6B00 0%, #FF8800 100%)",
            boxShadow: "0 0 18px rgba(255, 107, 0, 0.18)",
            "&:hover": {
              background: "linear-gradient(135deg, #FF7D1A 0%, #FF9A00 100%)",
              boxShadow: "0 0 28px rgba(255, 107, 0, 0.35)",
            },
          },
          outlinedPrimary: {
            borderColor: "rgba(255, 107, 0, 0.5)",
            "&:hover": {
              borderColor: "#FF6B00",
              backgroundColor: "rgba(255, 107, 0, 0.06)",
            },
          },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: ({ theme }) => ({
            backgroundImage: "none",
            backgroundColor: theme.palette.background.paper,
            border: `1px solid ${theme.palette.divider}`,
            boxShadow: "none",
          }),
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: ({ theme }) => ({
            backgroundImage: "none",
            backgroundColor: theme.palette.background.paper,
          }),
        },
      },
      MuiDialog: {
        styleOverrides: {
          paper: ({ theme }) => ({
            backgroundImage: "none",
            backgroundColor: theme.palette.background.paper,
            border: `1px solid ${theme.palette.divider}`,
            boxShadow: theme.palette.mode === "dark" ? "0 24px 60px rgba(0,0,0,0.6)" : "0 24px 60px rgba(20,22,28,0.12)",
          }),
        },
      },
      MuiDialogTitle: {
        styleOverrides: {
          root: ({ theme }) => ({
            fontFamily: '"Barlow Condensed", sans-serif',
            fontWeight: 700,
            fontSize: "1.2rem",
            letterSpacing: "0.05em",
            textTransform: "uppercase",
            color: theme.palette.text.primary,
            borderBottom: `1px solid ${theme.palette.divider}`,
            paddingBottom: 14,
          }),
        },
      },
      MuiDialogContent: {
        styleOverrides: {
          root: {
            paddingTop: "20px !important",
          },
        },
      },
      MuiDialogActions: {
        styleOverrides: {
          root: ({ theme }) => ({
            borderTop: `1px solid ${theme.palette.divider}`,
            padding: "12px 24px",
          }),
        },
      },
      MuiTableContainer: {
        styleOverrides: {
          root: ({ theme }) => ({
            backgroundImage: "none",
            backgroundColor: theme.palette.background.paper,
            border: `1px solid ${theme.palette.divider}`,
            borderRadius: 8,
          }),
        },
      },
      MuiTableHead: {
        styleOverrides: {
          root: ({ theme }) => ({
            "& .MuiTableCell-head": {
              backgroundColor: theme.palette.mode === "dark" ? "#0D0E12" : "#F1F2F5",
              fontFamily: '"Barlow Condensed", sans-serif',
              fontWeight: 600,
              fontSize: "0.78rem",
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              color: theme.palette.text.secondary,
              borderBottom: `1px solid ${theme.palette.divider}`,
              padding: "11px 16px",
              whiteSpace: "nowrap",
            },
          }),
        },
      },
      MuiTableCell: {
        styleOverrides: {
          root: ({ theme }) => ({
            borderBottom: `1px solid ${theme.palette.divider}`,
            padding: "13px 16px",
            fontSize: "0.875rem",
          }),
        },
      },
      MuiTableRow: {
        styleOverrides: {
          root: {
            "&:hover": {
              backgroundColor: "rgba(255, 107, 0, 0.06) !important",
            },
            "&:last-child td": {
              borderBottom: 0,
            },
          },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: {
            fontFamily: '"DM Sans", sans-serif',
            fontWeight: 500,
            fontSize: "0.78rem",
            height: 24,
            borderRadius: 5,
          },
        },
      },
      MuiTextField: {
        defaultProps: { size: "small" },
        styleOverrides: {
          root: ({ theme }) => {
            const border = theme.palette.mode === "dark" ? "#2A2C36" : "#D5D8DE";
            const borderHover = theme.palette.mode === "dark" ? "#3D4050" : "#B8BCC5";
            return {
              "& .MuiOutlinedInput-root": {
                "& fieldset": { borderColor: border },
                "&:hover fieldset": { borderColor: borderHover },
                "&.Mui-focused fieldset": {
                  borderColor: "#FF6B00",
                  borderWidth: 1.5,
                },
              },
              "& .MuiInputLabel-root.Mui-focused": {
                color: "#FF6B00",
              },
            };
          },
        },
      },
      MuiOutlinedInput: {
        styleOverrides: {
          notchedOutline: ({ theme }) => ({
            borderColor: theme.palette.mode === "dark" ? "#2A2C36" : "#D5D8DE",
          }),
          root: ({ theme }) => ({
            "&:hover .MuiOutlinedInput-notchedOutline": {
              borderColor: theme.palette.mode === "dark" ? "#3D4050" : "#B8BCC5",
            },
            "&.Mui-focused .MuiOutlinedInput-notchedOutline": {
              borderColor: "#FF6B00",
              borderWidth: 1.5,
            },
          }),
        },
      },
      MuiSelect: {
        styleOverrides: {
          icon: ({ theme }) => ({ color: theme.palette.text.secondary }),
        },
      },
      MuiSnackbar: {
        defaultProps: {
          anchorOrigin: { vertical: "bottom", horizontal: "right" },
        },
      },
      MuiAlert: {
        styleOverrides: {
          root: { borderRadius: 8, fontSize: "0.875rem" },
        },
      },
      MuiDivider: {
        styleOverrides: {
          root: ({ theme }) => ({ borderColor: theme.palette.divider }),
        },
      },
      MuiIconButton: {
        styleOverrides: {
          root: {
            borderRadius: 7,
            "&:hover": { backgroundColor: "rgba(127,127,127,0.09)" },
          },
        },
      },
      MuiTooltip: {
        styleOverrides: {
          tooltip: ({ theme }) => ({
            backgroundColor: theme.palette.mode === "dark" ? "#1C1E28" : "#2A2C36",
            border: `1px solid ${theme.palette.mode === "dark" ? "#2A2C36" : "#3D4050"}`,
            color: "#FFFFFF",
            fontSize: "0.8rem",
            borderRadius: 6,
          }),
          arrow: ({ theme }) => ({ color: theme.palette.mode === "dark" ? "#1C1E28" : "#2A2C36" }),
        },
      },
      MuiStepper: {
        styleOverrides: {
          root: { backgroundColor: "transparent" },
        },
      },
      MuiStepLabel: {
        styleOverrides: {
          label: {
            fontFamily: '"DM Sans", sans-serif',
            fontSize: "0.875rem",
          },
        },
      },
      MuiLinearProgress: {
        styleOverrides: {
          root: ({ theme }) => ({ borderRadius: 4, backgroundColor: theme.palette.divider }),
          bar: { borderRadius: 4, backgroundColor: "#FF6B00" },
        },
      },
      MuiInputLabel: {
        styleOverrides: {
          root: ({ theme }) => ({ fontSize: "0.875rem", color: theme.palette.text.secondary }),
        },
      },
      MuiFormHelperText: {
        styleOverrides: {
          root: { fontSize: "0.78rem", marginTop: 4 },
        },
      },
      MuiListItemButton: {
        styleOverrides: {
          root: { borderRadius: 7 },
        },
      },
    },
  });
}

/** Theme por defecto (dark) — se mantiene exportado para no romper imports
 * existentes que todavía no pasaron por ThemeModeProvider (p. ej. tests). */
export const theme = getTheme("dark");
