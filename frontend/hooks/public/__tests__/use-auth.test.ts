import { describe, it, expect, vi, beforeEach } from "vitest";
import { waitFor, act } from "@testing-library/react";
import {
  useAuthMe,
  usePublicAuth,
  useLogout,
  usePasswordLogin,
  useRegister,
} from "@/hooks/public/use-auth";
import { authApi } from "@/lib/public-api";
import { renderHookWithProviders } from "@/lib/test-utils";
import type { AuthUser } from "@/lib/public-types";

describe("useAuth hooks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockUser: AuthUser = {
    user_id: 42,
    email: "reader@example.test",
    role: "user",
    is_authenticated: true,
    is_owner: false,
  };

  it("useAuthMe fetches authenticated user info", async () => {
    vi.spyOn(authApi, "me").mockResolvedValueOnce(mockUser);

    const { result } = renderHookWithProviders(() => useAuthMe());

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(mockUser);
  });

  it("usePublicAuth computes convenience auth flags", async () => {
    vi.spyOn(authApi, "me").mockResolvedValueOnce(mockUser);

    const { result } = renderHookWithProviders(() => usePublicAuth());

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true);
    });

    expect(result.current.isPublicUser).toBe(true);
    expect(result.current.isOwner).toBe(false);
    expect(result.current.authState?.status).toBe("authenticated");
  });

  it("useLogout invalidates auth query and removes user reading/engagement cache", async () => {
    vi.spyOn(authApi, "logout").mockResolvedValueOnce(undefined);

    const { result, queryClient } = renderHookWithProviders(() => useLogout());
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const removeSpy = vi.spyOn(queryClient, "removeQueries");

    await act(async () => {
      await result.current.mutateAsync();
    });

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["auth", "me"] });
    expect(removeSpy).toHaveBeenCalledWith({ queryKey: ["user-reading"] });
    expect(removeSpy).toHaveBeenCalledWith({ queryKey: ["user-engagement"] });
    expect(removeSpy).toHaveBeenCalledWith({
      queryKey: ["user-notifications"],
    });
  });

  it("usePasswordLogin calls passwordLogin and invalidates auth cache", async () => {
    vi.spyOn(authApi, "passwordLogin").mockResolvedValueOnce(mockUser);

    const { result, queryClient } = renderHookWithProviders(() =>
      usePasswordLogin(),
    );
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    await act(async () => {
      await result.current.mutateAsync({
        email: "reader@example.test",
        password: "secret-password",
      });
    });

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["auth", "me"] });
  });

  it("useRegister calls register and invalidates auth cache", async () => {
    vi.spyOn(authApi, "register").mockResolvedValueOnce(mockUser);

    const { result, queryClient } = renderHookWithProviders(() =>
      useRegister(),
    );
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    await act(async () => {
      await result.current.mutateAsync({
        email: "new@example.test",
        password: "secret-password",
        display_name: "New Reader",
      });
    });

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["auth", "me"] });
  });
});
