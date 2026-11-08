import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { useVerificationStatus } from "@/api/queries";
import type { User, VerificationStatus, VerifyLinkResult } from "@/api/types";
import { announceVerified, forgetVerifyNext, rememberVerifyNext, verifyNextFor } from "@/auth/emailVerified";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/Button";
import { Field } from "@/components/Field";
import { InlineError, LoadingState } from "@/components/States";
import { describeError } from "@/lib/errors";
import { formatDateTime } from "@/lib/format";
import { safeReturnPath } from "@/lib/links";

import { AuthLayout } from "./AuthLayout";
import { EmailNotSentNote } from "./EmailNotSentNote";

/** A link's token: 43 URL-safe characters. Anything else was cut short or changed on the way. */
const TOKEN_SHAPE = /^[A-Za-z0-9_-]{43}$/;
const MALFORMED =
  "This link is incomplete. Mail apps sometimes break long links: open it from the email again, or enter the " +
  "6-digit code from the same email instead.";

/** Where to go once confirmed: the page that sent the learner here (an in-app path, never this
 * page), else where this account was going when it was asked (a link opened in a new tab), else
 * the dashboard. */
function useNext(userId: string | undefined): { asked: string; next: string } {
  const asked = safeReturnPath((useLocation().state as { next?: unknown } | null)?.next, "", ["/verify-email"]);
  return { asked, next: asked || verifyNextFor(userId) || "/dashboard" };
}

const time = (iso: string) => new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });

/**
 * "Check your email". Verifies either with the link from the email (#token=..., works even when
 * signed out) or with the 6-digit code typed in while signed in.
 */
function tokenInHash(): string | null {
  const params = new URLSearchParams(window.location.hash.slice(1));
  return params.has("token") ? (params.get("token") ?? "") : null;
}

/** Take the token out of the address bar (and history): it's a credential until it's used. */
function clearHash() {
  if (window.location.hash) {
    window.history.replaceState(window.history.state, "", window.location.pathname + window.location.search);
  }
}

export function VerifyEmailPage() {
  // `opened` counts links opened here, so the same link opened again is checked again.
  const [link, setLink] = useState(() => ({ token: tokenInHash(), opened: 0 }));
  useEffect(() => {
    clearHash();
    // A link pasted into a tab already on this page changes only the #token part: no new page.
    const onHashChange = () => {
      const token = tokenInHash();
      if (token === null) return;
      setLink((current) => ({ token, opened: current.opened + 1 }));
      clearHash();
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);
  return (
    <AuthLayout>
      {link.token !== null ? <VerifyByLink key={link.opened} token={link.token} /> : <VerifyByCode />}
    </AuthLayout>
  );
}

// --- The link from the email ------------------------------------------------------------------

type LinkState =
  | { kind: "working" }
  | { kind: "done"; result: VerifyLinkResult }
  | { kind: "ask"; linkFor: string } // another account's link, while signed in: asked before using it
  | { kind: "unusable"; reason: string; account: string; message: string }
  | { kind: "error"; error: unknown }; // couldn't reach the server, or it couldn't answer

const UNUSABLE_TITLES: Record<string, string> = {
  malformed: "This link is incomplete",
  unknown: "We don't recognise this link",
  expired: "This link has expired",
  superseded: "A newer email replaced this link",
  already_verified: "This email is already confirmed",
  address_changed: "This link is for an earlier request",
  stopped: "This link no longer works",
};

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="card auth__card stack" aria-labelledby="verify-title">
      <h1 className="page__title" id="verify-title">{title}</h1>
      {children}
    </div>
  );
}

