/**
 * Binary file-header magic-byte validation for cover image uploads
 * (Finding 9.3, REQ-15, AC-15, SEC-2).
 *
 * Threat model: a user (or attacker) selects a file that is *renamed* to a
 * supported extension but actually contains executable HTML, a script, or a
 * polyglot payload. Server-side MIME sniffing and extension validation are
 * not sufficient on their own; the client must verify the leading bytes
 * match the claimed format BEFORE any network transmission.
 *
 * The validator is a pure function: the caller is responsible for reading
 * the header bytes (via FileReader or a polyfill) and for deciding what
 * to do on failure. The CoverUploader component uses this to short-circuit
 * upload attempts at the browser boundary.
 */

export type SupportedImageFormat = "png" | "jpeg" | "webp";

export type ImageValidationResult =
  | { ok: true; kind: SupportedImageFormat }
  | { ok: false; reason: string };

const PNG_SIGNATURE = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a] as const;
const JPEG_SIGNATURE = [0xff, 0xd8, 0xff] as const;
// WEBP: "RIFF" .... "WEBP" (12 bytes total — the WEBP marker sits at offset 8).
const WEBP_RIFF = [0x52, 0x49, 0x46, 0x46] as const;
const WEBP_MARKER = [0x57, 0x45, 0x42, 0x50] as const;

/** Read the leading N bytes of a File as a Uint8Array. */
export function readFileHeader(file: File, length = 16): Promise<Uint8Array> {
  return new Promise((resolve, reject) => {
    if (typeof file === "undefined" || file === null) {
      reject(new Error("No file provided"));
      return;
    }
    if (typeof file.slice !== "function") {
      // Test environments without File.slice — fall back to the legacy API.
      const reader = new FileReader();
      reader.onerror = () => reject(reader.error ?? new Error("FileReader failed"));
      reader.onload = () => {
        const buffer = reader.result as ArrayBuffer | null;
        if (!buffer) {
          reject(new Error("FileReader produced no bytes"));
          return;
        }
        resolve(new Uint8Array(buffer));
      };
      reader.readAsArrayBuffer(file);
      return;
    }
    const slice = file.slice(0, length);
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error("FileReader failed"));
    reader.onload = () => {
      const buffer = reader.result as ArrayBuffer | null;
      if (!buffer) {
        reject(new Error("FileReader produced no bytes"));
        return;
      }
      resolve(new Uint8Array(buffer));
    };
    reader.readAsArrayBuffer(slice);
  });
}

function startsWith(bytes: Uint8Array, signature: readonly number[]): boolean {
  if (bytes.length < signature.length) return false;
  for (let i = 0; i < signature.length; i++) {
    if (bytes[i] !== signature[i]) return false;
  }
  return true;
}

function bytesEqualAt(bytes: Uint8Array, offset: number, expected: readonly number[]): boolean {
  if (bytes.length < offset + expected.length) return false;
  for (let i = 0; i < expected.length; i++) {
    if (bytes[offset + i] !== expected[i]) return false;
  }
  return true;
}

/**
 * Validate that `bytes` (the leading 16 bytes of a candidate file) match
 * the magic-byte signature of one of: PNG, JPEG, or WEBP.
 *
 * Any signature failure produces a typed reason string suitable for
 * displaying in a user-facing error banner. The function never throws.
 */
export function validateImageMagicBytes(bytes: Uint8Array | null | undefined): ImageValidationResult {
  if (!bytes || bytes.length === 0) {
    return { ok: false, reason: "File is empty." };
  }
  if (startsWith(bytes, PNG_SIGNATURE)) {
    return { ok: true, kind: "png" };
  }
  if (startsWith(bytes, JPEG_SIGNATURE)) {
    return { ok: true, kind: "jpeg" };
  }
  if (
    startsWith(bytes, WEBP_RIFF) &&
    bytesEqualAt(bytes, 8, WEBP_MARKER)
  ) {
    return { ok: true, kind: "webp" };
  }
  return {
    ok: false,
    reason:
      "File signature does not match PNG, JPEG, or WEBP. The selected file was rejected before upload.",
  };
}
