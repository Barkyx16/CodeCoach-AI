import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { useSharedView } from "@/api/queries";
import type { FeedbackReceipt, RecipientView } from "@/api/types";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { InlineError, LoadingState } from "@/components/States";
import { formatDateTime } from "@/lib/format";

import { FeedbackView } from "./FeedbackView";
import { SharedSnapshot } from "./SharedSnapshot";

const MAX_FIELD = 1500;
const MAX_COMMENTS = 8;

function newRequestId(): string {
  try {
    return crypto.randomUUID();
  } catch {
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
  }
}

/** The link's secret lives in the URL fragment (#t=…), which browsers never send to a server. */
function tokenFrom(hash: string): string {
  return new URLSearchParams(hash.replace(/^#/, "")).get("t") ?? "";
}

/** Keep this page out of search engines and never leak its address in a Referer header. */
function usePrivatePage() {
  useEffect(() => {
    const added = [["robots", "noindex, nofollow"], ["referrer", "no-referrer"]].map(([name, content]) => {
      const meta = document.createElement("meta");
      meta.name = name!;
      meta.content = content!;
      document.head.appendChild(meta);
      return meta;
    });
    return () => added.forEach((m) => m.remove());
  }, []);
}

const UNAVAILABLE: Record<string, { title: string; body: string }> = {
  share_revoked: { title: "This link was turned off", body: "The person who shared it turned it off, so the answer isn't available any more." },
  share_expired: { title: "This link has expired", body: "Shared answers are only available for a limited time. Ask the person who sent it for a new link if they'd still like feedback." },
  share_not_found: { title: "This link doesn't work", body: "Check that the whole link was copied. If it was, it may have been replaced by a newer one." },
};

/** What a reviewer sees: the shared copy and a short, structured way to give feedback. */
export function SharedPage() {
  usePrivatePage();
  const token = tokenFrom(useLocation().hash);
  const shared = useSharedView(token);

  if (!token) return <Unavailable code="share_not_found" />;
  if (shared.isPending) return <LoadingState label="Opening the shared answer…" />;
  if (shared.isError) {
    const code = shared.error instanceof ApiError ? shared.error.code : "";
    if (code in UNAVAILABLE) return <Unavailable code={code} />;
    return (
      <div className="page share-page">
        <InlineError error={shared.error} />
        <Button onClick={() => void shared.refetch()}>Try again</Button>
      </div>
    );
  }
  return <Shared token={token} data={shared.data} />;
}

function Unavailable({ code }: { code: string }) {
  const copy = UNAVAILABLE[code] ?? UNAVAILABLE.share_not_found!;
  return (
    <div className="page share-page">
      <div className="page__header"><div>
        <p className="eyebrow">SHARED ANSWER</p>
        <h1 className="page__title">{copy.title}</h1>
        <p className="page__subtitle">{copy.body}</p>
      </div></div>
      <p><Link to="/">Go to CodeCoach</Link></p>
    </div>
  );
}

function Shared({ token, data }: { token: string; data: RecipientView }) {
  const { view } = data;
  return (
    <div className="page share-page">
      <div className="page__header">
        <div>
          <p className="eyebrow">SHARED PRIVATELY FOR FEEDBACK</p>
          <h1 className="page__title">A practice answer to review</h1>
          <p className="page__subtitle">A CodeCoach learner asked you for feedback on this {view.kind === "interview_answer" ? "mock-interview" : "practice"} answer.</p>
        </div>
      </div>
      <p className="banner banner--info">
        Anyone with this link can see this page until {formatDateTime(data.expires_at)}, unless the learner turns it off sooner.
        Please don't pass it on.
      </p>
      <div className="share-review">
        <Card className="stack" role="region" aria-label="The shared answer">
          <SharedSnapshot view={view} idPrefix="shared" />
        </Card>
        {data.status === "closed"
          ? <Card className="stack-sm"><h2 className="section-title">Not taking feedback</h2><p>The learner has stopped taking feedback on this answer. You can still read it.</p></Card>
          : <FeedbackForm token={token} data={data} />}
      </div>
    </div>
  );
}

function FeedbackForm({ token, data }: { token: string; data: RecipientView }) {
  const { view } = data;
  const requestId = useRef(newRequestId());
  const [fields, setFields] = useState({ clear: "", needs_evidence: "", next_step: "" });
  const [comments, setComments] = useState<{ sentence: number; text: string }[]>([]);
  const [sentence, setSentence] = useState<number>(view.excerpt[0]?.index ?? 0);
  const [commentText, setCommentText] = useState("");
  const [guestName, setGuestName] = useState("");
  const [receipt, setReceipt] = useState<FeedbackReceipt | null>(null);
  const done = useRef<HTMLHeadingElement>(null);
  const send = useMutation({
    mutationFn: () => api.sendFeedback({ token, client_request_id: requestId.current, ...fields, comments, guest_name: guestName.trim() }),
    onSuccess: (r) => {
      setReceipt(r);
      requestId.current = newRequestId(); // the next one is new feedback, not a retry
      window.requestAnimationFrame(() => done.current?.focus());
    },
  });
  const empty = !fields.clear.trim() && !fields.needs_evidence.trim() && !fields.next_step.trim() && comments.length === 0;
  const quote = (i: number) => view.excerpt.find((s) => s.index === i)?.text ?? "";

  if (receipt) {
    return (
      <section className="stack" aria-labelledby="sent-title">
        <h2 className="section-title" id="sent-title" ref={done} tabIndex={-1}>Thanks, your feedback was sent</h2>
        <p className="subtle">This is what the learner sees. Only they can read it.</p>
        <FeedbackView item={receipt.feedback} />
        <Button onClick={() => { setReceipt(null); setFields({ clear: "", needs_evidence: "", next_step: "" }); setComments([]); }}>Add more feedback</Button>
      </section>
    );
  }

  function addComment() {
    if (!commentText.trim() || comments.length >= MAX_COMMENTS) return;
    setComments([...comments, { sentence, text: commentText.trim() }]);
    setCommentText("");
  }

  return (
    <section className="card stack" aria-labelledby="give-title">
      <h2 className="section-title" id="give-title">Your feedback</h2>
      <p className="subtle" id="feedback-about">
        It goes only to the learner who shared this. It's your personal view: it doesn't change their score and isn't an official verdict.
        A sentence or two in any box is plenty.
      </p>
      {data.reviewer
        ? <p>You're signed in, so this will be shown as from <strong>{data.reviewer.label}</strong>.</p>
        : (
          <label className="field">
            <span className="field__label">Your name <span className="subtle">(optional)</span></span>
            <input className="input" maxLength={60} value={guestName} onChange={(e) => setGuestName(e.target.value)} aria-describedby="guest-hint" autoComplete="name" />
            <span className="field__hint" id="guest-hint">Shown to the learner as a guest name they can't verify. Leave it empty to stay anonymous.</span>
          </label>
        )}
      {(["clear", "needs_evidence", "next_step"] as const).map((key, i) => (
        <label className="field" key={key}>
          <span className="field__label">{view.prompts[i]}</span>
          <textarea className="input" rows={3} maxLength={MAX_FIELD} value={fields[key]}
            onChange={(e) => setFields({ ...fields, [key]: e.target.value })} />
        </label>
      ))}

      <fieldset className="field share-comment-form">
        <legend className="field__label">Comment on a sentence <span className="subtle">(optional, up to {MAX_COMMENTS})</span></legend>
        {comments.length > 0 && (
          <ul className="share-comments" aria-label="Your comments">
            {comments.map((c, i) => (
              <li key={i}>
                <blockquote className="share-comments__quote"><span className="subtle">Sentence {c.sentence + 1}:</span> {quote(c.sentence)}</blockquote>
                <p>{c.text}</p>
                <Button size="sm" variant="ghost" aria-label={`Remove comment ${i + 1}`} onClick={() => setComments(comments.filter((_, j) => j !== i))}>Remove</Button>
              </li>
            ))}
          </ul>
        )}
        {comments.length < MAX_COMMENTS && (
          <div className="stack-sm">
            <label className="field">
              <span className="field__label">Sentence</span>
              <select className="select" value={sentence} onChange={(e) => setSentence(Number(e.target.value))}>
                {view.excerpt.map((s) => <option key={s.index} value={s.index}>{`${s.index + 1}. ${s.text.length > 70 ? `${s.text.slice(0, 70)}…` : s.text}`}</option>)}
              </select>
            </label>
            <label className="field">
              <span className="field__label">Your comment</span>
              <textarea className="input" rows={2} maxLength={600} value={commentText} onChange={(e) => setCommentText(e.target.value)} />
            </label>
            <span><Button size="sm" onClick={addComment} disabled={!commentText.trim()}>Add comment</Button></span>
          </div>
        )}
      </fieldset>

      <InlineError id="feedback-error" error={send.error} />
      <Button variant="primary" loading={send.isPending} disabled={empty} aria-describedby="feedback-about"
        onClick={() => send.mutate()}>Send feedback</Button>
      {empty && <p className="subtle">Write in at least one box, or add a comment, to send.</p>}
    </section>
  );
}
