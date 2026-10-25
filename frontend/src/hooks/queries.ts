import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { BoardFilters, ContactKind } from "../api/types";
import { useAuth } from "../auth/AuthContext";

export const boardKey = (filters: BoardFilters) => ["board", filters.sector ?? "", filters.assignee ?? ""];

export function useBoard(filters: BoardFilters) {
  const { api } = useAuth();
  return useQuery({
    queryKey: boardKey(filters),
    queryFn: () => api.board(filters),
    placeholderData: keepPreviousData,
    refetchInterval: 30_000,
  });
}

export function useUsers(enabled: boolean) {
  const { api } = useAuth();
  return useQuery({
    queryKey: ["users"],
    queryFn: () => api.users(),
    enabled,
    staleTime: 5 * 60_000,
  });
}

export function useContacts(q: string, kind: ContactKind | "", enabled = true) {
  const { api } = useAuth();
  return useQuery({
    queryKey: ["contacts", q, kind],
    queryFn: () => api.contacts({ q, kind }),
    enabled,
    placeholderData: keepPreviousData,
  });
}

export function usePatchContact() {
  const { api } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: { name?: string; kind?: ContactKind } }) =>
      api.patchContact(id, patch),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["contacts"] });
      void queryClient.invalidateQueries({ queryKey: ["board"] });
    },
  });
}

export function useChannelHealth(enabled: boolean) {
  const { api } = useAuth();
  return useQuery({
    queryKey: ["channels-health"],
    queryFn: () => api.channelsHealth(),
    enabled,
    refetchInterval: 60_000,
    retry: false,
  });
}
