/** Sequential buckets (one hue, light = more). Thresholds are counts of activity events. */
export function heatLevel(events: number): 0 | 1 | 2 | 3 | 4 {
  if (events <= 0) return 0;
  if (events <= 2) return 1;
  if (events <= 5) return 2;
  if (events <= 9) return 3;
  return 4;
}
