import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import type { ContentKind, ReportCategory } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/Button";
import { InlineError } from "@/components/States";

import { CATEGORY_LABEL } from "./labels";

const MAX_DETAILS = 2000;
const MAX_EXCERPT = 1500;

/**
 * "Report an issue": a small disclosure with a category, an optional description and, only if
 * the learner ticks it and reviews it, an excerpt of their own answer. The content id and the
 * version on screen are attached automatically; nothing else is.
 */
export function ReportIssue({ type, id, version, context = "content", answerId, excerptSource, label }: {
  type: ContentKind;
  id: string;
  version: number;
  context?: "content" | "feedback";
  answerId?: string;
  /** Text the learner may choose to attach (e.g. their answer). Never sent unless they opt in. */
  excerptSource?: string;
  label?: string;
}) {
  const { isAuthenticated } = useAuth();
  const qc = useQueryClient();
  const formId = useId();
  const toggle = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState<ReportCategory | "">("");
  const [details, setDetails] = useState("");
  const [attach, setAttach] = useState(false);
  const [excerpt, setExcerpt] = useState("");
  const send = useMutation({
    mutationFn: () => api.report({
      content_type: type, content_id: id, content_version: version, category: category as ReportCategory,
      details: details.trim(), context, answer_id: answerId ?? null, excerpt: attach && excerpt.trim() ? excerpt.trim() : null,
    }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["me", "reports"] }),
  });
  const already = send.error instanceof ApiError && send.error.code === "already_reported";
  const buttonText = label ?? (context === "feedback" ? "Report a problem with this feedback" : "Report an issue");

  function close() {
    setOpen(false);
    send.reset();
    window.requestAnimationFrame(() => toggle.current?.focus());
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    if (category) send.mutate();
  }

  return (
    <div className="report-issue">
      <button type="button" ref={toggle} className="link-button report-issue__toggle" aria-expanded={open} aria-controls={formId}
        onClick={() => (open ? close() : setOpen(true))}>
        {buttonText}
      </button>
      {open && (
        <div id={formId} className="card stack-sm report-issue__panel">
          {!isAuthenticated ? (
            <p>Sign in to report an issue, so you can follow what happens to it. <Link to="/login">Sign in</Link></p>
          ) : send.isSuccess ? (
            <div className="stack-sm" role="status">
              <p><strong>Thanks, it's been reported.</strong> Someone looks at reports by hand; there's no set time. You can follow it in <Link to="/reports">your reports</Link>.</p>
              <span><Button size="sm" onClick={close}>Close</Button></span>
            </div>
          ) : (
            <form className="stack-sm" onSubmit={submit} aria-label={buttonText}>
              <fieldset className="field">
                <legend className="field__label">What's wrong?</legend>
                <div className="report-issue__categories">
                  {(Object.keys(CATEGORY_LABEL) as ReportCategory[]).map((c) => (
                    <label key={c} className="checkbox">
                      <input type="radio" name={`${formId}-category`} value={c} checked={category === c} onChange={() => setCategory(c)} />
                      {CATEGORY_LABEL[c]}
                    </label>
                  ))}
                </div>
              </fieldset>
              <label className="field">
                <span className="field__label">Details <span className="subtle">(optional)</span></span>
                <textarea className="input" rows={3} maxLength={MAX_DETAILS} value={details} onChange={(e) => setDetails(e.target.value)}
                  placeholder="What's confusing or wrong, and what would be right?" aria-describedby={`${formId}-attached`} />
              </label>
              {excerptSource && (
                <div className="stack-sm">
                  <label className="checkbox">
                    <input type="checkbox" checked={attach} onChange={(e) => { setAttach(e.target.checked); if (e.target.checked && !excerpt) setExcerpt(excerptSource.slice(0, MAX_EXCERPT)); }} />
                    Attach part of my answer (you can edit it first)
                  </label>
                  {attach && (
                    <label className="field">
                      <span className="field__label">Excerpt to attach</span>
                      <textarea className="input" rows={4} maxLength={MAX_EXCERPT} value={excerpt} onChange={(e) => setExcerpt(e.target.value)} />
                    </label>
                  )}
                </div>
              )}
              <p className="subtle" id={`${formId}-attached`}>
                Sent with it: which {type === "question" ? "question" : "problem"} this is and its version ({version}){attach ? ", and the excerpt above" : ""}.
                Not sent: your other answers, recordings or anything else from your account. A report never changes a score.
              </p>
              {already ? (
                <p className="banner banner--info" role="status">You've already reported this and it's still open. <Link to="/reports">See its status</Link>.</p>
              ) : <InlineError error={send.error} />}
              <span className="row">
                <Button type="submit" variant="primary" size="sm" loading={send.isPending} disabled={!category}>Send report</Button>
                <Button size="sm" variant="ghost" onClick={close}>Cancel</Button>
              </span>
            </form>
          )}
        </div>
      )}
    </div>
  );
}
