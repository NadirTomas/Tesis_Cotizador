import { describe, expect, it } from "vitest";
import { CLIENT_NAME_NUMERIC_ERROR, getClientNameError } from "./clientName";

describe("getClientNameError", () => {
  it("rejects purely numeric names", () => {
    for (const name of ["123456", " 42 ", "12-34", "#123"]) {
      expect(getClientNameError(name)).toBe(CLIENT_NAME_NUMERIC_ERROR);
    }
  });

  it("accepts valid names that include numbers", () => {
    for (const name of ["Metalúrgica 24", "Taller 3D", "Empresa ABC S.R.L.", "Juan Pérez"]) {
      expect(getClientNameError(name)).toBeNull();
    }
  });

  it("does not flag empty input (the required check handles it)", () => {
    expect(getClientNameError("   ")).toBeNull();
  });
});
