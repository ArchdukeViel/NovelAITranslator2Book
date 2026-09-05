import type { ReactElement, ReactNode } from "react";
import { render, renderHook, type RenderOptions, type RenderHookOptions } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

/**
 * Creates a clean QueryClient configured for test isolation.
 * Retries are disabled so failures propagate immediately without timer delays.
 */
export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
      mutations: {
        retry: false,
        gcTime: 0,
      },
    },
  });
}

interface ProviderOptions {
  queryClient?: QueryClient;
}

export function createWrapper(queryClient = createTestQueryClient()) {
  return function TestProviderWrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    );
  };
}

/**
 * Custom render that wraps components in QueryClientProvider and other required test contexts.
 */
export function renderWithProviders(
  ui: ReactElement,
  options: RenderOptions & ProviderOptions = {}
) {
  const { queryClient = createTestQueryClient(), ...renderOptions } = options;
  return {
    ...render(ui, {
      wrapper: createWrapper(queryClient),
      ...renderOptions,
    }),
    queryClient,
  };
}

/**
 * Custom renderHook that wraps hooks in QueryClientProvider.
 */
export function renderHookWithProviders<Result, Props>(
  hook: (props: Props) => Result,
  options: RenderHookOptions<Props> & ProviderOptions = {}
) {
  const { queryClient = createTestQueryClient(), ...hookOptions } = options;
  return {
    ...renderHook(hook, {
      wrapper: createWrapper(queryClient),
      ...hookOptions,
    }),
    queryClient,
  };
}

export * from "@testing-library/react";
