import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, ScrollRestoration, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/Button";
import { BrandMark } from "@/components/BrandMark";
import { RouteAccessibility } from "./RouteAccessibility";

export function Layout() {
  const { user, isAuthenticated, isRestoring, logout, signedOutReason } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [openPath, setOpenPath] = useState<string | null>(null);
  const menuOpen = openPath === pathname;
  const headerRef = useRef<HTMLElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const navClass = ({ isActive }: { isActive: boolean }) => `nav__link${isActive ? " nav__link--active" : ""}`;

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
        <nav className="nav" aria-label="Main">
          <NavLink to="/problems" className={navClass}>Practice</NavLink>
          {isAuthenticated && <NavLink to="/interviews" className={navClass}>Interview</NavLink>}
          {isAuthenticated && <NavLink to="/dashboard" className={navClass}>Dashboard</NavLink>}
          {isAuthenticated && <NavLink to="/targets" className={navClass}>Roles</NavLink>}
          {isAuthenticated && <NavLink to="/analytics" className={navClass}>Analytics</NavLink>}
          {isAuthenticated && <NavLink to="/history" className={navClass}>History</NavLink>}
          {isAuthenticated && <NavLink to="/saved" className={navClass}>Saved</NavLink>}
        </nav>
        <div className="header__account">
          {isAuthenticated ? (
            <>
              <NavLink to="/settings" className="header__user" title="Account settings"
                aria-label={`${user?.is_guest ? "Guest" : (user?.display_name ?? user?.email ?? "")}, account settings`}>
                {user?.is_guest ? <span className="badge">Guest</span> : (user?.display_name ?? user?.email)}
              </NavLink>
              <Button variant="ghost" size="sm" onClick={async () => { setOpenPath(null); await logout(); navigate("/"); }}>
                Sign out
              </Button>
            </>
          ) : isRestoring ? null /* checking the session cookie: don't flash "Sign in" */ : (
            <>
              <NavLink to="/login" className="nav__link">Sign in</NavLink>
              <Button variant="primary" size="sm" onClick={() => { setOpenPath(null); navigate("/register"); }}>Create account</Button>
            </>
          )}
        </div>
        </div>
      </header>
      {signedOutReason && !isAuthenticated && (
        <div className="banner banner--warning app__banner" role="status">{signedOutReason}</div>
      )}
      <main id="main" className="app__main" tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  );
}
