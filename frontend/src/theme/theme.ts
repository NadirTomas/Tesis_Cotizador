import { createTheme } from "@mui/material/styles";

export const theme = createTheme({
  palette: {
    mode: "dark",
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
      default: "#0A0B0E",
      paper: "#111318",
    },
    text: {
      primary: "#E8E9EB",
      secondary: "#6B7280",
    },
    divider: "#1E2028",
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
      styleOverrides: {
        body: {
          scrollbarWidth: "thin",
          scrollbarColor: "#2A2C36 transparent",
          "&::-webkit-scrollbar": { width: 6 },
          "&::-webkit-scrollbar-track": { background: "transparent" },
          "&::-webkit-scrollbar-thumb": {
            background: "#2A2C36",
            borderRadius: 3,
          },
        },
      },
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
        root: {
          backgroundImage: "none",
          backgroundColor: "#111318",
          border: "1px solid #1E2028",
          boxShadow: "none",
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
          backgroundColor: "#111318",
        },
      },
    },
    MuiDialog: {
      styleOverrides: {
        paper: {
          backgroundImage: "none",
          backgroundColor: "#13151C",
          border: "1px solid #1E2028",
          boxShadow: "0 24px 60px rgba(0,0,0,0.6)",
        },
      },
    },
    MuiDialogTitle: {
      styleOverrides: {
        root: {
          fontFamily: '"Barlow Condensed", sans-serif',
          fontWeight: 700,
          fontSize: "1.2rem",
          letterSpacing: "0.05em",
          textTransform: "uppercase",
          color: "#E8E9EB",
          borderBottom: "1px solid #1E2028",
          paddingBottom: 14,
        },
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
        root: {
          borderTop: "1px solid #1E2028",
          padding: "12px 24px",
        },
      },
    },
    MuiTableContainer: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
          backgroundColor: "#111318",
          border: "1px solid #1E2028",
          borderRadius: 8,
        },
      },
    },
    MuiTableHead: {
      styleOverrides: {
        root: {
          "& .MuiTableCell-head": {
            backgroundColor: "#0D0E12",
            fontFamily: '"Barlow Condensed", sans-serif',
            fontWeight: 600,
            fontSize: "0.78rem",
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            color: "#6B7280",
            borderBottom: "1px solid #1E2028",
            padding: "11px 16px",
            whiteSpace: "nowrap",
          },
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderBottom: "1px solid #181A22",
          padding: "13px 16px",
          fontSize: "0.875rem",
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          "&:hover": {
            backgroundColor: "rgba(255, 107, 0, 0.03) !important",
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
        root: {
          "& .MuiOutlinedInput-root": {
            "& fieldset": { borderColor: "#2A2C36" },
            "&:hover fieldset": { borderColor: "#3D4050" },
            "&.Mui-focused fieldset": {
              borderColor: "#FF6B00",
              borderWidth: 1.5,
            },
          },
          "& .MuiInputLabel-root.Mui-focused": {
            color: "#FF6B00",
          },
        },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        notchedOutline: { borderColor: "#2A2C36" },
        root: {
          "&:hover .MuiOutlinedInput-notchedOutline": {
            borderColor: "#3D4050",
          },
          "&.Mui-focused .MuiOutlinedInput-notchedOutline": {
            borderColor: "#FF6B00",
            borderWidth: 1.5,
          },
        },
      },
    },
    MuiSelect: {
      styleOverrides: {
        icon: { color: "#6B7280" },
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
        root: { borderColor: "#1E2028" },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: {
          borderRadius: 7,
          "&:hover": { backgroundColor: "rgba(255,255,255,0.05)" },
        },
      },
    },
    MuiTooltip: {
      styleOverrides: {
        tooltip: {
          backgroundColor: "#1C1E28",
          border: "1px solid #2A2C36",
          fontSize: "0.8rem",
          borderRadius: 6,
        },
        arrow: { color: "#1C1E28" },
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
        root: { borderRadius: 4, backgroundColor: "#1E2028" },
        bar: { borderRadius: 4, backgroundColor: "#FF6B00" },
      },
    },
    MuiInputLabel: {
      styleOverrides: {
        root: { fontSize: "0.875rem", color: "#6B7280" },
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
