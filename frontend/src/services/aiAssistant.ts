import { CreateMLCEngine, type InitProgressReport, type MLCEngine } from "@mlc-ai/web-llm";
import { AI_SYSTEM_PROMPT, type AiChatMessage } from "./aiAssistantContent";

/**
 * Este módulo importa "@mlc-ai/web-llm" (varios MB) y se carga con
 * import() dinámico desde AiAssistantWidget, recién cuando el usuario abre
 * el asistente por primera vez — así el resto de la app (login, dashboard,
 * etc) no paga ese costo de bundle si nunca se usa la IA.
 */

/**
 * Modelo elegido tras probar Llama-3.2-1B-Instruct-q4f16_1-MLC contra
 * webllm.prebuiltAppConfig: ~879MB de VRAM, suficientemente chico para correr
 * en el navegador sin trabarlo. Si en la máquina de la demo anda lento,
 * cambiar esta única constante por "SmolLM2-360M-Instruct-q4f16_1-MLC"
 * (~376MB VRAM, mismo prebuiltAppConfig) es el único ajuste necesario.
 */
export const AI_MODEL_ID = "Llama-3.2-1B-Instruct-q4f16_1-MLC";

let enginePromise: Promise<MLCEngine> | null = null;

/**
 * Crea el engine una sola vez (singleton a nivel módulo) y lo reutiliza
 * mientras dure la pestaña. Si falla, limpia la promesa cacheada para que
 * un reintento posterior vuelva a intentar desde cero en vez de quedar
 * pegado a un engine roto.
 */
export function getOrCreateEngine(onProgress: (report: InitProgressReport) => void): Promise<MLCEngine> {
  if (!enginePromise) {
    enginePromise = CreateMLCEngine(AI_MODEL_ID, { initProgressCallback: onProgress }).catch((err) => {
      enginePromise = null;
      throw err;
    });
  }
  return enginePromise;
}

export async function* streamAssistantReply(
  engine: MLCEngine,
  history: AiChatMessage[],
): AsyncGenerator<string> {
  const messages = [
    { role: "system" as const, content: AI_SYSTEM_PROMPT },
    ...history.map((m) => ({ role: m.role, content: m.content })),
  ];
  const stream = await engine.chat.completions.create({
    messages,
    stream: true,
    // Se prioriza precisión/grounding sobre creatividad: para este
    // asistente de ayuda, una respuesta repetitiva es preferible a una
    // "creativa" que invente pantallas o mezcle etapas del flujo.
    temperature: 0.2,
    top_p: 0.9,
    max_tokens: 300,
  });
  for await (const chunk of stream) {
    const delta = chunk.choices[0]?.delta?.content;
    if (delta) yield delta;
  }
}
