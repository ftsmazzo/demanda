import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { AppointmentStatus, BoardFilters, ContactKind } from "../api/types";
import { useAuth } from "../auth/AuthContext";

export const boardKey = (filters: BoardFilters) => [
  "board",
  filters.sector ?? "",
  filters.assignee ?? "",
  filters.priority ?? false,
];

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
    mutationFn: ({ id, patch }: { id: string; patch: { name?: string; kind?: ContactKind; priority?: boolean } }) =>
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

export function useAppointments(range: { since?: string; until?: string } = {}) {
  const { api } = useAuth();
  return useQuery({
    queryKey: ["appointments", range.since ?? "", range.until ?? ""],
    queryFn: () => api.appointments(range),
    refetchInterval: 60_000,
    placeholderData: keepPreviousData,
  });
}

export function usePatchAppointment() {
  const { api } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...patch }: { id: string; status?: AppointmentStatus; starts_at?: string; all_day?: boolean }) =>
      api.patchAppointment(id, patch),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["appointments"] });
      void queryClient.invalidateQueries({ queryKey: ["today"] });
    },
  });
}

export function useSectors() {
  const { api } = useAuth();
  return useQuery({
    queryKey: ["sectors"],
    queryFn: () => api.sectors(),
    staleTime: 5 * 60_000,
    retry: false,
  });
}

export function useCreateSector() {
  const { api } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { label: string; color?: string }) => api.createSector(body),
    onSettled: () => void queryClient.invalidateQueries({ queryKey: ["sectors"] }),
  });
}

export function usePatchSector() {
  const { api } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ slug, ...patch }: { slug: string; label?: string; color?: string; active?: boolean }) =>
      api.patchSector(slug, patch),
    onSettled: () => void queryClient.invalidateQueries({ queryKey: ["sectors"] }),
  });
}

export function useConversation(contactId: string | undefined) {
  const { api } = useAuth();
  return useQuery({
    queryKey: ["conversation", contactId],
    queryFn: () => api.conversation(contactId as string),
    enabled: Boolean(contactId),
    refetchInterval: 30_000,
  });
}

export function useToday() {
  const { api } = useAuth();
  return useQuery({
    queryKey: ["today"],
    queryFn: () => api.today(),
    refetchInterval: 30_000,
  });
}

export function useConversations(q: string, waiting: boolean, enabled = true) {
  const { api } = useAuth();
  return useQuery({
    queryKey: ["conversations", q, waiting],
    queryFn: () => api.conversations({ q, waiting }),
    enabled,
    placeholderData: keepPreviousData,
    refetchInterval: 30_000,
  });
}
