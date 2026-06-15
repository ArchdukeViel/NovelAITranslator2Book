"use client";

import { useQuery } from "@tanstack/react-query";
import { publicApi } from "@/lib/public-api";
import type { CatalogParams } from "@/lib/public-types";

export function useCatalog(params: CatalogParams) {
  return useQuery({
    queryKey: ["public", "catalog", params],
    queryFn: () => publicApi.catalog(params),
  });
}
