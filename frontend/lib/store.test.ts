import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  ADMIN_UI_STORAGE_KEY,
  LEGACY_UI_STORAGE_KEY,
  READER_UI_STORAGE_KEY,
  useAdminUiStore,
  useReaderUiStore,
} from "@/lib/store";

function resetStores() {
  useReaderUiStore.setState({ theme: "light", fontSize: 18, width: "comfortable" });
  useAdminUiStore.setState({ darkMode: false, sidebarCollapsed: false });
}

beforeEach(() => {
  resetStores();
});

describe("Store partitioning (REQ-8, AC-8, NFR-5)", () => {
  it("exposes partitioned reader and admin stores with no monolithic useUiStore", async () => {
    const storeModule = await import("@/lib/store");
    expect("useUiStore" in storeModule).toBe(false);
    expect(typeof useReaderUiStore).toBe("function");
    expect(typeof useAdminUiStore).toBe("function");
  });

  it("uses isolated dokushodo storage namespaces", () => {
    expect(READER_UI_STORAGE_KEY).toBe("dokushodo-reader-ui");
    expect(ADMIN_UI_STORAGE_KEY).toBe("dokushodo-admin-ui");
    expect(LEGACY_UI_STORAGE_KEY).toBe("novelai-ui");
    expect(READER_UI_STORAGE_KEY).not.toBe(ADMIN_UI_STORAGE_KEY);
  });

  it("purges the deprecated novelai-ui key with zero legacy hydration", async () => {
    window.localStorage.setItem(
      LEGACY_UI_STORAGE_KEY,
      JSON.stringify({ darkMode: true, theme: "dark" }),
    );
    vi.resetModules();
    await import("@/lib/store");
    expect(window.localStorage.getItem(LEGACY_UI_STORAGE_KEY)).toBeNull();
  });

  it("reader actions never touch admin state and vice versa", () => {
    useReaderUiStore.getState().setTheme("sepia");
    useReaderUiStore.getState().setFontSize(22);
    useReaderUiStore.getState().setWidth("wide");
    expect(useAdminUiStore.getState().darkMode).toBe(false);
    expect(useAdminUiStore.getState().sidebarCollapsed).toBe(false);

    useAdminUiStore.getState().toggleDarkMode();
    useAdminUiStore.getState().toggleSidebar();
    expect(useReaderUiStore.getState().theme).toBe("sepia");
    expect(useReaderUiStore.getState().fontSize).toBe(22);
    expect(useReaderUiStore.getState().width).toBe("wide");
  });

  it("clamps reader font size to supported choices", () => {
    useReaderUiStore.getState().setFontSize(100);
    expect([16, 18, 20, 22]).toContain(useReaderUiStore.getState().fontSize);
  });
});
