import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { NavLink, Outlet, ScrollRestoration, useLocation, useNavigate } from "react-router-dom";

import { useCapabilities } from "@/api/queries";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/Button";
import { BrandMark } from "@/components/BrandMark";
import { FocusModeContext } from "@/features/display/focusContext";
import { countLocalWork } from "@/auth/localWork";
import { noteLocation } from "@/lib/documentEntry";

import { AppStatus } from "./AppStatus";
import { LeaveGuard } from "./LeaveGuard";
import { Reminders } from "@/features/schedule/Reminders";
import { TourFinishReconciler } from "@/features/onboarding/TourFinishReconciler";
import { PlanReturn } from "@/features/plan/PlanReturn";
import { MainNav, type NavGroup } from "./MainNav";
import { NAV_ICONS } from "./navIcons";
import { RouteAccessibility } from "./RouteAccessibility";
import { SessionEndedBanner } from "./SessionEndedBanner";

export function Layout() {
  const { user, isAuthenticated, isRestoring, logout, signedOutReason, offlineUser } = useAuth();
  const navigate = useNavigate();
  const { pathname, key: locationKey } = useLocation();
  // Every location shown, so a list can tell a page opened directly from a return to it.
  useLayoutEffect(() => noteLocation(locationKey), [locationKey]);
  // A demo server has no accounts to sign in to or create: its header offers the demo instead.
  // Only a signed-out header needs to know.
  const demoMode = useCapabilities(!isAuthenticated && !isRestoring).data?.demo_mode === true;
  const [openPath, setOpenPath] = useState<string | null>(null);
  const menuOpen = openPath === pathname;
  const headerRef = useRef<HTMLElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);
  // Focus mode belongs to the page it was turned on for: navigating elsewhere ends it.
  const [focusPath, setFocusPath] = useState<string | null>(null);
  const focusOn = focusPath === pathname;
  const release = useCallback(() => setFocusPath(null), []);
  const focusMode = useMemo(() => ({
    on: focusOn,
    enter: () => setFocusPath(pathname),
    exit: () => {
      setFocusPath(null);
      // Put keyboard focus back where the learner turned it on.
      window.requestAnimationFrame(() => document.getElementById("focus-toggle")?.focus());
    },
    release,
  }), [focusOn, pathname, release]);

  // A layout effect: the page and the mode change in the same commit, so the next page never
  // appears, even for a frame, without its header (a passive effect ran after it was shown).
  useLayoutEffect(() => {
    document.documentElement.toggleAttribute("data-focus", focusOn);
    if (!focusOn) return;
    const onKey = (event: KeyboardEvent) => {
      const inEditor = (event.target as HTMLElement | null)?.closest?.(".monaco-editor");
      if (event.key === "Escape" && !inEditor && !event.defaultPrevented) focusMode.exit();
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.documentElement.removeAttribute("data-focus");
    };
  }, [focusOn, focusMode]);
  const navClass = ({ isActive }: { isActive: boolean }) => `nav__link${isActive ? " nav__link--active" : ""}`;
  const navGroups = useMemo<NavGroup[]>(() => {
    const signedIn = isAuthenticated;
    const practice: NavGroup = {
      id: "practice", label: "Practice",
      blurb: "Answer real interview questions for your job, one at a time or as a full mock interview.",
      items: [
        { to: "/problems", title: "Questions", description: "Every question for your job, by difficulty", icon: NAV_ICONS.questions },
        ...(signedIn ? [{ to: "/interviews", title: "Mock interview", description: "Questions in a row, like the real thing", icon: NAV_ICONS.interview }] : []),
        { to: "/learn", title: "Lessons", description: "Short lessons with guided help", icon: NAV_ICONS.lessons },
        ...(signedIn ? [
          { to: "/drills", title: "Drills", description: "Quick exercises in how you say it", icon: NAV_ICONS.drills },
          { to: "/scenarios", title: "Scenarios", description: "Choose what to do and see what follows", icon: NAV_ICONS.scenarios },
        ] : []),
      ],
    };
    if (!signedIn) return [practice];
    return [
      practice,
      {
        id: "progress", label: "Progress", blurb: "See what you've done, how it's going and where to focus next.",
        items: [
          { to: "/dashboard", title: "Dashboard", description: "Today's plan and where you stand", icon: NAV_ICONS.dashboard },
          { to: "/analytics", title: "Analytics", description: "Scores and trends over time", icon: NAV_ICONS.analytics },
          { to: "/history", title: "History", description: "Every answer and round, with feedback", icon: NAV_ICONS.history },
        ],
      },
      {
        id: "job-search", label: "Job search", blurb: "The roles you're after, where you've applied and when you're interviewing.",
        items: [
          { to: "/targets", title: "Roles", description: "Target roles and what each one asks for", icon: NAV_ICONS.roles },
          { to: "/applications", title: "Applications", description: "Track where you've applied", icon: NAV_ICONS.applications },
          { to: "/schedule", title: "Schedule", description: "Interviews and practice on your calendar", icon: NAV_ICONS.schedule },
        ],
      },
      {
        id: "library", label: "Library", blurb: "Everything you've written down and kept for later.",
        items: [
          { to: "/stories", title: "Stories", description: "Your examples, ready for any question", icon: NAV_ICONS.stories },
          { to: "/notes", title: "Notes", description: "What you've noted while practising", icon: NAV_ICONS.notes },
          { to: "/saved", title: "Saved", description: "Bookmarks and collections", icon: NAV_ICONS.saved },
          ...(user?.is_admin ? [{ to: "/admin/reports", title: "Triage", description: "Reports about questions", icon: NAV_ICONS.triage }] : []),
        ],
      },
    ];
  }, [isAuthenticated, user?.is_admin]);

  useEffect(() => {
    if (!menuOpen) return;
    const dismiss = (event: PointerEvent) => {
      if (!headerRef.current?.contains(event.target as Node)) setOpenPath(null);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpenPath(null);
        toggleRef.current?.focus();
      }
    };
    document.addEventListener("pointerdown", dismiss);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", dismiss);
      document.removeEventListener("keydown", escape);
    };
  }, [menuOpen]);

  return (
    <div className="app">
      <RouteAccessibility />
      <ScrollRestoration />
      <a className="skip-link" href="#main">Skip to content</a>
      {focusOn ? (
        <header className="header header--focus">
          <span className="brand" aria-hidden="true"><BrandMark /></span>
          <p className="header__focus-note"><strong>Focus mode</strong><span className="header__focus-detail">: navigation and side panels are hidden. Press Esc or the button to exit.</span></p>
          <Button variant="secondary" size="sm" onClick={focusMode.exit}>Exit focus mode</Button>
        </header>
      ) : (
      <header className="header" ref={headerRef}>
        <NavLink to="/" className="brand" aria-label="CodeCoach AI home">
          <BrandMark />
          <span className="brand__name">CodeCoach AI</span>
        </NavLink>
        <button className="menu-toggle btn btn--ghost btn--md" type="button" ref={toggleRef}
          aria-expanded={menuOpen}
          aria-controls="primary-navigation" onClick={() => setOpenPath(menuOpen ? null : pathname)}>
          <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.7">
            <path d={menuOpen ? "m6 6 12 12M6 18 18 6" : "M4 6h16M4 12h16M4 18h16"} />
          </svg>
          Menu
        </button>
        <div id="primary-navigation" className="nav-shell" data-open={menuOpen}
          onClick={(event) => { if ((event.target as HTMLElement).closest("a")) setOpenPath(null); }}>
        <MainNav groups={navGroups} />
        <div className="header__account">
          <NavLink to="/help" className={navClass}>Help</NavLink>
          {isAuthenticated ? (
            <>
              <NavLink to="/settings" className="header__user" title="Account settings"
                aria-label={`${user?.is_guest ? "Guest" : (user?.display_name ?? user?.email ?? "")}, account settings`}>
                {user?.is_guest ? <span className="badge">Guest</span> : (user?.display_name ?? user?.email)}
              </NavLink>
              <Button variant="ghost" size="sm" onClick={async () => {
                const unsent = user ? countLocalWork(user.id) : 0;
                if (unsent > 0 && !window.confirm(`You have ${unsent} unsent ${unsent === 1 ? "draft" : "drafts"} on this device. Signing out deletes ${unsent === 1 ? "it" : "them"} from this device. Sign out anyway?`)) return;
                setOpenPath(null); await logout(); navigate("/");
              }}>
                Sign out
              </Button>
            </>
          ) : isRestoring ? null /* checking the session cookie: don't flash "Sign in" */ : offlineUser ? (
            <span className="header__user" title="Offline: your sign-in will be checked when you're back online">
              <span className="badge">Offline</span> {offlineUser.display_name ?? (offlineUser.is_guest ? "Guest" : "")}
            </span>
          ) : demoMode ? (
            <NavLink to="/demo" className="btn btn--primary btn--sm" onClick={() => setOpenPath(null)}>Guided demo</NavLink>
          ) : (
            <>
              <NavLink to="/login" className="nav__link">Sign in</NavLink>
              {/* A link like "Sign in": on /register it's marked as the current page, not a button that does nothing. */}
              <NavLink to="/register" className="btn btn--primary btn--sm" onClick={() => setOpenPath(null)}>Create account</NavLink>
            </>
          )}
        </div>
        </div>
      </header>
      )}
      <AppStatus />
      <LeaveGuard />
      <Reminders />
      {isAuthenticated && <TourFinishReconciler />}
      {signedOutReason && !isAuthenticated && <SessionEndedBanner reason={signedOutReason} />}
      <main id="main" className="app__main" tabIndex={-1}>
        <FocusModeContext.Provider value={focusMode}>
          {isAuthenticated && <PlanReturn />}
          <Outlet />
        </FocusModeContext.Provider>
      </main>
    </div>
  );
}
