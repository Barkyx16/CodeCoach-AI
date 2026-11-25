import { useId, useRef, useState } from "react";
import { useLocation } from "react-router-dom";

import { useCapabilities } from "@/api/queries";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/Button";
import { useOnline } from "@/hooks/useOnline";
import { recentFailures } from "@/lib/supportLog";

import {
  buildSupportReport, MAX_DESCRIPTION, reportFilename, reportText, type ReportedError, type ServerStatement,
} from "./report";

/** How long a downloaded report's temporary address lives: long enough for the browser to start saving. */
const REVOKE_AFTER_MS = 1000;
type Status = { tone: "ok" | "warn"; text: string } | null;

/**
 * The support report: an optional description, the exact report (read-only, selectable), and
 * Copy / Download. What's previewed is the very string that's copied and saved. Nothing is sent
 * anywhere and nothing is kept: closing the page discards it.
 */
export function SupportReportPanel({ problem, pagePath, standalone = false }: {
  problem: ReportedError | null;
  /** The page the problem happened on (masked in the report). */
  pagePath?: string;
  /** On its own page (with headings), rather than under an error message. */
  standalone?: boolean;
}) {
  const location = useLocation();
  const { user, isRestoring } = useAuth();
  const capabilities = useCapabilities();
  const online = useOnline();
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState<Status>(null);
  const [now] = useState(() => new Date());
  const [failures] = useState(recentFailures);
  const preview = useRef<HTMLTextAreaElement>(null);
  const ids = useId();

  // Whose report this is: the session when it opened. If another account signs in meanwhile, the
  // earlier session's failure and requests are left out rather than shown in this one's report.
  const sessionKey = isRestoring ? undefined : (user?.id ?? null);
  const [owner, setOwner] = useState<string | null | undefined>(sessionKey);
  if (owner === undefined && sessionKey !== undefined) setOwner(sessionKey);
  const sameSession = sessionKey === undefined || owner === undefined || owner === sessionKey;

  const server: ServerStatement | "loading" | "unavailable" = capabilities.data
    ? {
        code_judge: capabilities.data.execution?.state ?? null,
        code_judge_reason: capabilities.data.execution?.reason ?? null,
        ai_provider: capabilities.data.ai_provider ?? null,
        emails_delivered: capabilities.data.emails_delivered ?? null,
      }
    // Failed, or waiting for a connection that isn't there: either way the server's status isn't known.
    : capabilities.isError || capabilities.fetchStatus === "paused" ? "unavailable" : "loading";

  const report = buildSupportReport({
    now,
    timeZone: safeTimeZone(),
    build: typeof __CODECOACH_BUILD__ === "string" ? __CODECOACH_BUILD__ : "unknown",
    mode: import.meta.env.PROD ? "production" : "development",
    pathname: pagePath ?? location.pathname,
    userAgent: navigator.userAgent,
    language: navigator.language ?? null,
    online,
    session: isRestoring ? "checking" : user ? (user.is_guest ? "guest" : "signed_in") : "signed_out",
    capabilities: server,
    error: sameSession ? problem : null,
    failures: sameSession ? failures : [],
    description,
  });
  const text = reportText(report);
  const filename = reportFilename(now);

  function selectPreview() {
    preview.current?.focus();
    preview.current?.select();
  }

  async function copy() {
    try {
      if (!navigator.clipboard?.writeText) throw new Error("no clipboard");
      await navigator.clipboard.writeText(text);
      setStatus({ tone: "ok", text: "Copied the report. Paste it wherever you're asking for help; nothing has been sent anywhere." });
    } catch {
      selectPreview();
      setStatus({ tone: "warn", text: "This browser didn't allow copying. The report is selected above: press Ctrl+C (⌘C on a Mac) to copy it." });
    }
  }

  function download() {
    let url: string | null = null;
    try {
      url = URL.createObjectURL(new Blob([text], { type: "application/json" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.hidden = true;
      document.body.append(link);
      link.click();
      link.remove();
      setStatus({ tone: "ok", text: `Your browser was asked to save ${filename} on this device. Nothing has been sent anywhere; sharing the file is up to you.` });
    } catch {
      selectPreview();
      setStatus({ tone: "warn", text: "This browser didn't save the file. The report is selected above: copy it (Ctrl+C, or ⌘C on a Mac) and paste it into a message or a file." });
    } finally {
      if (url) {
        const made = url;
        window.setTimeout(() => URL.revokeObjectURL(made), REVOKE_AFTER_MS);
      }
    }
  }

  const Title = standalone ? "h2" : "p";
  return (
    <div className="support-report stack-sm" role={standalone ? undefined : "region"} aria-label={standalone ? undefined : "Support report"}>
      {!standalone && (
        <p className="subtle">
          A short report you can keep or send to whoever is helping you. It stays on this device until you copy or save it;
          sending it is your choice.
        </p>
      )}
      <div className="field">
        <label className="field__label" htmlFor={`${ids}-description`}>What happened? <span className="subtle">(optional)</span></label>
        <textarea id={`${ids}-description`} className="input" rows={3} maxLength={MAX_DESCRIPTION} value={description}
          onChange={(e) => setDescription(e.target.value.slice(0, MAX_DESCRIPTION))} aria-describedby={`${ids}-description-hint`} />
        <p className="field__hint" id={`${ids}-description-hint`}>
          Don't include passwords, codes from emails, or anything private: it goes into the report exactly as typed.
          {" "}{description.length} of {MAX_DESCRIPTION} characters.
        </p>
      </div>
      <Title className={standalone ? "section-title" : "support-report__title"} id={`${ids}-preview-title`}>
        {standalone ? "The report" : <strong>The report</strong>}
      </Title>
      <p className="subtle" id={`${ids}-preview-hint`}>Exactly what will be copied or saved. Read it first; nothing else is added.</p>
      <textarea ref={preview} className="input support-report__preview" readOnly rows={standalone ? 20 : 12} value={text}
        spellCheck={false} aria-labelledby={`${ids}-preview-title`} aria-describedby={`${ids}-preview-hint`} />
      <div className="row">
        <Button size="sm" onClick={() => void copy()}>Copy the report</Button>
        <Button size="sm" variant="secondary" onClick={download}>Download {filename}</Button>
      </div>
      <p role="status" className={status?.tone === "warn" ? "support-report__status support-report__status--warn" : "support-report__status subtle"}>
        {status?.text ?? ""}
      </p>
    </div>
  );
}

function safeTimeZone(): string | null {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone ?? null;
  } catch {
    return null;
  }
}