function VerifyByLink({ token }: { token: string }) {
  const { user, isRestoring, setUser, logout } = useAuth();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [state, setState] = useState<LinkState>(() =>
    TOKEN_SHAPE.test(token)
      ? { kind: "working" }
      : { kind: "unusable", reason: "malformed", account: "signed_out", message: MALFORMED },
  );
  const sent = useRef(false); // the link is single-use: never send it twice by accident (StrictMode)
  const signedIn = useRef(user !== null);
  useEffect(() => {
    signedIn.current = user !== null;
  }, [user]);

  const send = useCallback(async (otherAccountOk: boolean) => {
    try {
      const result = await api.verifyEmailLink(token, otherAccountOk);
      if (result.account === "this" && result.user) {
        setUser(result.user);
        announceVerified(result.user.id); // this browser's other tabs move on too
      } else if (result.account === "signed_out" && signedIn.current) {
        // Sent without the session (its access token had just expired): read the account again.
        void api.me().then((me) => {
          setUser(me);
          if (me.email_verified && !me.pending_email) announceVerified(me.id);
        }, () => {});
      }
      void queryClient.invalidateQueries({ queryKey: ["verification-status"] });
      setState({ kind: "done", result });
    } catch (error) {
      if (error instanceof ApiError && error.code === "verification_link_other_account") {
        setState({ kind: "ask", linkFor: String((error.details as { link_for?: string } | null)?.link_for ?? "") });
      } else if (error instanceof ApiError && error.code === "invalid_verification_token") {
        const d = (error.details ?? {}) as { reason?: string; account?: string };
        setState({ kind: "unusable", reason: d.reason ?? "unknown", account: d.account ?? "signed_out", message: error.message });
      } else {
        setState({ kind: "error", error });
      }
    }
  }, [token, setUser, queryClient]);

  // Wait for the session check: signed in, the server can tell whose link this is.
  useEffect(() => {
    if (isRestoring || sent.current || !TOKEN_SHAPE.test(token)) return;
    sent.current = true;
    void send(false);
  }, [isRestoring, token, send]);

  const again = (otherAccountOk: boolean) => {
    setState({ kind: "working" });
    void send(otherAccountOk);
  };
  const next = verifyNextFor(user?.id) || "/dashboard";
  const continueLink = (label = "Continue") => (
    <Link className="btn btn--primary btn--md" to={next} onClick={forgetVerifyNext}>{label}</Link>
  );
  const signedInAs = user?.email ? <strong>{user.email}</strong> : "a guest";
  const switchAccounts = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  if (state.kind === "working") return <Card title="Confirm your email"><LoadingState label="Confirming your email…" /></Card>;

  if (state.kind === "done") {
    const { result } = state;
    if (result.account === "other") {
      return (
        <Card title="That account's email is confirmed">
          <p className="banner banner--success" role="status">Confirmed {result.email_masked} for the other account.</p>
          <p className="muted">You're still signed in as {signedInAs}. Nothing about this account changed.</p>
          {continueLink(user?.email ? `Continue as ${user.email}` : "Continue")}
          <Button variant="ghost" onClick={() => void switchAccounts()}>Sign out to use the other account</Button>
        </Card>
      );
    }
    return (
      <Card title={result.changed_email ? "Your new email is confirmed" : "Your email is confirmed"}>
        <p className="banner banner--success" role="status">
          {result.changed_email
            ? `Your account now uses ${result.email_masked} to sign in and for notices.`
            : `${result.email_masked} is confirmed. Thanks!`}
        </p>
        {user ? continueLink() : <Link className="btn btn--primary btn--md" to="/login">Sign in to continue</Link>}
      </Card>
    );
  }

  if (state.kind === "ask") {
    return (
      <Card title="This link is for a different account">
        <p role="status">
          You're signed in as {signedInAs}. This link confirms the email of another account
          {state.linkFor ? ` (${state.linkFor})` : ""}. Nothing has changed yet.
        </p>
        <p className="muted">Confirming it doesn't sign you in to that account, and doesn't change this one.</p>
        <Button variant="primary" onClick={() => again(true)}>Confirm that account's email</Button>
        <Link className="subtle" to="/dashboard">Don't use it</Link>
      </Card>
    );
  }

  if (state.kind === "error") {
    return (
      <Card title="Confirm your email">
        <p role="alert">We couldn't confirm it just now. {describeError(state.error).message}</p>
        <Button variant="primary" onClick={() => again(false)}>Try again</Button>
      </Card>
    );
  }

  // A link that can't be used: say why, and offer the way on that fits who's here.
  const { reason, account, message } = state;
  const ownEmailDone = user && user.email_verified && !user.pending_email;
  let actions: ReactNode;
  if (reason === "already_verified") {
    actions = account === "other"
      ? <><p className="muted">It belongs to a different account than the one you're signed in to ({signedInAs}).</p>{continueLink()}</>
      : user ? continueLink() : <Link className="btn btn--primary btn--md" to="/login">Sign in</Link>;
  } else if (account === "other") {
    actions = (
      <>
        <p className="muted">
          It was for a different account than the one you're signed in to ({signedInAs}). To get a new one, sign in to
          that account.
        </p>
        {continueLink(user?.email ? `Continue as ${user.email}` : "Continue")}
      </>
    );
  } else if (!user) {
    actions = (
      <Link className="btn btn--primary btn--md" to="/login" state={{ from: "/verify-email" }}>
        Sign in to get a new code
      </Link>
    );
  } else if (ownEmailDone) {
    actions = <><p className="muted">Your email, {user.email}, is already confirmed.</p>{continueLink()}</>;
  } else {
    actions = (
      <Link className="btn btn--primary btn--md" to="/verify-email">
        {reason === "malformed" ? "Enter the code instead" : "Get a new code"}
      </Link>
    );
  }
  return (
    <Card title={UNUSABLE_TITLES[reason] ?? "This link doesn't work"}>
      <p role="alert">{message}</p>
      {actions}
    </Card>
  );
}

