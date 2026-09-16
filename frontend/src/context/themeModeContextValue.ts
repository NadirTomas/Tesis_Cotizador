import { createContext, useContext } from "react";
import type { PaletteMode } from "@mui/material";

export const STORAGE_KEY = "theme_mode";

export interface ThemeModeContextType {
  mode: PaletteMode;
  toggleMode: () => void;
}

export const ThemeModeContext = createContext<ThemeModeContextType>(null!);

export function readStoredMode(): PaletteMode {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

export function useThemeMode() {
  return useContext(ThemeModeContext);
}
