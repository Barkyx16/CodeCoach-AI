import type { SVGProps } from "react";

const paths = {
  arrow: "M5 12h14m-6-6 6 6-6 6",
  book: "M4 4h6a3 3 0 0 1 3 3v14a4 4 0 0 0-4-3H4V4Zm9 3a3 3 0 0 1 3-3h5v14h-4a4 4 0 0 0-4 3",
  chart: "M4 4v16h16M8 15v-4m5 4V7m5 8v-6",
  check: "m5 12 4 4L19 6",
  clock: "M12 8v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0",
  code: "m8 7-5 5 5 5m8-10 5 5-5 5M14 4l-4 16",
  file: "M14 3H5v18h14V8l-5-5Zm0 0v5h5M8 12h8m-8 4h5",
  flame: "M13 3c1 6-4 6-4 10 0 2 1 3 3 3 3 0 4-3 3-6 4 2 5 5 3 8-3 5-11 4-12-1-2-6 5-8 7-14Z",
  search: "m16 16 5 5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0",
  shield: "m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Zm-4 9 3 3 5-6",
  spark: "m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z",
  target: "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0ZM17 12a5 5 0 1 1-10 0 5 5 0 0 1 10 0Zm-3 0a2 2 0 1 1-4 0 2 2 0 0 1 4 0Z",
  terminal: "m5 7 5 5-5 5m8 0h6M3 3h18v18H3V3Z",
  user: "M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0ZM4 21v-2a8 8 0 0 1 16 0v2",
} as const;
export type IconName = keyof typeof paths;

/** Small decorative icons, bundled with the app and consistent with the code mark. */
export function Icon({ name, size = 20, ...props }: SVGProps<SVGSVGElement> & { name: IconName; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}><path d={paths[name]} /></svg>;
}
