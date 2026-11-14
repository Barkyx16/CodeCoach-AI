import { useEffect, useRef } from "react";

import type { Interview } from "@/api/types";

import { EngagementNote } from "@/features/voice/EngagementMeter";

import { PHASES } from "./phases";

export function Transcript({ turns, pending, showEngagement = false }: {
  turns: Interview["turns"]; pending?: string | null; showEngagement?: boolean;
}) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "end" });
  }, [turns.length, pending]);

  return (
    <div className="transcript" role="log" aria-label="Interview transcript" aria-live="polite">
      {turns.map((t, i) => {
        const prev = turns[i - 1];
        // Mark the start of a new phase above the first message that belongs to it.
        const divider = prev !== undefined && !!t.phase && t.phase !== prev.phase;
        return (
          <div key={t.seq}>
            {divider && <div className="transcript__divider">{PHASES.find((p) => p.id === t.phase)?.label}</div>}
            <div className={`bubble bubble--${t.role}`}>
              <div className="bubble__meta"><span className="bubble__who">{t.role === "interviewer" ? "Interviewer" : "You"}</span><time dateTime={t.created_at}>{new Date(t.created_at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}</time></div>
              <p className="bubble__text">{t.content}</p>
              {t.source && t.source !== "typed" && <p className="bubble__source subtle">{t.source === "voice" ? "Spoken" : "Spoken and edited"}</p>}
              {showEngagement && t.engagement && <EngagementNote engagement={t.engagement} />}
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
