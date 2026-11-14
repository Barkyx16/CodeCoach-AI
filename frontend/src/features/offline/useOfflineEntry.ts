import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { listOffline, readOffline, removeOffline, saveOffline, type OfflineKind } from "./offlineStore";

export function useOfflineEntry(kind: OfflineKind, key: string) {
  return useQuery({
    queryKey: ["offline", kind, key],
    queryFn: async () => (await readOffline(kind, key))?.entry ?? null,
    staleTime: 0,
    networkMode: "always", // reads this device, not the network
  });
}

export function useOfflineList() {
  return useQuery({ queryKey: ["offline", "list"], queryFn: listOffline, staleTime: 0, networkMode: "always" });
}

/** Save or remove an offline copy, keeping every view of the offline store in step. */
export function useOfflineMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ kind, key, remove }: { kind: OfflineKind; key: string; remove?: boolean }) =>
      remove ? removeOffline(kind, key).then(() => null) : saveOffline(kind, key),
    networkMode: "always",
    onSettled: () => void qc.invalidateQueries({ queryKey: ["offline"] }),
  });
}
