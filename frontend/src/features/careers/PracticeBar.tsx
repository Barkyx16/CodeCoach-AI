import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { InlineError } from "@/components/States";

import { CareerSelect } from "./CareerSelect";
import { usePracticeTrack } from "./practiceTrack";

/** "Practicing for: [job]" plus, for jobs that also have coding problems, a coding/questions switch. */
export function PracticeBar({ view }: { view: "coding" | "questions" }) {
  const { track, career, setTrack } = usePracticeTrack();
  const [params] = useSearchParams();
  const [error, setError] = useState<unknown>(null);
  const href = (v: "coding" | "questions") => {
    const next = new URLSearchParams();
    if (params.get("career")) next.set("career", params.get("career")!);
    if (v === "questions") next.set("view", "questions");
    const query = next.toString();
    return `/problems${query ? `?${query}` : ""}`;
  };
  return (
    <div className="practice-bar">
      <CareerSelect label="Practicing for" value={track}
        onChange={(slug) => { setError(null); setTrack(slug).catch(setError); }} />
      {career?.has_coding && (
        <nav className="practice-switch" aria-label="Practice type">
          <Link to={href("coding")} aria-current={view === "coding" ? "page" : undefined}>Coding problems</Link>
          <Link to={href("questions")} aria-current={view === "questions" ? "page" : undefined}>Interview questions</Link>
        </nav>
      )}
      <InlineError error={error} />
    </div>
  );
}
