import { useEffect, useRef } from "react";
import { useLocation, useNavigationType } from "react-router-dom";

import { routeTitle } from "./routeTitles";

/** Give route changes a useful browser title and a predictable keyboard starting point. */
export function RouteAccessibility() {
  const { pathname } = useLocation();
  const navigationType = useNavigationType();
  const previous = useRef(pathname);
  useEffect(() => {
    document.title = `${routeTitle(pathname)} | CodeCoach AI`;
    if (previous.current !== pathname) {
      document.getElementById("main")?.focus({ preventScroll: true });
      // New pages start at the top; Back/Forward (POP) keep the position <ScrollRestoration> restores.
      if (navigationType !== "POP") window.scrollTo({ top: 0, behavior: "instant" });
      previous.current = pathname;
    }
  }, [pathname, navigationType]);
  return null;
}