// --- The code, signed in ----------------------------------------------------------------------

function VerifyByCode() {
  const { user, isRestoring } = useAuth();
  if (isRestoring) return <LoadingState label="Loading…" />;
  if (!user || user.is_guest || !user.email) {
    return (
      <div className="card auth__card stack">
        <h1 className="page__title">Confirm your email</h1>
        <p className="muted">Sign in to enter the code from your email, or open the link in that email.</p>
        <Link className="btn btn--primary btn--md" to="/login" state={{ from: "/verify-email" }}>Sign in</Link>
      </div>
    );
  }
  return <ConfirmEmail user={user} />;
}

function ConfirmEmail({ user }: { user: User }) {
  const { setUser, logout } = useAuth();
  const navigate = useNavigate();
  const { asked, next } = useNext(user.id);
  const returnBack = (useLocation().state as { returnBack?: unknown } | null)?.returnBack === true;
  // A pending change is confirmed by the new address; until then the account keeps its email.
  const pending = user.pending_email ?? null;
  const waiting = !user.email_verified || !!pending;
  // Was this page waiting when it opened? Then a confirmation it didn't make came from elsewhere.
  const [startedWaiting] = useState(waiting);
  const [confirmedHere, setConfirmedHere] = useState(false);
  const status = useVerificationStatus(user.id, waiting);
  const s = status.data;

  // Keep where the learner was going, so a link opened in another tab can continue there.
  useEffect(() => {
    if (asked) rememberVerifyNext(user.id, asked);
  }, [user.id, asked]);
  // Confirmed in another tab or on another device (the status says so on focus): refresh the account.
  const confirmedElsewhere = waiting && s?.state === "verified";
  useEffect(() => {
    if (confirmedElsewhere) void api.me().then(setUser, () => {});
  }, [confirmedElsewhere, setUser]);

  if (!waiting) {
    return (
      <div className="card auth__card stack" aria-labelledby="verify-title">
        <h1 className="page__title" id="verify-title">Your email is confirmed</h1>
        <p className="banner banner--success" role="status">
          {user.email} is verified.
          {startedWaiting && !confirmedHere && " You confirmed it in another tab or on another device."}
        </p>
        <Link className="btn btn--primary btn--md" to={next} onClick={forgetVerifyNext}>Continue</Link>
      </div>
    );
  }
  return (
    <CodeForm user={user} pending={pending} status={s} refetch={() => void status.refetch()}
      statusUpdatedAt={status.dataUpdatedAt} next={next}
      onConfirmed={(verified) => {
        setConfirmedHere(true);
        setUser(verified);
        announceVerified(verified.id);
        forgetVerifyNext();
        // Opened from Settings (the previous page): go back to it, rather than adding a second
        // copy of it on top (Back then seemed to do nothing). Otherwise, on to `next`.
        if (returnBack && asked === next) navigate(-1);
        else navigate(next, { replace: true });
      }}
      onSignOut={async () => {
        await logout();
        navigate("/", { replace: true });
      }} />
  );
}

