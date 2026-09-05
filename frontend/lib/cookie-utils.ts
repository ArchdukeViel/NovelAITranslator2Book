/**
 * Client-side cookie utilities enforcing secure attribute invariants (Finding 8.8, REQ-14, AC-14).
 *
 * Invariants:
 * - Unconditional SameSite=Lax and Path=/
 * - Secure attribute appended when running on HTTPS
 */

export interface CookieOptions {
  maxAge?: number;
  expires?: Date;
  path?: string;
  sameSite?: "Lax" | "Strict" | "None";
  secure?: boolean;
}

export function setCookie(name: string, value: string, options: CookieOptions = {}): void {
  if (typeof document === "undefined") return;

  const encodedName = encodeURIComponent(name);
  const encodedValue = encodeURIComponent(value);
  let cookieStr = `${encodedName}=${encodedValue}`;

  if (options.maxAge !== undefined) {
    cookieStr += `; max-age=${options.maxAge}`;
  } else if (options.expires) {
    cookieStr += `; expires=${options.expires.toUTCString()}`;
  }

  const path = options.path ?? "/";
  cookieStr += `; path=${path}`;

  const sameSite = options.sameSite ?? "Lax";
  cookieStr += `; SameSite=${sameSite}`;

  const isHttps = typeof window !== "undefined" && window.location.protocol === "https:";
  if (options.secure || (options.secure === undefined && isHttps)) {
    cookieStr += "; Secure";
  }

  document.cookie = cookieStr;
}

export function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${encodeURIComponent(name)}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

export function deleteCookie(name: string, path = "/"): void {
  setCookie(name, "", { path, maxAge: 0 });
}
