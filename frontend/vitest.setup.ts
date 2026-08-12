/// <reference types="vitest/globals" />
import type { ReactNode } from "react";
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";

// Auto-cleanup React DOM after each test to prevent cross-file DOM pollution
// when using singleFork (all tests share one jsdom environment).
afterEach(() => {
  cleanup();
});

// Fail tests on console.warn and console.error (e.g. React DOM validation errors)
const originalWarn = console.warn;
const originalError = console.error;

beforeAll(() => {
  console.warn = (...args: unknown[]) => {
    originalWarn(...args);
    const msg = args.map(a => (typeof a === "string" ? a : JSON.stringify(a))).join(" ");
    throw new Error(`Unexpected console.warn during test: ${msg}`);
  };
  console.error = (...args: unknown[]) => {
    originalError(...args);
    const msg = args.map(a => (typeof a === "string" ? a : JSON.stringify(a))).join(" ");
    throw new Error(`Unexpected console.error during test: ${msg}`);
  };
});

afterAll(() => {
  console.warn = originalWarn;
  console.error = originalError;
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

// ---------------------------------------------------------------------------
// Mock next/font/google for test environments
// Font functions (Noto_Serif_JP, DM_Sans, DM_Mono) are server-side constructs
// that throw in jsdom. This shim replaces them with noop objects.
// ---------------------------------------------------------------------------

vi.mock("next/font/google", () => {
  const mockFont = () => ({
    className: "mock-font",
    variable: "mock-font-variable",
    style: { fontFamily: "mock" },
  });
  return {
    Noto_Serif_JP: mockFont,
    DM_Sans: mockFont,
    DM_Mono: mockFont,
  };
});

// ---------------------------------------------------------------------------
// Mock next/navigation for test environments
// Components use useRouter, usePathname, useSearchParams from next/navigation,
// which throw "invariant expected app router to be mounted" in jsdom.
// This shim provides noop implementations.
// ---------------------------------------------------------------------------

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    refresh: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    prefetch: vi.fn(),
  }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({}),
}));

// ---------------------------------------------------------------------------
// Mock next/link for test environments
// The real next/link schedules an idle-callback timer (useIntersection) that
// can setState after the current test has finished, tripping the console.error
// guard with an act() warning and failing the whole suite nondeterministically
// (visible once parallel forks shifted the timing on CI). A plain anchor keeps
// href, children, and props intact for navigation-structure assertions.
// ---------------------------------------------------------------------------

vi.mock("next/link", async () => {
  const { forwardRef, createElement } = await vi.importActual<typeof import("react")>("react");
  const Link = forwardRef<HTMLAnchorElement, Record<string, unknown> & { href?: unknown }>(
    (props, ref) => {
      const { href, children, ...rest } = props;
      return createElement(
        "a",
        { ...rest, ref, href: typeof href === "string" ? href : undefined },
        children as ReactNode
      );
    }
  );
  Link.displayName = "NextLinkMock";
  return { default: Link };
});
