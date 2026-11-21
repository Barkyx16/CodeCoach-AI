import { type KeyboardEvent, type ReactNode, useEffect, useId, useRef, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";

export interface NavItem {
  to: string;
  title: string;
  description: string;
  icon: ReactNode;
}

export interface NavGroup {
  id: string;
  label: string;
  blurb: string;
  items: NavItem[];
}

/** Hover opens a panel only with a mouse, and only where the full header is shown (wider than the
 * menu-button layout in layout.css); touch and keyboard use the heading's button. */
function hoverOpens(): boolean {
  try {
    return window.matchMedia("(hover: hover) and (min-width: 1101px)").matches;
  } catch {
    return false;
  }
}

function isCurrent(pathname: string, to: string): boolean {
  return pathname === to || pathname.startsWith(`${to}/`);
}

/**
 * The site's main navigation: four or five headings, each opening a panel with the pages under
 * it (title, one line on what it's for, an icon). The disclosure-navigation pattern: each heading
 * is a button with aria-expanded; a mouse opens it on hover, a click or Enter toggles it, Escape
 * closes it and returns focus to the heading, and moving focus or the pointer away closes it. In
 * the narrow-screen menu every section is listed open, under its heading.
 */
export function MainNav({ groups }: { groups: NavGroup[] }) {
  const { pathname } = useLocation();
  // A panel belongs to the page it was opened on: going somewhere else closes it.
  const [openAt, setOpenAt] = useState<{ group: string; path: string } | null>(null);
  const open = openAt?.path === pathname ? openAt.group : null;
  const setOpen = (group: string | null) => setOpenAt(group ? { group, path: pathname } : null);
  const closeIf = (group: string) => setOpenAt((o) => (o?.group === group ? null : o));
  const closing = useRef<number | undefined>(undefined);
  const buttons = useRef(new Map<string, HTMLButtonElement>());
  // The group the pointer just opened by hovering: the click that usually follows keeps it open
  // rather than toggling it shut again. A second click closes it.
  const hoverOpened = useRef<string | null>(null);
  const id = useId();

  useEffect(() => () => window.clearTimeout(closing.current), []);

  const cancelClose = () => window.clearTimeout(closing.current);
  const closeSoon = (groupId: string) => {
    cancelClose();
    // A short grace period, so crossing the gap between heading and panel doesn't close it.
    closing.current = window.setTimeout(() => closeIf(groupId), 160);
  };

  function onKeyDown(event: KeyboardEvent<HTMLLIElement>, groupId: string) {
    if (event.key !== "Escape" || open !== groupId) return;
    event.stopPropagation(); // the narrow-screen menu would close too
    setOpen(null);
    buttons.current.get(groupId)?.focus();
  }

  return (
    <nav className="nav" aria-label="Main">
      <ul className="nav__groups">
        {groups.map((group) => {
          const expanded = open === group.id;
          const panelId = `${id}-${group.id}`;
          const current = group.items.some((item) => isCurrent(pathname, item.to));
          return (
            <li key={group.id} className={`nav-group${expanded ? " is-open" : ""}${current ? " is-current" : ""}`}
              onPointerEnter={(e) => {
                if (e.pointerType !== "mouse" || !hoverOpens()) return;
                cancelClose();
                if (!expanded) hoverOpened.current = group.id;
                setOpen(group.id);
              }}
              onPointerLeave={(e) => { if (e.pointerType === "mouse" && hoverOpens()) { hoverOpened.current = null; closeSoon(group.id); } }}
              onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) closeIf(group.id); }}
              onKeyDown={(e) => onKeyDown(e, group.id)}>
              <button type="button" className="nav-group__button" aria-expanded={expanded} aria-controls={panelId}
                ref={(el) => { if (el) buttons.current.set(group.id, el); else buttons.current.delete(group.id); }}
                onClick={() => {
                  if (hoverOpened.current === group.id) { hoverOpened.current = null; setOpen(group.id); return; }
                  setOpen(expanded ? null : group.id);
                }}>
                {group.label}
                <svg className="nav-group__chevron" width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
                  <path d="m2.5 4.5 3.5 3.5 3.5-3.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
              {/* In the narrow-screen menu the button is hidden and this heading shows instead. */}
              <span className="nav-group__label">{group.label}</span>
              <div id={panelId} className="nav-panel" data-open={expanded}>
                <div className="nav-panel__inner">
                  <div className="nav-panel__intro">
                    <p className="nav-panel__title">{group.label}</p>
                    <p className="nav-panel__blurb">{group.blurb}</p>
                  </div>
                  <ul className="nav-panel__items">
                    {group.items.map((item) => {
                      const describedBy = `${panelId}-${item.to.replace(/\W+/g, "-")}`;
                      return (
                        <li key={item.to}>
                          <NavLink to={item.to} className={({ isActive }) => `nav-item${isActive ? " is-active" : ""}`}
                            aria-describedby={describedBy}
                            // Close as soon as a page is chosen, not when it has rendered (a page
                            // that loads its code first would otherwise keep the panel open).
                            onClick={() => setOpen(null)}>
                            <span className="nav-item__icon" aria-hidden="true">{item.icon}</span>
                            <span className="nav-item__text">
                              <span className="nav-item__title">{item.title}</span>
                              <span className="nav-item__desc" id={describedBy} aria-hidden="true">{item.description}</span>
                            </span>
                          </NavLink>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
