import { CreateMLCEngine, type InitProgressReport, type MLCEngine } from "@mlc-ai/web-llm";
import { AI_SYSTEM_PROMPT, type AiChatMessage } from "./aiAssistantContent";

/**
 * Este módulo importa "@mlc-ai/web-llm" (varios MB) y se carga con
 * import() dinámico desde AiAssistantWidget, recién cuando el usuario abre
 * el asistente por primera vez — así el resto de la app (login, dashboard,
 * etc) no paga ese costo de bundle si nunca se usa la IA.
 */

/**
 * Llama-3.2-1B-Instruct funcionaba (WebGPU real, carga y genera) pero
 * respondía mal preguntas básicas de CotizaLaser aunque estaban explicadas
 * en el system prompt (mezclaba etapas del flujo, ubicaba mal cuándo se
 * genera un remanente). La integración del prompt se verificó correcta
 * (sin duplicación, sin truncamiento — ver aiAssistant.ts historial de
 * commits), así que la causa era capacidad del modelo de 1B, no un bug.
 * Se sube a Llama-3.2-3B-Instruct-q4f16_1-MLC (~2.26GB VRAM, confirmado
 * presente en esta versión de webllm.prebuiltAppConfig), siguiendo debajo
 * de 7B/8B. Si en la máquina de la demo anda lento, volver a
 * "Llama-3.2-1B-Instruct-q4f16_1-MLC" (~879MB) es el único ajuste
 * necesario.
 */
export const AI_MODEL_ID = "Llama-3.2-3B-Instruct-q4f16_1-MLC";

/**
 * Se prioriza precisión/grounding sobre creatividad: para este asistente de
 * ayuda, una respuesta repetitiva es preferible a una "creativa" que
 * invente pantallas o mezcle etapas del flujo.
 */
export const AI_GENERATION_CONFIG = {
  temperature: 0.15,
  top_p: 0.9,
  max_tokens: 300,
} as const;

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

/**
 * Arma el array de mensajes que se le manda al engine: el system prompt
 * completo de CotizaLaser SIEMPRE primero y único (WebLLM exige que el
 * único mensaje "system" esté en la posición 0, y lo usa para reemplazar
 * el system prompt por defecto del modelo, no para sumarse a él), seguido
 * de todo el historial tal cual — la pregunta actual del usuario ya viene
 * incluida como el último elemento de `history` (ver AiAssistantWidget,
 * que arma `nextHistory` con el mensaje nuevo antes de llamar acá).
 * Separado en su propia función para poder testear la construcción del
 * prompt sin necesitar un engine real.
 */
export function buildChatMessages(history: AiChatMessage[]) {
  return [
    { role: "system" as const, content: AI_SYSTEM_PROMPT },
    ...history.map((m) => ({ role: m.role, content: m.content })),
  ];
}

export async function* streamAssistantReply(
  engine: MLCEngine,
  history: AiChatMessage[],
): AsyncGenerator<string> {
  const stream = await engine.chat.completions.create({
    messages: buildChatMessages(history),
    stream: true,
    ...AI_GENERATION_CONFIG,
  });
  for await (const chunk of stream) {
    const delta = chunk.choices[0]?.delta?.content;
    if (delta) yield delta;
  }
}
