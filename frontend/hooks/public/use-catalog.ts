"use client";

import { useQuery } from "@tanstack/react-query";
import { publicApi } from "@/lib/public-api";
import { catalogQueryKey } from "@/lib/public-query-keys";
import type { CatalogParams } from "@/lib/public-types";

export { catalogQueryKey } from "@/lib/public-query-keys";

export function useCatalog(params: CatalogParams) {
  return useQuery({
    queryKey: catalogQueryKey(params),
    queryFn: ({ signal }) => publicApi.catalog(params, signal),
    retry: false,
  });
}
