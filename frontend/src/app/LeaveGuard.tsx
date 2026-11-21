import { useEffect } from "react";
import { useBlocker } from "react-router-dom";

import { hasUnretainedWork, leaveQuestion, takeLeaveAfterSave } from "@/hooks/useLeaveWarning";

/**
 * In-app navigation asks first when a page has work that leaving would lose: the same pages and
 * the same condition (useLeaveWarning) as the browser's own close or reload warning. One guard for
 * the whole app (a router supports one blocker at a time). Moving within a page (its query or
 * hash) never asks.
 */
export function LeaveGuard() {
  const blocker = useBlocker(({ currentLocation, nextLocation }) =>
    currentLocation.pathname !== nextLocation.pathname && !takeLeaveAfterSave() && hasUnretainedWork());
  useEffect(() => {
    if (blocker.state !== "blocked") return;
    if (window.confirm(leaveQuestion())) blocker.proceed();
    else blocker.reset();
  }, [blocker]);
  return null;
}
