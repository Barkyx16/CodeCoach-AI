import { useDisplayPrefs } from "@/features/display/displayPrefs";

import { RAIL_ICONS } from "./navIcons";

/**
 * Narrows the sidebar to a rail of icons, or widens it again (wider than 1100px; hidden below).
 * The same preference as Settings › Display › Sidebar, kept in this browser. The button keeps
 * focus as the sidebar changes width, so pressing it again undoes it.
 */
export function SidebarToggle() {
  const { prefs, update } = useDisplayPrefs();
  const icons = prefs.sidebar === "icons";
  const label = icons ? "Expand sidebar" : "Collapse sidebar";
  return (
    <button type="button" className="sidebar-toggle btn btn--ghost btn--sm" aria-label={label} data-tip={label}
      title={icons ? undefined : label} onClick={() => update({ sidebar: icons ? "full" : "icons" })}>
      <span className="sidebar-toggle__icon" aria-hidden="true">{icons ? RAIL_ICONS.expand : RAIL_ICONS.collapse}</span>
    </button>
  );
}
