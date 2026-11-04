import { useEffect, useRef } from "react";

import { useAnswerFollowup, useSkipFollowup } from "@/api/queries";
import type { AnswerSource, Interview } from "@/api/types";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Icon } from "@/components/Icon";
import { InlineError } from "@/components/States";
import { clearStoredDraft, useStoredDraft } from "@/hooks/useStoredDraft";
import type { useInterviewerVoice } from "@/features/voice/useInterviewerVoice";
import { VoiceComposer } from "@/features/voice/VoiceComposer";

import { reportIgnored, tracedRoundAction } from "./roundDiag";
import { roundDraftKey } from "./roundDrafts";
import { FeedbackKind } from "@/components/FeedbackKind";

type Followup = NonNullable<NonNullable<Interview["round_format"]>["pending_followup"]>;

/** A follow-up question: who's asking (in text), what they asked, and a reply box. One speaker at a time. */
export function FollowupTurn({ iv, followup, voice, readAloud }: {
  iv: Interview;
  followup: Followup;
  voice: ReturnType<typeof useInterviewerVoice>;
  readAloud: boolean;
}) {
  const key = `${roundDraftKey(iv.id, followup.question_index)}:followup`;
  const [draft, setDraft] = useStoredDraft(key);
  const reply = useAnswerFollowup(iv.id);
  const skip = useSkipFollowup(iv.id);
  const heading = useRef<HTMLHeadingElement>(null);
  const busy = reply.isPending || skip.isPending;
  const asker = followup.speaker?.title ?? "Interviewer";
  const parent = iv.questions[followup.question_index];
  const { speak } = voice;

  useEffect(() => {
    heading.current?.focus();
    if (readAloud) speak(followup.question); // speak() stops anything already playing first
  }, [followup.question, readAloud, speak]);

  async function send(source: AnswerSource): Promise<boolean> {
    try {
      await tracedRoundAction("reply", iv.id, followup.question_index, (traceparent) =>
        reply.mutateAsync({ answer: draft.trim(), source, traceparent }));
      clearStoredDraft(key);
      return true;
    } catch {
      return false; // kept in the draft; error shown
    }
  }

  return (
    <div className="stack">
      <Card className="question-page__prompt stack followup-card" role="region" aria-labelledby="followup-title">
        <p className="eyebrow">FOLLOW-UP · {asker.toUpperCase()}</p>
        <h1 className="page__title" id="followup-title" ref={heading} tabIndex={-1}>
          <span className="speaker-label">{asker} asks:</span> {followup.question}
        </h1>
        <FeedbackKind kind="interviewer" />
        {parent && <p className="subtle">About your answer to “{parent.title}”. This asks for one detail ({followup.detail}); it isn't scored separately.</p>}
        {voice.supported && (
          <div className="row">
            {voice.speaking
              ? <Button size="sm" variant="ghost" onClick={voice.stop}><Icon name="stop" size={14} />Stop reading</Button>
              : <Button size="sm" variant="ghost" onClick={() => voice.speak(followup.question)}><Icon name="speaker" size={14} />Read follow-up aloud</Button>}
          </div>
        )}
        <p className="turn-cue" role="status">Your turn: reply to the {asker.toLowerCase()}.</p>
      </Card>
      <VoiceComposer
        id="followup-answer" label="Your reply" value={draft} onChange={setDraft} onSubmit={send}
        submitting={reply.isPending} disabled={busy && !reply.isPending} maxLength={3000} onIgnored={() => reportIgnored("reply")}
        submitLabel="Send reply" placeholder="A sentence or two is enough…" voice={voice}
        hint="Typing works too. The next question comes after you reply or skip." errorId={reply.error ?? skip.error ? "followup-error" : undefined}
        extraActions={<Button type="button" variant="ghost" disabled={busy} loading={skip.isPending} onClick={() => void tracedRoundAction("skip_followup", iv.id, followup.question_index, (traceparent) => skip.mutateAsync(traceparent)).catch(() => undefined)}>Skip follow-up</Button>}
      />
      <InlineError id="followup-error" error={reply.error ?? skip.error} />
    </div>
  );
}
