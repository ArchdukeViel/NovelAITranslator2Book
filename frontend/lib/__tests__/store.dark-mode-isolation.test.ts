/**
 * Property test: Admin dark mode is isolated from the reader theme
 * Feature: admin-ui-rework, Property 3: Admin dark mode is isolated from the reader theme
 *
 * For any initial reader theme and any number of admin darkMode toggles,
 * assert the partitioned reader store theme is unchanged (and vice versa).
 *
 * Validates: Requirements 13.4, 13.5 (Design Property 3)
 */
import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { useAdminUiStore, useReaderUiStore } from "@/lib/store";

// Helper to reset store state for testing
function resetStore() {
  useAdminUiStore.setState({
    darkMode: false,
    sidebarCollapsed: false
  });
  useReaderUiStore.setState({
    theme: "light",
    fontSize: 18,
    width: "comfortable"
  });
}

const themeArb = fc.oneof(
  fc.constant("light" as const),
  fc.constant("dark" as const),
  fc.constant("sepia" as const)
);

const widthArb = fc.oneof(
  fc.constant("compact" as const),
  fc.constant("comfortable" as const),
  fc.constant("wide" as const)
);

describe("Property 3: Admin dark mode is isolated from the reader theme", () => {
  it("reader theme unchanged after admin darkMode toggles", () => {
    fc.assert(
      fc.property(
        themeArb,
        fc.nat({ max: 100 }),
        (initialReaderTheme, toggleCount) => {
          resetStore();
          useReaderUiStore.setState({ theme: initialReaderTheme });

          // Apply toggleCount darkMode toggles on the admin store
          for (let i = 0; i < toggleCount; i++) {
            useAdminUiStore.getState().toggleDarkMode();
          }

          // readerTheme should be unchanged
          expect(useReaderUiStore.getState().theme).toBe(initialReaderTheme);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("setTheme on the reader store does not affect admin darkMode", () => {
    fc.assert(
      fc.property(
        themeArb,
        fc.boolean(),
        (newReaderTheme, initialDarkMode) => {
          resetStore();
          useAdminUiStore.setState({ darkMode: initialDarkMode });

          // Set reader theme
          useReaderUiStore.getState().setTheme(newReaderTheme);

          // darkMode should be unchanged
          expect(useAdminUiStore.getState().darkMode).toBe(initialDarkMode);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("reader settings remain independent from admin settings", () => {
    fc.assert(
      fc.property(
        themeArb,
        fc.boolean(),
        fc.boolean(),
        fc.nat({ max: 50 }),
        (initialReaderTheme, initialDarkMode, initialSidebarCollapsed, darkModeToggles) => {
          resetStore();
          useReaderUiStore.setState({ theme: initialReaderTheme });
          useAdminUiStore.setState({
            darkMode: initialDarkMode,
            sidebarCollapsed: initialSidebarCollapsed
          });

          // Toggle darkMode multiple times
          for (let i = 0; i < darkModeToggles; i++) {
            useAdminUiStore.getState().toggleDarkMode();
          }

          // Verify reader settings are independent
          expect(useReaderUiStore.getState().theme).toBe(initialReaderTheme);
          // Sidebar should also be independent (not affected by darkMode toggles)
          expect(useAdminUiStore.getState().sidebarCollapsed).toBe(initialSidebarCollapsed);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("reader fontSize unaffected by admin darkMode", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 16, max: 22 }),
        fc.nat({ max: 100 }),
        (initialFontSize, toggleCount) => {
          resetStore();
          useReaderUiStore.setState({ fontSize: initialFontSize });

          // Toggle darkMode
          for (let i = 0; i < toggleCount; i++) {
            useAdminUiStore.getState().toggleDarkMode();
          }

          expect(useReaderUiStore.getState().fontSize).toBe(initialFontSize);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("reader width unaffected by admin darkMode", () => {
    fc.assert(
      fc.property(
        widthArb,
        fc.nat({ max: 100 }),
        (initialWidth, toggleCount) => {
          resetStore();
          useReaderUiStore.setState({ width: initialWidth });

          // Toggle darkMode
          for (let i = 0; i < toggleCount; i++) {
            useAdminUiStore.getState().toggleDarkMode();
          }

          expect(useReaderUiStore.getState().width).toBe(initialWidth);
        }
      ),
      { numRuns: 100 }
    );
  });
});
