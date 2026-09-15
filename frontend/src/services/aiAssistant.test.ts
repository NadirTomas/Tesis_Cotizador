import { describe, expect, it } from "vitest";
import { AI_GENERATION_CONFIG, AI_MODEL_ID, buildChatMessages } from "./aiAssistant";
import { AI_SYSTEM_PROMPT, type AiChatMessage } from "./aiAssistantContent";

describe("aiAssistant integration", () => {
  it("includes the full CotizaLaser system prompt as the single, first message", () => {
    const messages = buildChatMessages([]);
    expect(messages).toHaveLength(1);
    expect(messages[0]).toEqual({ role: "system", content: AI_SYSTEM_PROMPT });
  });

  it("never duplicates or sends an empty system message, regardless of history length", () => {
    const history: AiChatMessage[] = [
      { role: "user", content: "¿Cómo creo una cotización?" },
      { role: "assistant", content: "..." },
      { role: "user", content: "¿Y el stock?" },
    ];
    const messages = buildChatMessages(history);
    const systemMessages = messages.filter((m) => m.role === "system");
    expect(systemMessages).toHaveLength(1);
    expect(systemMessages[0].content.length).toBeGreaterThan(0);
  });

  it("sends the current user question as the last message the engine sees, after the full history", () => {
    const history: AiChatMessage[] = [
      { role: "user", content: "¿Qué es una reserva?" },
      { role: "assistant", content: "Es apartar una chapa para una cotización aceptada." },
      { role: "user", content: "¿Cómo creo una cotización?" },
    ];
    const messages = buildChatMessages(history);
    // system + 3 mensajes de historial, sin truncar nada
    expect(messages).toHaveLength(4);
    expect(messages[messages.length - 1]).toEqual({
      role: "user",
      content: "¿Cómo creo una cotización?",
    });
  });

  it("contains the three required few-shot examples", () => {
    expect(AI_SYSTEM_PROMPT).toContain("¿Cuándo se genera un remanente?");
    expect(AI_SYSTEM_PROMPT).toContain(
      "El remanente se genera al confirmar el corte, si después del corte queda material reutilizable."
    );
    expect(AI_SYSTEM_PROMPT).toContain("¿Puedo reservar stock antes de aceptar una cotización?");
    expect(AI_SYSTEM_PROMPT).toContain(
      "No. En CotizaLaser la cotización debe estar ACCEPTED antes de poder reservar stock."
    );
    expect(AI_SYSTEM_PROMPT).toContain("¿Cómo creo una cotización?");
    expect(AI_SYSTEM_PROMPT).toContain("Seleccionás o creás el cliente");
  });

  it("states the reservation/accepted-status rule explicitly (grounding for the flow order)", () => {
    expect(AI_SYSTEM_PROMPT).toMatch(/RESERVED.*cotizaci[oó]n ACEPTADA/i);
  });

  it("uses the configured 3B model, not 1B/7B/8B", () => {
    expect(AI_MODEL_ID).toBe("Llama-3.2-3B-Instruct-q4f16_1-MLC");
  });

  it("uses precision-oriented generation parameters", () => {
    expect(AI_GENERATION_CONFIG).toEqual({
      temperature: 0.15,
      top_p: 0.9,
      max_tokens: 300,
    });
  });
});
