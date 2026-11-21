import { Link } from "react-router-dom";

import { BrowseNote } from "./BrowseNote";
import { CareerSelect } from "./CareerSelect";
import { usePracticeTrack } from "./practiceTrack";

/**
 * The career whose practice is shown, plus, for careers that also have coding problems, a
 * coding/questions switch. Choosing a career here browses it; it never changes the learner's own
 * career (Settings does that). When it isn't their own, one line says so, with the way back.
 */
export function PracticeBar({ view }: { view: "coding" | "questions" }) {
  const { track, career, ownCareer, keep, setTrack } = usePracticeTrack();
  const href = (v: "coding" | "questions") => {
    const next = new URLSearchParams(keep);
    if (v === "questions") next.set("view", "questions");
    const query = next.toString();
    return `/problems${query ? `?${query}` : ""}`;
  };
  const what = view === "coding" ? "coding problems" : "interview questions";
  // The learner's own practice: their coding problems or questions, whichever their career has.
  const ownHasCoding = ownCareer?.has_coding ?? false;
  const back = ownHasCoding && view === "questions" ? "/problems?view=questions" : "/problems";
  return (
    <div className="practice-bar">
      <CareerSelect label="Show practice for" value={track} onChange={setTrack} />
      {career?.has_coding && (
        <nav className="practice-switch" aria-label="Practice type">
          <Link to={href("coding")} aria-current={view === "coding" ? "page" : undefined}>Coding problems</Link>
          <Link to={href("questions")} aria-current={view === "questions" ? "page" : undefined}>Interview questions</Link>
        </nav>
      )}
      <BrowseNote what={what} back={back} backWhat={ownHasCoding ? what : "interview questions"} />
    </div>
  );
}
