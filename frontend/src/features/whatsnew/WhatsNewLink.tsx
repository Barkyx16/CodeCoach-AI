import { NavLink, type NavLinkProps } from "react-router-dom";

import { useAuth } from "@/auth/useAuth";

import { forThisCareer } from "./whatsNew";
import { useSeenRelease, useShippedEntries, useWhatsNewContext } from "./useWhatsNew";

/**
 * The header's "What's new" link (docs/WHATS_NEW.md). For a signed-in learner with changes they
 * haven't looked at in this browser, a small dot and, in the link's name, how many: nothing moves,
 * opens, speaks up or takes focus, so an interview or an answer in progress isn't interrupted.
 * The careers list is asked for only when a coding-only change is among the unseen ones.
 */
export function WhatsNewLink({ className }: { className: NavLinkProps["className"] }) {
  const { user, isAuthenticated } = useAuth();
  const entries = useShippedEntries();
  const { release: seen } = useSeenRelease(isAuthenticated ? user?.id : undefined);
  const candidates = seen === null ? [] : entries.filter((e) => e.release > seen);
  const { context, careerKnown } = useWhatsNewContext(candidates.some((e) => e.audience === "coding"));
  // Until the career is known, a coding-only change isn't counted.
  const count = candidates.filter((e) => (e.audience === "coding" ? careerKnown && forThisCareer(e, context) : true)).length;
  return (
    // The name is set outright when there's a count, so every browser reads the same words.
    <NavLink to="/whats-new" className={className} aria-label={count > 0 ? `What's new, ${count} new` : undefined}>
      What&apos;s new
      {count > 0 && <span className="whats-new-dot" aria-hidden="true" />}
    </NavLink>
  );
}
