/**
 * Property test: Admin dark mode is isolated from the reader theme
 * Feature: admin-ui-rework, Property 3: Admin dark mode is isolated from the reader theme
 *
 * For any initial readerTheme and any number of darkMode toggles,
 * assert readerTheme is unchanged.
 *
 * Validates: Requirements 13.4, 13.5 (Design Property 3)
 */
import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { useUiStore } from "@/lib/store";

// Helper to reset store state for testing
function resetStore() {
  useUiStore.setState({
    darkMode: false,
    readerTheme: "light"
  });
}

describe("Property 3: Admin dark mode is isolated from the reader theme", () => {
  it("readerTheme unchanged after darkMode toggles", () => {
    fc.assert(
      fc.property(
        fc.oneof(
          fc.constant("light" as const),
          fc.constant("dark" as const),
          fc.constant("sepia" as const)
        ),
        fc.nat({ max: 100 }),
        (initialReaderTheme, toggleCount) => {
          resetStore();
          useUiStore.setState({ readerTheme: initialReaderTheme });

          // Apply toggleCount darkMode toggles
          for (let i = 0; i < toggleCount; i++) {
            useUiStore.getState().toggleDarkMode();
          }

          // readerTheme should be unchanged
          expect(useUiStore.getState().readerTheme).toBe(initialReaderTheme);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("setReaderTheme does not affect darkMode", () => {
    fc.assert(
      fc.property(
        fc.oneof(
          fc.constant("light" as const),
          fc.constant("dark" as const),
          fc.constant("sepia" as const)
        ),
        fc.boolean(),
        (newReaderTheme, initialDarkMode) => {
          resetStore();
          useUiStore.setState({ darkMode: initialDarkMode });

          // Set reader theme
          useUiStore.getState().setReaderTheme(newReaderTheme);

          // darkMode should be unchanged
          expect(useUiStore.getState().darkMode).toBe(initialDarkMode);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("reader settings remain independent from admin settings", () => {
    fc.assert(
      fc.property(
        fc.oneof(
          fc.constant("light" as const),
          fc.constant("dark" as const),
          fc.constant("sepia" as const)
        ),
        fc.boolean(),
        fc.boolean(),
        fc.nat({ max: 50 }),
        (initialReaderTheme, initialDarkMode, initialSidebarCollapsed, darkModeToggles) => {
          resetStore();
          useUiStore.setState({
            readerTheme: initialReaderTheme,
            darkMode: initialDarkMode,
            sidebarCollapsed: initialSidebarCollapsed
          });

          // Toggle darkMode multiple times
          for (let i = 0; i < darkModeToggles; i++) {
            useUiStore.getState().toggleDarkMode();
          }

          // Verify reader settings are independent
          const state = useUiStore.getState();
          expect(state.readerTheme).toBe(initialReaderTheme);
          // Sidebar should also be independent (not affected by darkMode toggles)
          expect(state.sidebarCollapsed).toBe(initialSidebarCollapsed);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("readerFontSize unaffected by darkMode", () => {
    fc.assert(
      fc.property(
        fc.nat({ max: 9 }).map((n) => n + 15), // 15-24 range
        fc.nat({ max: 100 }),
        (initialFontSize, toggleCount) => {
          resetStore();
          useUiStore.setState({ readerFontSize: initialFontSize });

          // Toggle darkMode
          for (let i = 0; i < toggleCount; i++) {
            useUiStore.getState().toggleDarkMode();
          }

          expect(useUiStore.getState().readerFontSize).toBe(initialFontSize);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("readerWidth unaffected by darkMode", () => {
    fc.assert(
      fc.property(
        fc.oneof(
          fc.constant("compact" as const),
          fc.constant("comfortable" as const),
          fc.constant("wide" as const)
        ),
        fc.nat({ max: 100 }),
        (initialReaderWidth, toggleCount) => {
          resetStore();
          useUiStore.setState({ readerWidth: initialReaderWidth });

          // Toggle darkMode
          for (let i = 0; i < toggleCount; i++) {
            useUiStore.getState().toggleDarkMode();
          }

          expect(useUiStore.getState().readerWidth).toBe(initialReaderWidth);
        }
      ),
      { numRuns: 100 }
    );
  });
});