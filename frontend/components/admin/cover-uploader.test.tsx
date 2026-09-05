import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CoverUploader } from "@/components/admin/cover-uploader";

// 16-byte header bytes that match each supported format.
const PNG_HEADER = new Uint8Array([
  0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52,
]);
const JPEG_HEADER = new Uint8Array([
  0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0x00, 0x01, 0x01, 0x00, 0x00, 0x01,
]);
const WEBP_HEADER = new Uint8Array([
  0x52, 0x49, 0x46, 0x46, 0x1a, 0x00, 0x00, 0x00, 0x57, 0x45, 0x42, 0x50, 0x56, 0x50, 0x38, 0x4c,
]);
const HTML_HEADER = new Uint8Array([
  0x3c, 0x21, 0x44, 0x4f, 0x43, 0x54, 0x59, 0x50, 0x45, 0x20, 0x68, 0x74, 0x6d, 0x6c, 0x3e, 0x00,
]);

/**
 * jsdom does not implement URL.createObjectURL. The component uses it only
 * for the accepted-state preview, so we provide a minimal stub that returns
 * a stable string. The cover-uploader does not require the URL to be
 * dereferenceable for its security-relevant code paths.
 */
beforeEach(() => {
  if (!("createObjectURL" in URL)) {
    Object.defineProperty(URL, "createObjectURL", {
      value: () => "blob:mock-url",
      writable: true,
    });
  }
  if (!("revokeObjectURL" in URL)) {
    Object.defineProperty(URL, "revokeObjectURL", {
      value: () => undefined,
      writable: true,
    });
  }
});

function buildFileWithHeader(name: string, header: Uint8Array): File {
  // FileReader in jsdom returns whatever ArrayBuffer is passed; we use a
  // minimally populated File and rely on the mock FileReader below to
  // surface the requested header bytes.
  return new File([new Uint8Array(header)], name, { type: "image/*" });
}

let queuedResults: ArrayBuffer[] = [];

class MockFileReader {
  public onload: (() => void) | null = null;
  public onerror: (() => void) | null = null;
  private result: ArrayBuffer | null = null;
  readAsArrayBuffer(_blob: Blob): void {
    this.result = queuedResults.shift() ?? new ArrayBuffer(0);
    queueMicrotask(() => this.onload?.());
  }
}

beforeEach(() => {
  queuedResults = [];
  vi.stubGlobal("FileReader", MockFileReader);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function selectFile(input: HTMLInputElement, file: File, headerBytes: ArrayBuffer) {
  queuedResults.push(headerBytes);
  Object.defineProperty(input, "files", {
    value: [file],
    writable: true,
    configurable: true,
  });
  fireEvent.change(input);
}

describe("CoverUploader (Finding 9.3, REQ-15, AC-15, SEC-2)", () => {
  it("renders the file input with PNG/JPEG/WEBP accept attributes", () => {
    render(<CoverUploader />);
    const input = screen.getByTestId("cover-uploader-input") as HTMLInputElement;
    expect(input.type).toBe("file");
    expect(input.accept).toBe("image/png,image/jpeg,image/webp");
  });

  it("calls onValidatedFile and shows preview for a valid PNG", async () => {
    const onValidatedFile = vi.fn();
    render(<CoverUploader onValidatedFile={onValidatedFile} />);
    const input = screen.getByTestId("cover-uploader-input") as HTMLInputElement;
    const file = buildFileWithHeader("cover.png", PNG_HEADER);
    selectFile(input, file, PNG_HEADER.buffer);

    await waitFor(() => {
      expect(onValidatedFile).toHaveBeenCalledWith(file, "png");
    });
    expect(screen.getByTestId("cover-uploader-preview")).toBeInTheDocument();
    expect(screen.getByText(/png signature verified/i)).toBeInTheDocument();
  });

  it("accepts a valid JPEG", async () => {
    const onValidatedFile = vi.fn();
    render(<CoverUploader onValidatedFile={onValidatedFile} />);
    const input = screen.getByTestId("cover-uploader-input") as HTMLInputElement;
    const file = buildFileWithHeader("cover.jpg", JPEG_HEADER);
    selectFile(input, file, JPEG_HEADER.buffer);

    await waitFor(() => {
      expect(onValidatedFile).toHaveBeenCalledWith(file, "jpeg");
    });
  });

  it("accepts a valid WEBP", async () => {
    const onValidatedFile = vi.fn();
    render(<CoverUploader onValidatedFile={onValidatedFile} />);
    const input = screen.getByTestId("cover-uploader-input") as HTMLInputElement;
    const file = buildFileWithHeader("cover.webp", WEBP_HEADER);
    selectFile(input, file, WEBP_HEADER.buffer);

    await waitFor(() => {
      expect(onValidatedFile).toHaveBeenCalledWith(file, "webp");
    });
  });

  it("rejects a file disguised as PNG with HTML content and does NOT call onValidatedFile", async () => {
    const onValidatedFile = vi.fn();
    render(<CoverUploader onValidatedFile={onValidatedFile} />);
    const input = screen.getByTestId("cover-uploader-input") as HTMLInputElement;
    const file = buildFileWithHeader("disguised.png", HTML_HEADER);
    selectFile(input, file, HTML_HEADER.buffer);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    expect(onValidatedFile).not.toHaveBeenCalled();
    expect(screen.getByText(/does not match png, jpeg, or webp/i)).toBeInTheDocument();
  });

  it("does not make any network calls when validation fails", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(() => {
      throw new Error("CoverUploader must not call fetch during validation");
    });
    const onValidatedFile = vi.fn();
    render(<CoverUploader onValidatedFile={onValidatedFile} />);
    const input = screen.getByTestId("cover-uploader-input") as HTMLInputElement;
    const file = buildFileWithHeader("attack.exe", new Uint8Array([0x4d, 0x5a, 0x90, 0x00]));
    selectFile(input, file, new Uint8Array([0x4d, 0x5a, 0x90, 0x00, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]).buffer);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(onValidatedFile).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  it("can be cleared after a successful validation", async () => {
    const onValidatedFile = vi.fn();
    render(<CoverUploader onValidatedFile={onValidatedFile} />);
    const input = screen.getByTestId("cover-uploader-input") as HTMLInputElement;
    const file = buildFileWithHeader("cover.png", PNG_HEADER);
    selectFile(input, file, PNG_HEADER.buffer);

    await waitFor(() => {
      expect(onValidatedFile).toHaveBeenCalled();
    });
    fireEvent.click(screen.getByRole("button", { name: /clear selected file/i }));
    expect(screen.queryByTestId("cover-uploader-preview")).not.toBeInTheDocument();
  });
});
