import { describe, expect, it } from "vitest";
import { parseDeliveryQuantity } from "./deliveryNotes";

describe("parseDeliveryQuantity", () => {
  it("treats blank and 0 as 'not delivering this line' without error", () => {
    expect(parseDeliveryQuantity("", 10)).toEqual({ quantity: null, error: null });
    expect(parseDeliveryQuantity("  ", 10)).toEqual({ quantity: null, error: null });
    expect(parseDeliveryQuantity("0", 10)).toEqual({ quantity: null, error: null });
  });

  it("accepts whole numbers up to the pending amount", () => {
    expect(parseDeliveryQuantity("1", 10)).toEqual({ quantity: 1, error: null });
    expect(parseDeliveryQuantity("10", 10)).toEqual({ quantity: 10, error: null });
  });

  it("reports negatives as an error instead of flipping the sign", () => {
    const result = parseDeliveryQuantity("-5", 10);
    expect(result.quantity).toBeNull();
    expect(result.error).toMatch(/negativa/);
  });

  it("rejects over-delivery, decimals and non-numeric text", () => {
    expect(parseDeliveryQuantity("11", 10).error).toMatch(/pendiente/);
    expect(parseDeliveryQuantity("2.5", 10).error).toMatch(/entero/);
    expect(parseDeliveryQuantity("abc", 10).error).toMatch(/entero/);
    expect(parseDeliveryQuantity("1e3", 10).error).toMatch(/entero/);
  });

  it("allows nothing when there is nothing pending", () => {
    expect(parseDeliveryQuantity("1", 0).error).toMatch(/pendiente/);
  });
});
