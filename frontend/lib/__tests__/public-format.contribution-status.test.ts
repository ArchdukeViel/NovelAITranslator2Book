// Feature: public-reader-rework, Property 29: Contribution status is constrained to the allowed set
// **Validates: Requirements 17.9**

import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { mapContributionStatus } from "@/lib/public-format";

const VALID_STATUSES = ["Unchecked", "Checking", "Working", "Failed"] as const;

describe("Property 29: Contribution status is constrained to the allowed set", () => {
  it("for any valid status value, the function returns that value unchanged", () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...VALID_STATUSES),
        (status) => {
          expect(mapContributionStatus(status)).toBe(status);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("for any unknown string value, the function returns 'Unchecked' as the safe default", () => {
    fc.assert(
      fc.property(
        fc.string().filter((s) => !(VALID_STATUSES as readonly string[]).includes(s)),
        (unknownStr) => {
          expect(mapContributionStatus(unknownStr)).toBe("Unchecked");
        }
      ),
      { numRuns: 100 }
    );
  });

  it("for any non-string value, the function returns 'Unchecked'", () => {
    const nonStringArb = fc.oneof(
      fc.integer(),
      fc.double({ noNaN: true, noDefaultInfinity: true }),
      fc.constant(null),
      fc.constant(undefined),
      fc.dictionary(fc.string(), fc.string()),
      fc.array(fc.anything()),
      fc.boolean()
    );

    fc.assert(
      fc.property(nonStringArb, (value) => {
        expect(mapContributionStatus(value)).toBe("Unchecked");
      }),
      { numRuns: 100 }
    );
  });

  it("the return value is always in the allowed set", () => {
    fc.assert(
      fc.property(fc.anything(), (value) => {
        const result = mapContributionStatus(value);
        expect(VALID_STATUSES).toContain(result);
      }),
      { numRuns: 100 }
    );
  });
});
