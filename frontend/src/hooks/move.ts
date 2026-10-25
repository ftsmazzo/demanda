import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { Board, Status } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { moveInBoard } from "../lib/board";

type Snapshot = [readonly unknown[], Board | undefined][];

/** Mover uma demanda de coluna: o card muda na hora e volta sozinho se o servidor recusar. */
export function useMoveDemand() {
  const { api } = useAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, to }: { id: string; to: Status }) => api.patchDemand(id, { status: to }),
    onMutate: async ({ id, to }) => {
      await queryClient.cancelQueries({ queryKey: ["board"] });
      const snapshot: Snapshot = queryClient.getQueriesData<Board>({ queryKey: ["board"] });
      const now = new Date().toISOString();
      for (const [key, board] of snapshot) {
        if (board) queryClient.setQueryData<Board>(key, moveInBoard(board, id, to, now));
      }
      return { snapshot };
    },
    onError: (_error, _vars, context) => {
      for (const [key, board] of context?.snapshot ?? []) queryClient.setQueryData(key, board);
    },
    onSettled: (_data, _error, vars) => {
      void queryClient.invalidateQueries({ queryKey: ["board"] });
      void queryClient.invalidateQueries({ queryKey: ["demand", vars.id] });
    },
  });
}
