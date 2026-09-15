import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AiAssistantWidget from "./AiAssistantWidget";

const isWebGpuSupported = vi.fn();
vi.mock("../services/aiAssistantContent", async () => {
  const actual = await vi.importActual<typeof import("../services/aiAssistantContent")>(
    "../services/aiAssistantContent"
  );
  return {
    ...actual,
    isWebGpuSupported: (...args: unknown[]) => isWebGpuSupported(...args),
  };
});

const getOrCreateEngine = vi.fn();
const streamAssistantReply = vi.fn();
vi.mock("../services/aiAssistant", () => ({
  getOrCreateEngine: (...args: unknown[]) => getOrCreateEngine(...args),
  streamAssistantReply: (...args: unknown[]) => streamAssistantReply(...args),
}));

describe("AiAssistantWidget", () => {
  beforeEach(() => {
    isWebGpuSupported.mockReset();
    getOrCreateEngine.mockReset();
    streamAssistantReply.mockReset();
  });

  it("renders closed by default and does not touch WebLLM until opened", () => {
    render(<AiAssistantWidget />);
    expect(screen.getByLabelText("Asistente IA")).toBeInTheDocument();
    expect(isWebGpuSupported).not.toHaveBeenCalled();
    expect(getOrCreateEngine).not.toHaveBeenCalled();
  });

  it("opens and closes the panel without breaking the rest of the page", async () => {
    isWebGpuSupported.mockResolvedValue(false);
    const user = userEvent.setup();
    render(
      <div>
        <button>Otro botón de la app</button>
        <AiAssistantWidget />
      </div>
    );

    await user.click(screen.getByLabelText("Asistente IA"));
    expect(await screen.findByText(/WebGPU/i)).toBeInTheDocument();

    await user.click(screen.getByLabelText("Asistente IA"));
    expect(screen.queryByText(/WebGPU/i)).not.toBeInTheDocument();
    expect(screen.getByText("Otro botón de la app")).toBeInTheDocument();
  });

  it("shows the WebGPU-unsupported fallback and never calls getOrCreateEngine", async () => {
    isWebGpuSupported.mockResolvedValue(false);
    const user = userEvent.setup();
    render(<AiAssistantWidget />);

    await user.click(screen.getByLabelText("Asistente IA"));

    expect(
      await screen.findByText(
        "El asistente IA local requiere un navegador y dispositivo compatibles con WebGPU."
      )
    ).toBeInTheDocument();
    expect(getOrCreateEngine).not.toHaveBeenCalled();
  });

  it("loads the engine, shows suggested questions, and streams a reply end to end", async () => {
    isWebGpuSupported.mockResolvedValue(true);
    getOrCreateEngine.mockImplementation(async (onProgress: (r: unknown) => void) => {
      onProgress({ progress: 1, timeElapsed: 1, text: "Listo" });
      return {};
    });
    streamAssistantReply.mockImplementation(async function* () {
      yield "Hola ";
      yield "mundo";
    });

    const user = userEvent.setup();
    render(<AiAssistantWidget />);
    await user.click(screen.getByLabelText("Asistente IA"));

    await waitFor(() => expect(getOrCreateEngine).toHaveBeenCalled());
    const chip = await screen.findByText("¿Cómo creo una cotización?");
    await user.click(chip);

    expect(await screen.findByText("Hola mundo")).toBeInTheDocument();
  });

  it("shows a retry option and does not crash the app when engine initialization fails", async () => {
    isWebGpuSupported.mockResolvedValue(true);
    getOrCreateEngine.mockRejectedValue(new Error("boom"));

    const user = userEvent.setup();
    render(<AiAssistantWidget />);
    await user.click(screen.getByLabelText("Asistente IA"));

    expect(await screen.findByText(/No se pudo inicializar el asistente local/i)).toBeInTheDocument();
    expect(screen.getByText("Reintentar")).toBeInTheDocument();
  });
});
