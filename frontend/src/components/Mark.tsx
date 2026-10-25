interface Props {
  size?: number;
  onDark?: boolean;
}

/** Marca: um medidor de envelhecimento parcialmente cheio. */
export function Mark({ size = 30, onDark = false }: Props) {
  return (
    <svg viewBox="0 0 30 30" width={size} height={size} aria-hidden="true">
      <rect x="10" y="3" width="10" height="24" rx="3" fill={onDark ? "#35564d" : "var(--rule-strong)"} />
      <rect x="10" y="13" width="10" height="14" rx="3" fill={onDark ? "#4fc2aa" : "var(--azinhavre)"} />
    </svg>
  );
}
