import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ReaderControls } from "@/components/public/reader-controls";

const mocks = vi.hoisted(() => ({
  setFontSize: vi.fn(),
  setTheme: vi.fn(),
  setWidth: vi.fn(),
  isAuthenticated: false,
}));

vi.mock("@/hooks/public", () => ({ usePublicAuth: () => ({ isAuthenticated: mocks.isAuthenticated }) }));
vi.mock("@/lib/store", () => ({
  useReaderUiStore: () => ({ theme: "sepia", fontSize: 18, width: "comfortable", setFontSize: mocks.setFontSize, setTheme: mocks.setTheme, setWidth: mocks.setWidth }),
}));

beforeEach(() => { vi.clearAllMocks(); mocks.isAuthenticated = false; });
afterEach(cleanup);

function open() {
  render(<ReaderControls />);
  fireEvent.click(screen.getByRole("button", { name: "Reading settings" }));
}

describe("ReaderControls Aa sheet", () => {
  it("opens a labeled dialog and closes with Escape", () => {
    open();
    expect(screen.getByRole("dialog", { name: "Reading settings" })).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("opens from the documented period shortcut", () => {
    render(<ReaderControls />);
    fireEvent.keyDown(window, { key: "." });
    expect(screen.getByRole("dialog", { name: "Reading settings" })).toBeInTheDocument();
  });

  it("sets exact font, width, and theme choices", () => {
    open();
    fireEvent.click(screen.getByRole("button", { name: "22px" }));
    fireEvent.click(screen.getByRole("button", { name: /Wide 800px/ }));
    fireEvent.click(screen.getByRole("button", { name: "dark" }));
    expect(mocks.setFontSize).toHaveBeenCalledWith(22);
    expect(mocks.setWidth).toHaveBeenCalledWith("wide");
    expect(mocks.setTheme).toHaveBeenCalledWith("dark");
  });

  it("resets size and width while preserving saved theme", () => {
    open();
    fireEvent.click(screen.getByRole("button", { name: /Reset size and width/ }));
    expect(mocks.setFontSize).toHaveBeenCalledWith(18);
    expect(mocks.setWidth).toHaveBeenCalledWith("comfortable");
    expect(mocks.setTheme).not.toHaveBeenCalled();
  });

  it("explains guest position is local-only", () => {
    open();
    expect(screen.getByText(/stays on this device/i)).toBeInTheDocument();
  });

  it("ignores the period shortcut when focus is inside editable controls", () => {
    render(<ReaderControls />);
    const input = document.createElement("input");
    const textarea = document.createElement("textarea");
    const select = document.createElement("select");
    const editable = document.createElement("div");
    editable.setAttribute("contenteditable", "true");
    const editableChild = document.createElement("span");
    editable.appendChild(editableChild);
    document.body.append(input, textarea, select, editable);
    try {
      for (const target of [input, textarea, select, editable, editableChild]) {
        fireEvent.keyDown(target, { key: "." });
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      }
    } finally {
      input.remove();
      textarea.remove();
      select.remove();
      editable.remove();
    }
  });
});
