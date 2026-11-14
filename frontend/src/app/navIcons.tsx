import type { ReactNode } from "react";

/** Line icons for the navigation (24-unit grid, drawn with the text colour). */
const icon = (d: string): ReactNode => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <path d={d} />
  </svg>
);

export const NAV_ICONS = {
  questions: icon("M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01"),
  interview: icon("M12 3a3 3 0 0 0-3 3v5a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3ZM5 11a7 7 0 0 0 14 0M12 18v3"),
  lessons: icon("M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5v-15ZM4 20.5A2.5 2.5 0 0 0 6.5 23H20v-5"),
  drills: icon("M4 12h3l2-5 4 10 2-5h5"),
  scenarios: icon("M6 3v6a6 6 0 0 0 6 6h0a6 6 0 0 1 6 6M18 3v6M15 6l3-3 3 3"),
  dashboard: icon("M4 4h7v7H4zM13 4h7v4h-7zM13 10h7v10h-7zM4 13h7v7H4z"),
  analytics: icon("M4 20V10M10 20V4M16 20v-7M22 20H2"),
  history: icon("M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l3 2"),
  roles: icon("M10 6V4h4v2M4 7h16v12H4zM4 12h16"),
  applications: icon("M9 4h6v3H9zM6 5H5v16h14V5h-1M9 12h6M9 16h4"),
  schedule: icon("M4 6h16v15H4zM4 10h16M9 3v4M15 3v4"),
  stories: icon("M5 4h10l4 4v12H5zM14 4v5h5M9 13h6M9 17h4"),
  notes: icon("M4 20h4L19 9l-4-4L4 16v4ZM13 7l4 4"),
  saved: icon("M7 3h10v18l-5-4-5 4z"),
  search: icon("M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14ZM20 20l-4-4"),
  triage: icon("M12 3 2 21h20L12 3ZM12 10v5M12 18h.01"),
};