function DeliveryLine({ status }: { status: VerificationStatus }) {
  const d = status.delivery;
  if (!d) return null;
  switch (d.state) {
    case "queued":
      return <>Sending it now{d.requested_at ? ` (asked for at ${time(d.requested_at)})` : ""}. This updates when it has gone out.</>;
    case "retrying":
      return (
        <>
          Not sent yet: the first try didn't go through. It's tried again automatically
          {d.next_try_at ? ` (next try around ${time(d.next_try_at)})` : ""}.
        </>
      );
    case "sent_to_provider":
      return (
        <>
          Sent{d.updated_at ? ` at ${time(d.updated_at)}` : ""}: our mail server handed it to your email provider. We can't
          see whether it has reached your inbox.
        </>
      );
    case "kept_locally":
      return <>Not emailed: this copy of CodeCoach keeps emails on the computer running it (see below).</>;
    case "failed":
      return (
        <>
          We couldn't send it{d.updated_at ? ` (we stopped trying at ${time(d.updated_at)})` : ""}. Send a new code; if that
          doesn't arrive either, try again later.
        </>
      );
    default:
      return <>We have no record of the latest email. If it isn't in your inbox, send a new code.</>;
  }
}

function CodeForm({ user, pending, status, statusUpdatedAt, refetch, next, onConfirmed, onSignOut }: {
  user: User;
  pending: string | null;
  status: VerificationStatus | undefined;
  statusUpdatedAt: number;
  refetch: () => void;
  next: string;
  onConfirmed: (user: User) => void;
  onSignOut: () => Promise<void>;
}) {
  const { setUser } = useAuth();
  const [code, setCode] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [resending, setResending] = useState(false);
  const resendInFlight = useRef(false);
  const [resendNote, setResendNote] = useState<string | null>(null);
  const [resendError, setResendError] = useState<unknown>(null);
  const [showFull, setShowFull] = useState(false);
  // The server's resend cooldown: from the status on load, or from a 202/429 since. "Send a new
  // code" waits until then, with a visible countdown.
  const [waitUntil, setWaitUntil] = useState<number | null>(null);
  const statusUntil = status && status.resend_available_in_seconds > 0
    ? statusUpdatedAt + status.resend_available_in_seconds * 1000
    : 0;
  const until = Math.max(waitUntil ?? 0, statusUntil);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!until) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [until]);
  // `now` ticks once a second; a status fetched since is newer than it, so count from whichever is later.
  const secondsLeft = until ? Math.max(0, Math.ceil((until - Math.max(now, statusUpdatedAt)) / 1000)) : 0;
  const startCooldown = (seconds: number) => {
    setNow(Date.now());
    setWaitUntil(Date.now() + seconds * 1000);
  };

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onConfirmed(await api.verifyEmailCode(code));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    // One request at a time, however often it's pressed (a ref: two clicks in one frame both see
    // `resending` still false).
    if (resendInFlight.current) return;
    resendInFlight.current = true;
    setResending(true);
    setResendNote(null);
    setResendError(null);
    try {
      setResendNote((await api.resendVerification()).message);
      setCode("");
      setError(null);
      startCooldown(60);
      refetch();
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        // A code went out under a minute ago (perhaps from another tab), or too many tries from
        // this network: say so, and wait as long as the server asked.
        setResendNote(err.message);
        startCooldown(err.retryAfterSeconds ?? 60);
      } else if (err instanceof ApiError && err.code === "already_verified") {
        void api.me().then(setUser, () => {}); // confirmed elsewhere meanwhile: show that
      } else {
        setResendError(err); // nothing was queued: the button stays, to try again
      }
    } finally {
      resendInFlight.current = false;
      setResending(false);
    }
  }

  const attemptsLeft = error instanceof ApiError
    ? (error.details as { attempts_left?: number } | null)?.attempts_left
    : undefined;
  const tries = attemptsLeft === undefined ? "" : `${attemptsLeft} ${attemptsLeft === 1 ? "try" : "tries"} left.`;
  const codeError = attemptsLeft === undefined
    ? undefined
    : error instanceof ApiError && error.code === "superseded_verification_code"
      ? `${error.message} ${tries}`
      : `That code isn't right. ${tries}`;
  const full = pending ?? user.email ?? "";
  const shown = showFull ? full : (status?.address_masked ?? "your email address");
  const deliveryState = status?.delivery?.state;

  return (
    <form className="card auth__card stack" onSubmit={onSubmit} noValidate aria-labelledby="verify-title">
      <h1 className="page__title" id="verify-title">{pending ? "Confirm your new email" : "Check your email"}</h1>
      <p className="muted">
        We send a 6-digit code to <strong data-testid="verify-destination">{shown}</strong>{" "}
        <button type="button" className="link-button" aria-pressed={showFull} onClick={() => setShowFull((v) => !v)}>
          {showFull ? "Hide full address" : "Show full address"}
        </button>
        . Enter it below, or open the link in the same email.
      </p>
      {status && (
        <p className="verify-delivery" role="status" data-testid="delivery-status">
          <DeliveryLine status={status} />
        </p>
      )}
      {status && (status.code_expires_at
        ? (
          <p className="subtle">
            The newest code and link work until {formatDateTime(status.code_expires_at)}. Each new email replaces the
            one before, so only the newest one works.
          </p>
        )
        : deliveryState !== "queued" && deliveryState !== "retrying" && (
          <p className="subtle">Your last code no longer works. Send a new one below.</p>
        ))}
      {pending && (
        <p className="muted" data-testid="pending-email-note">
          Until you enter it, your account keeps using <strong>{user.email}</strong> to sign in and for notices.
        </p>
      )}
      <EmailNotSentNote what="code (and the link)" transport={status?.transport} />
      <Field label="Verification code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]*"
        maxLength={6} required value={code} className="input code-input"
        onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
        error={codeError} />
      {attemptsLeft === undefined && <InlineError error={error} />}
      <Button type="submit" variant="primary" loading={busy} disabled={code.length !== 6}>Verify email</Button>
      <div className="auth__alt">
        <Button variant="ghost" onClick={() => void resend()} loading={resending} disabled={secondsLeft > 0}>
          {resending ? "Sending a new code…" : secondsLeft > 0 ? `Send a new code (in ${secondsLeft} s)` : "Send a new code"}
        </Button>
        <span className="subtle" role="status">{resendNote}</span>
        <InlineError error={resendError} />
        <details className="verify-help">
          <summary>Not in your inbox?</summary>
          <ul>
            <li>Look in spam or junk, and search your mail for “CodeCoach AI”.</li>
            <li>Check the address above (use “Show full address”). A typo means the code went somewhere else.</li>
            <li>
              {pending
                ? <>Wrong address? <Link to="/settings">Change or cancel it in Settings</Link>.</>
                : <>Wrong address? <Link to="/settings">Change it in Settings</Link> (you'll need your password).</>}
            </li>
            <li>Send a new code: only the newest email's code and link work.</li>
            <li>
              Still nothing? You can carry on and confirm later, or{" "}
              <button type="button" className="link-button" onClick={() => void onSignOut()}>sign out</button>.
            </li>
          </ul>
        </details>
        <Link to={next} className="subtle">Do this later</Link>
      </div>
    </form>
  );
}
