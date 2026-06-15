/**
 * Property test: Persisted boolean UI toggle round-trip
 * Feature: admin-ui-rework, Property 2: Persisted boolean UI toggle round-trip
 *
 * For any admin-scoped boolean field and any sequence of toggles,
 * assert the final value equals the parity of the toggle count applied
 * to the initial value and equals the persisted value.
 *
 * Validates: Requirements 3.2, 3.5, 3.6, 13.1, 13.6 (Design Property 2)
 */
import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { useUiStore } from "@/lib/store";

// Helper to reset store state for testing
function resetStore() {
  useUiStore.setState({
    darkMode: false,
    sidebarCollapsed: false
  });
}

describe("Property 2: Persisted boolean UI toggle round-trip", () => {
  it("darkMode toggle parity matches final state", () => {
    fc.assert(
      fc.property(
        fc.boolean(),
        fc.nat({ max: 100 }),
        (initialDarkMode, toggleCount) => {
          resetStore();
          useUiStore.setState({ darkMode: initialDarkMode });

          // Apply toggleCount toggles
          for (let i = 0; i < toggleCount; i++) {
            useUiStore.getState().toggleDarkMode();
          }

          // Final value should be parity of toggle count applied to initial
          const expectedDarkMode = toggleCount % 2 === 0 ? initialDarkMode : !initialDarkMode;
          expect(useUiStore.getState().darkMode).toBe(expectedDarkMode);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("sidebarCollapsed toggle parity matches final state", () => {
    fc.assert(
      fc.property(
        fc.boolean(),
        fc.nat({ max: 100 }),
        (initialSidebarCollapsed, toggleCount) => {
          resetStore();
          useUiStore.setState({ sidebarCollapsed: initialSidebarCollapsed });

          // Apply toggleCount toggles
          for (let i = 0; i < toggleCount; i++) {
            useUiStore.getState().toggleSidebar();
          }

          // Final value should be parity of toggle count applied to initial
          const expectedSidebarCollapsed = toggleCount % 2 === 0 ? initialSidebarCollapsed : !initialSidebarCollapsed;
          expect(useUiStore.getState().sidebarCollapsed).toBe(expectedSidebarCollapsed);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("toggles persist in zustand state", () => {
    fc.assert(
      fc.property(
        fc.boolean(),
        fc.boolean(),
        fc.nat({ max: 50 }),
        fc.nat({ max: 50 }),
        (initialDarkMode, initialSidebarCollapsed, darkModeToggles, sidebarToggles) => {
          resetStore();
          useUiStore.setState({
            darkMode: initialDarkMode,
            sidebarCollapsed: initialSidebarCollapsed
          });

          // Apply darkMode toggles
          for (let i = 0; i < darkModeToggles; i++) {
            useUiStore.getState().toggleDarkMode();
          }

          // Apply sidebar toggles
          for (let i = 0; i < sidebarToggles; i++) {
            useUiStore.getState().toggleSidebar();
          }

          // Verify both persisted values match expected parity
          const expectedDarkMode = darkModeToggles % 2 === 0 ? initialDarkMode : !initialDarkMode;
          const expectedSidebarCollapsed = sidebarToggles % 2 === 0 ? initialSidebarCollapsed : !initialSidebarCollapsed;

          const state = useUiStore.getState();
          expect(state.darkMode).toBe(expectedDarkMode);
          expect(state.sidebarCollapsed).toBe(expectedSidebarCollapsed);
        }
      ),
      { numRuns: 100 }
    );
  });
});