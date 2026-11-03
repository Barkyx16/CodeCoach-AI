import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useShare, useShareMutation } from "@/api/queries";
import type { ShareCreated, ShareFeedback } from "@/api/types";
import { BackLink } from "@/components/BackLink";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { formatDateTime } from "@/lib/format";

import { FeedbackView } from "./FeedbackView";
import { LinkPanel } from "./LinkPanel";
import { SharedSnapshot } from "./SharedSnapshot";
import { feedbackCount, STATUS_LABEL, STATUS_TONE } from "./shareStatus";

/** One shared answer: link controls, the feedback people left (kept apart from AI feedback), and the snapshot. */
export function ShareDetailPage() {
  const { id = "" } = useParams();
  const share = useShare(id);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const heading = useRef<HTMLHeadingElement>(null);
  const [confirm, setConfirm] = useState<"revoke" | "delete" | null>(null);
  const [newLink, setNewLink] = useState<ShareCreated | null>(null);
  const [announce, setAnnounce] = useState("");
  const action = useShareMutation((name: "close" | "reopen" | "revoke") => api.shareAction(id, name));
  const useful = useShareMutation(({ fid, value }: { fid: string; value: boolean }) => api.markFeedbackUseful(id, fid, value));
  const removeFeedback = useShareMutation((fid: string) => api.deleteFeedback(id, fid));
  const rotate = useMutation({
    mutationFn: () => api.newShareLink(id),
    onSuccess: (created) => {
      setNewLink(created);
      qc.setQueryData(["me", "share", id], created.share);
    },
  });
  const remove = useMutation({
    mutationFn: () => api.deleteShare(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["me", "shares"] });
      qc.removeQueries({ queryKey: ["me", "share", id] });
      navigate("/shares", { replace: true });
    },
  });

  if (share.isPending) return <LoadingState label="Loading the shared answer…" />;
  if (share.isError) return <div className="page"><ErrorState error={share.error} onRetry={() => void share.refetch()} /></div>;
  const s = share.data;
  const live = s.status === "active" || s.status === "closed";

  function cancelConfirm(trigger: string) {
    setConfirm(null);
    window.requestAnimationFrame(() => document.getElementById(trigger)?.focus());
  }

  function deleteOne(item: ShareFeedback) {
    if (!window.confirm(`Delete this feedback from ${item.reviewer.label}? This can't be undone.`)) return;
    removeFeedback.mutate(item.id, {
      onSuccess: () => {
        setAnnounce("Feedback deleted.");
        heading.current?.focus(); // its card (and the focused button) are gone
      },
    });
  }

  return (
    <div className="page share-page">
      <BackLink fallback={{ to: "/shares", label: "All shared answers" }} />
      <div className="page__header">
        <div>
          <p className="eyebrow">SHARED FOR FEEDBACK · {s.career_title.toUpperCase()}</p>
          <h1 className="page__title" ref={heading} tabIndex={-1}>{s.question_title}</h1>
          <p className="row">
            <Badge tone={STATUS_TONE[s.status]}>{STATUS_LABEL[s.status]}</Badge>
            <span className="subtle">
              Shared {formatDateTime(s.created_at)}
              {live ? ` · link works until ${formatDateTime(s.expires_at)}` : ""}
              {s.last_opened_at ? ` · last opened ${formatDateTime(s.last_opened_at)}` : " · not opened yet"}
            </span>
          </p>
        </div>
      </div>
      <p className="visually-hidden" role="status">{announce}</p>

      {s.source_changed && <p className="banner banner--info">Your original answer has changed since you shared it. Reviewers still see the copy you shared.</p>}
      {s.source_missing && <p className="banner banner--info">The original answer is no longer in your history. Reviewers still see the copy you shared.</p>}

      <Card className="stack-sm share-controls">
        <h2 className="section-title">The link</h2>
        {s.status === "revoked" && <p>You turned this link off. It can't be turned back on; share the answer again if you need to. The copy and its feedback stay here until you delete them.</p>}
        {s.status === "expired" && <p>This link has expired. The copy and its feedback stay here until you delete them.</p>}
        {s.status === "closed" && <p>The link still opens, but it isn't taking new feedback.</p>}
        {s.status === "active" && <p>Anyone with the link can see the copy below and leave feedback.</p>}
        <div className="row share-controls__actions">
          {s.status === "active" && <Button size="sm" loading={action.isPending && action.variables === "close"} onClick={() => action.mutate("close")}>Stop taking feedback</Button>}
          {s.status === "closed" && <Button size="sm" loading={action.isPending && action.variables === "reopen"} onClick={() => action.mutate("reopen")}>Take feedback again</Button>}
          {live && <Button size="sm" loading={rotate.isPending} onClick={() => rotate.mutate()}
            title="The old link stops working">Make a new link</Button>}
          {live && <Button size="sm" variant="danger" id="revoke-share" aria-expanded={confirm === "revoke"} onClick={() => setConfirm("revoke")}>Turn the link off</Button>}
          <Button size="sm" variant="ghost" id="delete-share" aria-expanded={confirm === "delete"} onClick={() => setConfirm("delete")}>Delete</Button>
        </div>
        {confirm && (
          <div className="banner banner--warning stack-sm" role="alertdialog" aria-labelledby="share-confirm-title"
            onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); cancelConfirm(confirm === "revoke" ? "revoke-share" : "delete-share"); } }}>
            <strong id="share-confirm-title">{confirm === "revoke" ? "Turn this link off for good?" : "Delete this share and all its feedback?"}</strong>
            <p>{confirm === "revoke"
              ? "Anyone who opens it, including people who already have it, will see that it's turned off. You keep the copy and feedback."
              : "The link stops working and the copy and every piece of feedback on it are deleted. This can't be undone."}</p>
            <span className="row">
              <Button size="sm" variant="danger" autoFocus loading={confirm === "revoke" ? action.isPending : remove.isPending}
                onClick={() => (confirm === "revoke"
                  ? action.mutate("revoke", { onSuccess: () => { setConfirm(null); setAnnounce("Link turned off."); heading.current?.focus(); } })
                  : remove.mutate())}>
                {confirm === "revoke" ? "Turn it off" : "Delete"}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => cancelConfirm(confirm === "revoke" ? "revoke-share" : "delete-share")}>Cancel</Button>
            </span>
          </div>
        )}
        <InlineError error={action.error ?? rotate.error ?? remove.error} />
      </Card>
      {newLink && <LinkPanel created={newLink} />}

      <section className="stack" aria-labelledby="people-feedback">
        <h2 className="section-title" id="people-feedback">Feedback from people ({feedbackCount(s.feedback_count).toLowerCase()})</h2>
        <p className="subtle">
          Written by the people you shared with. It's their opinion: CodeCoach doesn't check it, it doesn't change your
          scores or plan, and it isn't a hiring decision or professional validation. Names are as given, not verified,
          unless marked as a signed-in CodeCoach user.
        </p>
        {s.feedback.length === 0 ? <p className="subtle">{live ? "Nothing yet. Feedback appears here when someone sends it." : "No feedback was left."}</p> : (
          <ul className="share-feedback-list">
            {s.feedback.map((f) => (
              <li key={f.id}>
                <FeedbackView item={f} actions={
                  <span className="row">
                    <Button size="sm" variant={f.useful ? "secondary" : "ghost"} aria-pressed={f.useful}
                      loading={useful.isPending && useful.variables?.fid === f.id}
                      onClick={() => useful.mutate({ fid: f.id, value: !f.useful })}>Useful</Button>
                    <Button size="sm" variant="ghost" loading={removeFeedback.isPending && removeFeedback.variables === f.id}
                      onClick={() => deleteOne(f)}>Delete</Button>
                  </span>
                } />
              </li>
            ))}
          </ul>
        )}
        <InlineError error={useful.error ?? removeFeedback.error} />
      </section>

      <Card className="stack share-copy" role="region" aria-label="What you shared">
        <p className="eyebrow">WHAT YOU SHARED (A FIXED COPY)</p>
        <SharedSnapshot view={s.view} idPrefix="owner" />
        <p className="subtle"><Link to={`/history`}>Your full history</Link> isn't shared.</p>
      </Card>
    </div>
  );
}
