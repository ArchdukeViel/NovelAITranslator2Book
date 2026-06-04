import { ApiError, apiErrorInlineMessage } from "@/lib/api";

export function formatAdminError(error: unknown, fallback = "Something went wrong."): string {
  if (error instanceof ApiError) {
    return apiErrorInlineMessage(error);
  }
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  if (typeof error === "string" && error.trim()) {
    return error.trim();
  }
  return fallback;
}
