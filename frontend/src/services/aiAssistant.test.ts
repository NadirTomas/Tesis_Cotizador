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

  it("describes the machine cost as hours MULTIPLIED by the hourly rate, never divided by it", () => {
    // Regresión puntual: el modelo llegó a decir "tiempo de corte + setup
    // dividido por la tarifa horaria", que invierte la fórmula real
    // (quotation_calculator.py: cost_machine_total = tiempo_total_horas *
    // machine_cost_per_hour_ars). El prompt debe dejar la multiplicación
    // explícita y no debe contener ninguna frase de "dividido" pegada a la
    // tarifa/costo por hora.
    expect(AI_SYSTEM_PROMPT).toMatch(/tiempo total en horas MULTIPLICADO por el costo por hora/i);
    expect(AI_SYSTEM_PROMPT).toMatch(/se MULTIPLICA por la tarifa horaria/i);
    expect(AI_SYSTEM_PROMPT).not.toMatch(/dividid[oa]\s+(por\s+)?(la\s+)?(tarifa horaria|costo por hora)/i);
  });

  it("includes the internal technical details block with the 10 verified facts", () => {
    expect(AI_SYSTEM_PROMPT).toContain("DETALLES TÉCNICOS INTERNOS VERIFICADOS");
    expect(AI_SYSTEM_PROMPT).toContain(
      "Descartar una chapa (DISCARDED) solo puede pasar desde AVAILABLE."
    );
    expect(AI_SYSTEM_PROMPT).toMatch(/actualizaci[oó]n condicional.*evitar carreras/i);
    expect(AI_SYSTEM_PROMPT).toContain(
      "Cancelar una cotización con reservas activas libera esas reservas automáticamente."
    );
    expect(AI_SYSTEM_PROMPT).toMatch(/Liberar una reserva NO significa descartar la chapa/);
    expect(AI_SYSTEM_PROMPT).toMatch(/DISCARDED significa que el material físico se dio de baja/);
    expect(AI_SYSTEM_PROMPT).toMatch(/tiempo de corte escala con la cantidad/i);
    expect(AI_SYSTEM_PROMPT).toMatch(/setup.*NO escala.*una sola vez por lote/i);
    expect(AI_SYSTEM_PROMPT).toContain(
      "machine_cost = ((( length_cut_mm × quantity ) / cut_speed_mm_min ) + setup_time_min ) / 60 × machine_cost_per_hour_ars"
    );
    expect(AI_SYSTEM_PROMPT).toMatch(/mano de obra es un porcentaje configurable del costo de m[aá]quina/i);
    expect(AI_SYSTEM_PROMPT).toMatch(/JWT emitido antes de desactivar a un usuario/i);
    expect(AI_SYSTEM_PROMPT).toMatch(/vuelve a consultar si el usuario sigue activo en la base de datos/i);
    expect(AI_SYSTEM_PROMPT).toMatch(/CompanyMember inactivo/);
    expect(AI_SYSTEM_PROMPT).toMatch(/no invalida necesariamente su acceso a otras empresas/i);
  });

  it("makes explicit that machine cost scales with quantity via cut time, unlike setup", () => {
    // Regresión real detectada en prueba funcional: preguntado "¿qué
    // escala con la cantidad?", el modelo de 3B respondió que el costo de
    // máquina "permanece constante", contradiciendo la propia formula
    // (cut_time_total_min = length_cut_mm * quantity / cut_speed_mm_min).
    // Se refuerza el hecho junto a la fórmula y se agrega un 4to few-shot
    // con exactamente este tipo de pregunta.
    expect(AI_SYSTEM_PROMPT).toMatch(/el tiempo de corte SÍ escala con la cantidad/i);
    expect(AI_SYSTEM_PROMPT).toMatch(/EL COSTO DE MÁQUINA SÍ AUMENTA AL AUMENTAR LA CANTIDAD/i);
    expect(AI_SYSTEM_PROMPT).toMatch(/El costo de máquina NUNCA permanece constante al cambiar la cantidad/i);
    expect(AI_SYSTEM_PROMPT).toContain(
      "Si aumento la cantidad de una pieza de 1 a 5, ¿qué partes del costo escalan con la cantidad y cuáles no?"
    );
    expect(AI_SYSTEM_PROMPT).toContain(
      "El costo de máquina también aumenta, porque el tiempo de corte escala con la cantidad"
    );
  });

  it("makes explicit that total material cost DOES scale linearly with quantity", () => {
    // Segunda regresión encontrada en la misma prueba funcional, efecto
    // colateral del fix anterior: al reforzar que el setup NO escala, el
    // modelo empezó a responder que el costo de material "no escala con la
    // cantidad" -- describía solo el costo UNITARIO (que en efecto no
    // cambia) sin mencionar que el total se multiplica por quantity
    // (cost_material_total = costo_material_unitario * quantity en
    // quotation_calculator.py). Se distingue unitario vs. total
    // explícitamente en el prompt.
    expect(AI_SYSTEM_PROMPT).toMatch(/costo de material UNITARIO/);
    expect(AI_SYSTEM_PROMPT).toMatch(/costo de material TOTAL del ítem = ese costo unitario MULTIPLICADO por la cantidad/);
    expect(AI_SYSTEM_PROMPT).toMatch(/el costo de material SÍ escala linealmente con la cantidad/i);
  });

  it("uses the configured 3B model, not 1B/7B/8B", () => {
    expect(AI_MODEL_ID).toBe("Llama-3.2-3B-Instruct-q4f16_1-MLC");
  });

  it("uses precision-oriented generation parameters", () => {
    // max_tokens subido de 300 a 450: una respuesta tecnica real (escalado
    // de costos con quantity) se cortaba a mitad de frase antes de llegar
    // al resumen final.
    expect(AI_GENERATION_CONFIG).toEqual({
      temperature: 0.15,
      top_p: 0.9,
      max_tokens: 450,
    });
  });

  it("states plainly why machine cost isn't strictly proportional to quantity", () => {
    expect(AI_SYSTEM_PROMPT).toContain(
      "Cuando aumenta quantity, el costo de máquina aumenta porque aumenta el tiempo total de corte. No aumenta de forma estrictamente proporcional, porque setup_time_min se cobra una sola vez por lote/trabajo."
    );
  });
});
