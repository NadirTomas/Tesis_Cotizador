import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { ThemeModeProvider } from "./ThemeModeContext";
import { useThemeMode } from "./themeModeContextValue";

function Probe() {
  const { mode, toggleMode } = useThemeMode();
  return (
    <div>
      <span data-testid="mode">{mode}</span>
      <button onClick={toggleMode}>toggle</button>
    </div>
  );
}

describe("ThemeModeContext", () => {
  beforeEach(() => localStorage.clear());

  it("defaults to light when there is no stored preference", () => {
    render(<ThemeModeProvider><Probe /></ThemeModeProvider>);
    expect(screen.getByTestId("mode").textContent).toBe("light");
  });

  it("toggling switches the active mode", () => {
    render(<ThemeModeProvider><Probe /></ThemeModeProvider>);
    act(() => screen.getByText("toggle").click());
    expect(screen.getByTestId("mode").textContent).toBe("dark");

    act(() => screen.getByText("toggle").click());
    expect(screen.getByTestId("mode").textContent).toBe("light");
  });

  it("persists the chosen preference to localStorage", () => {
    render(<ThemeModeProvider><Probe /></ThemeModeProvider>);
    act(() => screen.getByText("toggle").click());
    expect(localStorage.getItem("theme_mode")).toBe("dark");
  });

  it("restores a previously stored preference on mount", () => {
    localStorage.setItem("theme_mode", "dark");
    render(<ThemeModeProvider><Probe /></ThemeModeProvider>);
    expect(screen.getByTestId("mode").textContent).toBe("dark");
  });
});
