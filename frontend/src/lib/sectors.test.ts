import { describe, expect, it } from "vitest";
import { SECTORS, SECTOR_COLOR, SECTOR_LABEL } from "./sectors";

describe("sectors", () => {
  it("includes Consultoria with a label and a color", () => {
    expect(SECTORS).toContain("consultoria");
    expect(SECTOR_LABEL.consultoria).toBe("Consultoria");
    expect(SECTOR_COLOR.consultoria).toBe("var(--sector-consultoria)");
  });

  it("gives every sector a label and a color", () => {
    for (const sector of SECTORS) {
      expect(SECTOR_LABEL[sector]).toBeTruthy();
      expect(SECTOR_COLOR[sector]).toMatch(/^var\(--sector-/);
    }
  });
});
