import { useEffect, useRef } from "react";

import type { Interview } from "@/api/types";

import { PHASES } from "./phases";

export function Transcript({ turns, pending }: { turns: Interview["turns"]; pending?: string | null }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "end" });
  }, [turns.length, pending]);

  return (
    <div className="transcript" role="log" aria-label="Interview transcript" aria-live="polite">
      {turns.map((t, i) => {
        const prev = turns[i - 1];
        // Mark the start of a new phase above the first message that belongs to it.
        const divider = prev !== undefined && t.phase !== prev.phase;
        return (
          <div key={t.seq}>
            {divider && <div className="transcript__divider">{PHASES.find((p) => p.id === t.phase)?.label}</div>}
            <div className={`bubble bubble--${t.role}`}>
              <span className="bubble__who">{t.role === "interviewer" ? "Interviewer" : "You"}</span>
              <p className="bubble__text">{t.content}</p>
            </div>
          </div>
        );
      })}
      {pending && (
        <>
          <div className="bubble bubble--candidate bubble--pending">
            <span className="bubble__who">You</span>
            <p className="bubble__text">{pending}</p>
          </div>
          <div className="bubble bubble--interviewer bubble--typing" aria-label="Interviewer is typing">
            <span className="typing"><i /><i /><i /></span>
          </div>
        </>
      )}
      <div ref={end} />
    </div>
  );
}
