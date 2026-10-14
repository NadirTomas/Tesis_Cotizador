import { beforeEach, describe, expect, it } from "vitest";
import { clearNestingDraft, loadNestingDraft, NESTING_DRAFT_KEY, saveNestingDraft, type NestingDraft } from "./nestingDraft";

const draft: NestingDraft = {
  cart: [{ piece_id: 7, quantity: 3 }],
  sheetW: 1250,
  sheetH: 2500,
  margin: 8,
  allowRotation: false,
  result: {
    sheets: [{ placements: [], utilization_pct: 61.5 }],
    total_sheets: 1,
    total_pieces_requested: 3,
    total_pieces_placed: 3,
    overall_utilization_pct: 61.5,
    sheet_width_mm: 1250,
    sheet_height_mm: 2500,
    margin_mm: 8,
  },
  activeSheet: 0,
};

describe("nestingDraft", () => {
  beforeEach(() => sessionStorage.clear());

  it("restores what was saved for the same company", () => {
    saveNestingDraft(1, draft);
    expect(loadNestingDraft(1)).toEqual(draft);
  });

  it("never returns another company's draft", () => {
    saveNestingDraft(1, draft);
    expect(loadNestingDraft(2)).toBeNull();
    expect(loadNestingDraft(null)).toBeNull();
  });

  it("is gone after clearNestingDraft (logout / company switch)", () => {
    saveNestingDraft(1, draft);
    clearNestingDraft();
    expect(loadNestingDraft(1)).toBeNull();
  });

  it("ignores corrupt or malformed stored data instead of throwing", () => {
    sessionStorage.setItem(NESTING_DRAFT_KEY, "{not json");
    expect(loadNestingDraft(1)).toBeNull();
    sessionStorage.setItem(NESTING_DRAFT_KEY, JSON.stringify({ companyId: 1, draft: { cart: "x" } }));
    expect(loadNestingDraft(1)).toBeNull();
    sessionStorage.setItem(
      NESTING_DRAFT_KEY,
      JSON.stringify({ companyId: 1, draft: { ...draft, cart: [{ piece_id: 1, quantity: 0 }] } }),
    );
    expect(loadNestingDraft(1)).toBeNull();
  });
});
