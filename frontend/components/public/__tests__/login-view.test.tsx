import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { LoginView } from "@/components/public/login-view";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockLogin = vi.fn();
const mockStartGoogleOAuth = vi.fn();

vi.mock("@/hooks/public/use-auth", () => ({
  useLogin: () => ({
    mutateAsync: mockLogin,
    isPending: false,
    mutate: vi.fn(),
  }),
  useStartGoogleOAuth: () => mockStartGoogleOAuth,
}));

let queryClient: QueryClient;

beforeEach(() => {
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  vi.clearAllMocks();
  // Mock fetch for Google OAuth preflight
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ status: 302, type: "opaqueredirect" })
  );
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function renderLogin(onClose = vi.fn(), onSuccess = vi.fn()) {
  return render(
    <QueryClientProvider client={queryClient}>
      <LoginView onClose={onClose} onSuccess={onSuccess} />
    </QueryClientProvider>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("LoginView owner sign-in", () => {
  it("shows Google option and Owner toggle by default", () => {
    renderLogin();

    expect(screen.getByText("Continue with Google")).toBeInTheDocument();
    expect(screen.getByText("Google")).toBeInTheDocument();
    expect(screen.getByText("Owner")).toBeInTheDocument();
  });

  it("shows owner secret field when Owner tab is clicked", async () => {
    const user = userEvent.setup();
    renderLogin();

    await user.click(screen.getByText("Owner"));

    expect(screen.getByLabelText("Owner secret")).toBeInTheDocument();
    expect(screen.getByText("Sign in")).toBeInTheDocument();
  });

  it("does not show owner secret field in Google mode", () => {
    renderLogin();

    expect(screen.queryByLabelText("Owner secret")).not.toBeInTheDocument();
  });

  it("calls authApi.login on owner form submit", async () => {
    const user = userEvent.setup();
    const onSuccess = vi.fn();
    mockLogin.mockResolvedValueOnce({
      user_id: 1,
      email: "owner@local",
      role: "owner",
      is_authenticated: true,
      is_owner: true,
    });

    renderLogin(vi.fn(), onSuccess);

    // Switch to owner mode
    await user.click(screen.getByText("Owner"));

    // Type the secret
    const input = screen.getByLabelText("Owner secret");
    await user.type(input, "test-secret-value");

    // Submit
    await user.click(screen.getByText("Sign in"));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith("test-secret-value");
    });
  });

  it("calls onSuccess callback on successful owner login", async () => {
    const user = userEvent.setup();
    const onSuccess = vi.fn();
    mockLogin.mockResolvedValueOnce({
      user_id: 1,
      email: "owner@local",
      role: "owner",
      is_authenticated: true,
      is_owner: true,
    });

    renderLogin(vi.fn(), onSuccess);

    await user.click(screen.getByText("Owner"));
    await user.type(screen.getByLabelText("Owner secret"), "valid-secret");
    await user.click(screen.getByText("Sign in"));

    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalled();
    });
  });

  it("shows safe error on failed owner login", async () => {
    const user = userEvent.setup();
    mockLogin.mockRejectedValueOnce(new Error("401 Unauthorized"));

    renderLogin();

    await user.click(screen.getByText("Owner"));
    await user.type(screen.getByLabelText("Owner secret"), "wrong-secret");
    await user.click(screen.getByText("Sign in"));

    await waitFor(() => {
      expect(
        screen.getByText("Invalid credentials. Please try again.")
      ).toBeInTheDocument();
    });
  });

  it("does not reveal secret details in error message", async () => {
    const user = userEvent.setup();
    mockLogin.mockRejectedValueOnce(new Error("503 Not configured"));

    renderLogin();

    await user.click(screen.getByText("Owner"));
    await user.type(
      screen.getByLabelText("Owner secret"),
      "super-secret-123"
    );
    await user.click(screen.getByText("Sign in"));

    await waitFor(() => {
      const errorEl = screen.getByRole("alert");
      expect(errorEl.textContent).not.toContain("super-secret");
      expect(errorEl.textContent).not.toContain("503");
    });
  });

  it("clears secret from state after successful login", async () => {
    const user = userEvent.setup();
    mockLogin.mockResolvedValueOnce({
      user_id: 1,
      role: "owner",
      is_authenticated: true,
      is_owner: true,
    });

    renderLogin();

    await user.click(screen.getByText("Owner"));
    const input = screen.getByLabelText("Owner secret") as HTMLInputElement;
    await user.type(input, "my-secret");

    await user.click(screen.getByText("Sign in"));

    await waitFor(() => {
      expect(input.value).toBe("");
    });
  });

  it("does not show secret in DOM after failed login", async () => {
    const user = userEvent.setup();
    mockLogin.mockRejectedValueOnce(new Error("401"));

    renderLogin();

    await user.click(screen.getByText("Owner"));
    await user.type(screen.getByLabelText("Owner secret"), "my-secret-abc");

    await user.click(screen.getByText("Sign in"));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });

    // Secret should not be in any visible text
    const bodyText = document.body.textContent ?? "";
    expect(bodyText).not.toContain("my-secret-abc");
  });
});

describe("LoginView Google OAuth", () => {
  it("shows unavailable message when Google returns 503", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ status: 503 })
    );

    renderLogin();

    await user.click(screen.getByText("Continue with Google"));

    await waitFor(() => {
      expect(
        screen.getByText("Google sign-in is not configured on this server.")
      ).toBeInTheDocument();
    });
  });

  it("does not redirect when Google is unavailable", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ status: 503 })
    );

    renderLogin();

    await user.click(screen.getByText("Continue with Google"));

    await waitFor(() => {
      expect(mockStartGoogleOAuth).not.toHaveBeenCalled();
    });
  });

  it("redirects to Google OAuth when available", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ status: 302, type: "opaqueredirect" })
    );

    renderLogin();

    await user.click(screen.getByText("Continue with Google"));

    await waitFor(() => {
      expect(mockStartGoogleOAuth).toHaveBeenCalled();
    });
  });
});