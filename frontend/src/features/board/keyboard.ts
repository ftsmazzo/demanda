import type { KeyboardCoordinateGetter } from "@dnd-kit/core";

/**
 * Setas esquerda/direita levam o card para a coluna anterior/seguinte, na ordem de leitura
 * (as colunas podem quebrar em duas linhas em telas medias), parando no meio da coluna destino.
 */
export const laneKeyboardCoordinates: KeyboardCoordinateGetter = (
  event,
  { context: { droppableRects, droppableContainers, collisionRect }, currentCoordinates },
) => {
  const direction = event.code === "ArrowRight" ? 1 : event.code === "ArrowLeft" ? -1 : 0;
  if (!direction || !collisionRect) return undefined;
  event.preventDefault();

  const lanes = droppableContainers
    .getEnabled()
    .map((container) => droppableRects.get(container.id))
    .filter((rect): rect is NonNullable<typeof rect> => Boolean(rect))
    .sort((a, b) => a.top - b.top || a.left - b.left);
  const centerX = collisionRect.left + collisionRect.width / 2;
  const centerY = collisionRect.top + collisionRect.height / 2;
  const current = lanes.findIndex(
    (rect) =>
      centerX >= rect.left &&
      centerX <= rect.left + rect.width &&
      centerY >= rect.top &&
      centerY <= rect.top + rect.height,
  );
  const target = lanes[current + direction];
  if (current < 0 || !target) return undefined;

  return {
    x: currentCoordinates.x + (target.left + target.width / 2 - centerX),
    y: currentCoordinates.y + (target.top + Math.min(target.height, 140) / 2 - centerY) * (target.top === lanes[current].top ? 0 : 1),
  };
};
