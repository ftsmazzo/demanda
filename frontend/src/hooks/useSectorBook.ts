import { useMemo } from "react";
import type { Sector, SectorInfo } from "../api/types";
import { SECTOR_COLOR, SECTOR_LABEL, SECTORS } from "../lib/sectors";
import { useSectors } from "./queries";

const FALLBACK: SectorInfo[] = SECTORS.map((slug) => ({
  slug,
  label: SECTOR_LABEL[slug],
  color: SECTOR_COLOR[slug],
  system: slug === "triagem" || slug === "rh-interno",
  active: true,
}));

export interface SectorBook {
  /** setores ativos (os que recebem trabalho novo), na ordem do escritorio */
  active: SectorInfo[];
  label: (slug: Sector) => string;
  color: (slug: Sector) => string;
}

/** Nomes e cores dos setores do escritorio; enquanto a lista nao chega (ou falha) valem os padroes. */
export function useSectorBook(): SectorBook {
  const query = useSectors();
  const all = query.data ?? FALLBACK;
  return useMemo(() => {
    const bySlug = new Map(all.map((item) => [item.slug, item]));
    return {
      active: all.filter((item) => item.active),
      label: (slug) => bySlug.get(slug)?.label ?? SECTOR_LABEL[slug] ?? slug,
      color: (slug) => bySlug.get(slug)?.color ?? SECTOR_COLOR[slug] ?? "var(--sector-triagem)",
    };
  }, [all]);
}
