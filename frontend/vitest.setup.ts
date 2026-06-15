/// <reference types="vitest/globals" />
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";

// Auto-cleanup React DOM after each test to prevent cross-file DOM pollution
// when using singleFork (all tests share one jsdom environment).
afterEach(() => {
  cleanup();
});

/**
 * In-memory Storage shim for localStorage/sessionStorage in tests.
 * Used by storage-policy property tests to verify no session tokens
 * or credentials leak into browser storage.
 */
class InMemoryStorage implements Storage {
  private store = new Map<string, string>();

  get length(): number {
    return this.store.size;
  }

  clear(): void {
    this.store.clear();
  }

  getItem(key: string): string | null {
    return this.store.get(key) ?? null;
  }

  key(index: number): string | null {
    const keys = [...this.store.keys()];
    return keys[index] ?? null;
  }

  removeItem(key: string): void {
    this.store.delete(key);
  }

  setItem(key: string, value: string): void {
    this.store.set(key, value);
  }
}

// Replace global storage with in-memory shims so tests run in jsdom
// without persisting state between runs.
Object.defineProperty(globalThis, "localStorage", {
  value: new InMemoryStorage(),
  writable: true,
});

Object.defineProperty(globalThis, "sessionStorage", {
  value: new InMemoryStorage(),
  writable: true,
});

// Reset storage between tests
beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});