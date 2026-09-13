import { act, cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PublicHeader } from "@/components/public/public-header";

vi.mock("next/navigation", () => ({
  usePathname: () => "/browse-novels",
}));

vi.mock("@/components/public/notification-indicator", () => ({
  NotificationIndicator: () => <div />,
}));
vi.mock("@/components/public/search-entry", () => ({
  SearchEntry: () => <div />,
}));
vi.mock("@/components/public/current-user-indicator", () => ({
  CurrentUserIndicator: () => <div />,
}));
vi.mock("@/components/public/public-brand", () => ({
  PublicBrand: () => <div />,
}));
vi.mock("@/components/public/public-sidebar", () => ({
  PublicSidebar: () => <div />,
}));

describe("PublicHeader scroll throttle (REQ-4, AC-4)", () => {
  let rafCallbacks: FrameRequestCallback[];
  let addListenerSpy: ReturnType<typeof vi.spyOn>;
  let cancelSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    rafCallbacks = [];
    vi.spyOn(window, "requestAnimationFrame").mockImplementation((cb: FrameRequestCallback) => {
      rafCallbacks.push(cb);
      return rafCallbacks.length as unknown as number;
    });
    cancelSpy = vi.spyOn(window, "cancelAnimationFrame").mockImplementation(() => undefined);
    addListenerSpy = vi.spyOn(window, "addEventListener");
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  function flushRaf() {
    const pending = [...rafCallbacks];
    rafCallbacks = [];
    for (const cb of pending) {
      cb(16);
    }
  }

  it("registers scroll listener as passive", () => {
    render(<PublicHeader />);
    const scrollCall = (addListenerSpy.mock.calls as unknown[][]).find((call) => call[0] === "scroll");
    expect(scrollCall).toBeDefined();
    expect(scrollCall?.[2]).toEqual({ passive: true });
  });

  it("throttles rapid scroll events into a single animation frame", () => {
    const { container } = render(<PublicHeader />);
    const header = container.querySelector("header");
    expect(header?.className).toContain("translate-y-0");

    Object.defineProperty(window, "scrollY", { configurable: true, value: 200 });
    act(() => {
      window.dispatchEvent(new Event("scroll"));
      window.dispatchEvent(new Event("scroll"));
      window.dispatchEvent(new Event("scroll"));
    });

    // Multiple synchronous scroll events schedule exactly one frame.
    expect(rafCallbacks).toHaveLength(1);

    act(() => {
      flushRaf();
    });
    expect(header?.className).toContain("-translate-y-full");
  });

  it("cancels pending animation frame on unmount", () => {
    Object.defineProperty(window, "scrollY", { configurable: true, value: 200 });
    const { unmount } = render(<PublicHeader />);
    act(() => {
      window.dispatchEvent(new Event("scroll"));
    });
    expect(rafCallbacks).toHaveLength(1);
    unmount();
    expect(cancelSpy).toHaveBeenCalled();
  });
});
