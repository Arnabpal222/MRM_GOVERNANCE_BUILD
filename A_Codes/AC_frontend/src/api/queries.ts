import { useQuery } from "@tanstack/react-query";
import { api } from "./client";
import type { Model360, ModelMeta } from "./types";

export function useModelMeta() {
  return useQuery({ queryKey: ["model-meta"], queryFn: () => api<ModelMeta>("/api/models/meta"), staleTime: 60_000 });
}

export function useModel360(modelId: string | undefined) {
  return useQuery({
    queryKey: ["model", modelId],
    queryFn: () => api<Model360>(`/api/models/${modelId}`),
    enabled: !!modelId,
  });
}

/** Resolve a user id to "Full Name (U-123)" using the meta user list. */
export function userLabel(meta: ModelMeta | undefined, id: string | null | undefined): string {
  if (!id) return "—";
  const u = meta?.users.find((x) => x.user_id === id);
  return u ? `${u.full_name} (${id})` : id;
}
