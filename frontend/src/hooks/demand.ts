import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { DemandCreate, DemandPatch, Detail, Subtask } from "../api/types";
import { useAuth } from "../auth/AuthContext";

const demandKey = (id: string) => ["demand", id];

function withProgress(detail: Detail): Detail {
  const total = detail.subtasks.length;
  const done = detail.subtasks.filter((item) => item.done).length;
  return { ...detail, progress: { done, total, percent: total ? Math.round((100 * done) / total) : 0 } };
}

export function useDemand(id: string) {
  const { api } = useAuth();
  return useQuery({ queryKey: demandKey(id), queryFn: () => api.demand(id) });
}

export function usePatchDemand(id: string) {
  const { api } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (patch: DemandPatch) => api.patchDemand(id, patch),
    onSuccess: (detail) => {
      queryClient.setQueryData(demandKey(id), detail);
      void queryClient.invalidateQueries({ queryKey: ["board"] });
    },
  });
}

export function useToggleSubtask(demandId: string) {
  const { api } = useAuth();
  const queryClient = useQueryClient();
  const key = demandKey(demandId);

  return useMutation({
    mutationKey: ["toggle", demandId],
    mutationFn: ({ id, done }: { id: string; done: boolean }) => api.patchSubtask(id, { done }),
    onMutate: async ({ id, done }) => {
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<Detail>(key);
      if (previous) {
        const subtasks = previous.subtasks.map((item) => (item.id === id ? { ...item, done } : item));
        queryClient.setQueryData(key, withProgress({ ...previous, subtasks }));
      }
      return { previous };
    },
    onError: (_error, _vars, context) => {
      if (queryClient.isMutating({ mutationKey: ["toggle", demandId] }) > 1) return;
      if (context?.previous) queryClient.setQueryData(key, context.previous);
    },
    onSettled: () => {
      if (queryClient.isMutating({ mutationKey: ["toggle", demandId] }) > 1) return;
      void queryClient.invalidateQueries({ queryKey: key });
      void queryClient.invalidateQueries({ queryKey: ["board"] });
    },
  });
}

export function useAddSubtask(demandId: string) {
  const { api } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (title: string) => api.addSubtask(demandId, title),
    onSuccess: (created: Subtask) => {
      queryClient.setQueryData<Detail>(demandKey(demandId), (current) =>
        current ? withProgress({ ...current, subtasks: [...current.subtasks, created] }) : current,
      );
      void queryClient.invalidateQueries({ queryKey: ["board"] });
    },
  });
}

export function useCreateDemand() {
  const { api } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: DemandCreate) => api.createDemand(body),
    onSuccess: (detail) => {
      queryClient.setQueryData(demandKey(detail.id), detail);
      void queryClient.invalidateQueries({ queryKey: ["board"] });
    },
  });
}
