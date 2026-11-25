import { Link } from "react-router-dom";

import { useAuth } from "@/auth/useAuth";

import { useBrowseCareer } from "./practiceTrack";

/**
 * One line of context when a page shows a career that isn't the learner's own (Volume 9, prompt
 * 4): what's shown, that their plan and progress follow their own career, the way back to it, and
 * where to change it on purpose (Settings). Nothing when they're on their own career, and nothing
 * for a signed-out visitor, whose page heading already names the career. A `?career=` that names
 * no career says what's shown instead.
 */
export function BrowseNote({ what, back, backWhat = what, scope }: {
  /** What the page lists, e.g. "interview questions". */
  what: string;
  /** The same page for the learner's own career. */
  back: string;
  /** What the learner's own page lists, when it differs (a nurse has questions, not coding problems). */
  backWhat?: string;
  /** What a personal action on this page does with the career shown. */
  scope?: string;
}) {
  const { isAuthenticated } = useAuth();
  const b = useBrowseCareer();
  const shown = b.career?.title ?? b.track;
  if (b.unknown) {
    const asked = b.unknown.length > 40 ? `${b.unknown.slice(0, 40)}…` : b.unknown;
    return <p className="subtle browse-note" role="status">There's no career called “{asked}” here, so these are {shown} {what}.</p>;
  }
  if (!isAuthenticated || !b.browsing || !b.own) return null;
  const mine = b.ownCareer?.title ?? b.own;
  return (
    <p className="subtle browse-note">
      Viewing {shown} {what}. Your plan and progress follow your own career, {mine}.{scope ? ` ${scope}` : ""}{" "}
      <Link to={back}>Back to {mine} {backWhat}</Link> · <Link to="/settings#account">Change my career</Link>
    </p>
  );
}
