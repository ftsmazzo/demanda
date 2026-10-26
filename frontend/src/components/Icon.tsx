const PATHS = {
  board: "M4 5h4.5v14H4zM9.75 5h4.5v9h-4.5zM15.5 5H20v11.5h-4.5z",
  chart: "M5 19V11M10 19V5M15 19v-6M20 19V8",
  people:
    "M8.5 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM3 19c0-3 2.5-5 5.5-5s5.5 2 5.5 5M16.5 6.5a2.6 2.6 0 0 1 0 5M17.5 14.3c1.9.5 3.5 2 3.5 4.7",
  star:
    "M12 4.5l2.2 4.6 5 .7-3.6 3.5.9 5-4.5-2.4-4.5 2.4.9-5L4.8 9.8l5-.7z",
  chat:
    "M5 6.5h14v9H10l-4 3.5v-3.5H5z",
  sun:
    "M12 7.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9zM12 3.5v2M12 18.5v2M3.5 12h2M18.5 12h2M6 6l1.4 1.4M16.6 16.6 18 18M6 18l1.4-1.4M16.6 7.4 18 6",
  calendar:
    "M5 6.5h14v12.5H5zM5 10.5h14M9 4v4M15 4v4",
  plus: "M12 5v14M5 12h14",
  close: "M6 6l12 12M18 6 6 18",
  check: "M5 12.5l4.5 4.5L19 7.5",
  lock: "M7 11V8a5 5 0 0 1 10 0v3M6 11h12v9H6z",
  search: "M10.5 17a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13zM20 20l-4.8-4.8",
} as const;

export type IconName = keyof typeof PATHS;

interface Props {
  name: IconName;
  size?: number;
}

export function Icon({ name, size = 21 }: Props) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
