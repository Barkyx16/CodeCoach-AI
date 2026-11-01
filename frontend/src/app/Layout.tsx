import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/Button";

export function Layout() {
  const { user, isAuthenticated, logout, signedOutReason } = useAuth();
  const navigate = useNavigate();
  const navClass = ({ isActive }: { isActive: boolean }) => `nav__link${isActive ? " nav__link--active" : ""}`;

  return (
    <div className="app">
      <a className="skip-link" href="#main">Skip to content</a>
      <header className="header">
        <NavLink to="/" className="brand" aria-label="CodeCoach AI home">
          <span className="brand__mark" aria-hidden="true">{"</>"}</span>
          <span className="brand__name">CodeCoach AI</span>
        </NavLink>
        <nav className="nav" aria-label="Main">
          <NavLink to="/problems" className={navClass}>Practice</NavLink>
          {isAuthenticated && <NavLink to="/interviews" className={navClass}>Interview</NavLink>}
          {isAuthenticated && <NavLink to="/dashboard" className={navClass}>Dashboard</NavLink>}
          {isAuthenticated && <NavLink to="/history" className={navClass}>History</NavLink>}
        </nav>
        <div className="header__account">
          {isAuthenticated ? (
            <>
              <NavLink to="/settings" className="header__user" title="Account settings"
                aria-label={`${user?.is_guest ? "Guest" : (user?.display_name ?? user?.email ?? "")}, account settings`}>
                {user?.is_guest ? <span className="badge">Guest</span> : (user?.display_name ?? user?.email)}
              </NavLink>
              <Button variant="ghost" size="sm" onClick={async () => { await logout(); navigate("/"); }}>
                Sign out
              </Button>
            </>
          ) : (
            <>
              <NavLink to="/login" className="nav__link">Sign in</NavLink>
              <Button variant="primary" size="sm" onClick={() => navigate("/register")}>Create account</Button>
            </>
          )}
        </div>
      </header>
      {signedOutReason && !isAuthenticated && (
        <div className="banner banner--warning app__banner" role="status">{signedOutReason}</div>
      )}
      <main id="main" className="app__main">
        <Outlet />
      </main>
    </div>
  );
}
