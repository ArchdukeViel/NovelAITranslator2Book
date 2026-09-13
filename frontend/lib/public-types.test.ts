import { describe, expect, it } from "vitest";

import { toPublicationStatus } from "./public-types";

describe("toPublicationStatus (REQ-16, AC-16)", () => {
  it("accepts canonical backend statuses case-insensitively", () => {
    expect(toPublicationStatus("ongoing")).toBe("ongoing");
    expect(toPublicationStatus("Ongoing")).toBe("ongoing");
    expect(toPublicationStatus("Completed")).toBe("completed");
    expect(toPublicationStatus("Hiatus")).toBe("hiatus");
    expect(toPublicationStatus("unknown")).toBe("unknown");
  });

  it("preserves the legacy Dropped filter as unknown (backend normalize behavior)", () => {
    expect(toPublicationStatus("Dropped")).toBe("unknown");
  });

  it("rejects empty and unrecognized values", () => {
    expect(toPublicationStatus(null)).toBeUndefined();
    expect(toPublicationStatus(undefined)).toBeUndefined();
    expect(toPublicationStatus("")).toBeUndefined();
    expect(toPublicationStatus("  ")).toBeUndefined();
    expect(toPublicationStatus("published-ish")).toBeUndefined();
  });
});
