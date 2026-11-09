import type { ReactNode } from "react";

import { Button } from "@/components/Button";

import type { useEarlierAction } from "./useEarlierAction";

const time = (ms: number) => new Date(ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

/**
 * What became of an action sent before the page was reloaded, whose reply never came (Volume 8,
 * prompt 1). Checking an earlier action is not starting a new one: this only reports what the
 * server says it made; sending again is the learner's own choice, from the usual buttons.
 */
export function EarlierActionNotice({ earlier, noun, changed, found }: {
  earlier: ReturnType<typeof useEarlierAction>;
  /** "submission", "hint request", "code review", "story". */
  noun: string;
  /** What's on screen now isn't what was sent: said, so the learner knows which is which. */
  changed?: string | null;
  /** What to say and offer when it arrived ("Its result is below", a link to it). */
  found: ReactNode;
}) {
  if (earlier.status === "none") return null;
  const when = time(earlier.intent.sentAt);
  return (
    <div className="earlier-action banner banner--info stack-sm" role="status">
      {earlier.status === "checking" && <p>Checking what happened to the {noun} you sent at {when}, before the page reloaded…</p>}
      {earlier.status === "found" && (
        <>
          <p><strong>Your {noun} from {when} arrived.</strong> {found}</p>
          {changed && <p className="subtle">{changed}</p>}
          <span><Button size="sm" variant="ghost" onClick={earlier.dismiss}>Dismiss</Button></span>
        </>
      )}
      {earlier.status === "not_found" && (
        <>
          <p><strong>The {noun} you sent at {when} never arrived.</strong> The server has no record of it, so nothing was
            made. Sending now is a new {noun}.</p>
          <span><Button size="sm" variant="ghost" onClick={earlier.dismiss}>OK</Button></span>
        </>
      )}
      {earlier.status === "in_progress" && (
        <>
          <p><strong>The {noun} you sent at {when} is still being answered.</strong> Nothing has been saved yet, and it
            isn't being sent again. Check again in a moment to see its answer.</p>
          <span className="row">
            <Button size="sm" onClick={earlier.recheck}>Check again</Button>
            <Button size="sm" variant="ghost" onClick={earlier.dismiss}>Dismiss</Button>
          </span>
        </>
      )}
      {earlier.status === "unavailable" && (
        <>
          <p><strong>Couldn't check the {noun} you sent at {when}.</strong> It may have arrived. Sending the same thing
            again is safe: it uses the same key, so it isn't done twice.</p>
          {changed && <p className="subtle">{changed}</p>}
          <span className="row">
            <Button size="sm" onClick={earlier.recheck}>Check again</Button>
            <Button size="sm" variant="ghost" onClick={earlier.dismiss}>Dismiss</Button>
          </span>
        </>
      )}
    </div>
  );
}
