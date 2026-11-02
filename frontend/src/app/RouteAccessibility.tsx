import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";

const TITLES: Record<string, string> = {
  "/": "Java interview practice", "/login": "Sign in", "/register": "Create account",
  "/forgot-password": "Reset your password", "/reset-password": "Choose a new password",
  "/problems": "Problem library", "/dashboard": "Dashboard", "/analytics": "Analytics",
  "/history": "History", "/settings": "Settings", "/interviews": "Mock interviews",
};

/** Give route changes a useful browser title and a predictable keyboard starting point. */
export function RouteAccessibility() {
  const { pathname } = useLocation();
  const previous = useRef(pathname);
  useEffect(() => {
    const title = TITLES[pathname] ?? (pathname.startsWith("/problems/") ? "Coding workspace"
      : pathname.startsWith("/interviews/") ? "Mock interview" : "Page not found");
    document.title = `${title} | CodeCoach AI`;
    if (previous.current !== pathname) {
      document.getElementById("main")?.focus({ preventScroll: true });
      window.scrollTo({ top: 0, behavior: "instant" });
      previous.current = pathname;
    }
  }, [pathname]);
  return null;
}
