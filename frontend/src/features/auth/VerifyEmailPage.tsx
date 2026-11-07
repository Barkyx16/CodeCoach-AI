import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/Button";
import { Field } from "@/components/Field";
import { InlineError, LoadingState } from "@/components/States";

import { AuthLayout } from "./AuthLayout";
import { EmailNotSentNote } from "./EmailNotSentNote";

/** Where to go afterwards: whatever page sent the user here, else the dashboard. */
function useNext(): string {
  return (useLocation().state as { next?: string } | null)?.next ?? "/dashboard";
}

/**
 * "Check your email". Verifies either with the link from the email (#token=..., works even when
 * signed out) or with the 6-digit code typed in while signed in.
 */
export function VerifyEmailPage() {
  const [linkToken] = useState(() => new URLSearchParams(window.location.hash.slice(1)).get("token"));
  useEffect(() => {
    if (window.location.hash) {
      window.history.replaceState(window.history.state, "", window.location.pathname + window.location.search);
    }
  }, []);
  return <AuthLayout>{linkToken ? <VerifyByLink token={linkToken} /> : <VerifyByCode />}</AuthLayout>;
}

function VerifyByLink({ token }: { token: string }) {
  const { user, setUser } = useAuth();
  const [state, setState] = useState<"working" | "done" | "failed">("working");
  const started = useRef(false); // the link is single-use: never send it twice (StrictMode)
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    api.verifyEmailLink(token).then(
      (verified) => {
        if (user && user.id === verified.id) setUser(verified);
        setState("done");
      },
      () => setState("failed"),
    );
  }, [token, user, setUser]);
  return (
    <div className="card auth__card stack" aria-labelledby="verify-title">
      <h1 className="page__title" id="verify-title">Confirm your email</h1>
      {state === "working" && <LoadingState label="Confirming your email…" />}
      {state === "done" && (
        <>
          <p className="banner banner--success" role="status">Your email is verified. Thanks!</p>
          <Link className="btn btn--primary btn--md" to={user ? "/dashboard" : "/login"}>{user ? "Go to your dashboard" : "Sign in"}</Link>
        </>
      )}
      {state === "failed" && (
        <>
          <p role="alert">This verification link is invalid or has expired.</p>
          <Link className="btn btn--primary btn--md" to={user ? "/verify-email" : "/login"}>
            {user ? "Enter a code instead" : "Sign in to get a new one"}
          </Link>
        </>
      )}
    </div>
  );
}

function VerifyByCode() {
  const { user, isRestoring, setUser } = useAuth();
  const navigate = useNavigate();
  const next = useNext();
  const [code, setCode] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [resent, setResent] = useState<string | null>(null);
  const [resendError, setResendError] = useState<unknown>(null);

  if (isRestoring) return <LoadingState label="Loading…" />;
  if (!user || user.is_guest || !user.email) {
    return (
      <div className="card auth__card stack">
        <h1 className="page__title">Confirm your email</h1>
        <p className="muted">Sign in to enter the code from your email, or open the link in that email.</p>
        <Link className="btn btn--primary btn--md" to="/login">Sign in</Link>
      </div>
    );
  }
  if (user.email_verified) {
    return (
      <div className="card auth__card stack">
        <h1 className="page__title">Confirm your email</h1>
        <p className="banner banner--success" role="status">{user.email} is verified.</p>
        <Link className="btn btn--primary btn--md" to={next}>Continue</Link>
      </div>
    );
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setUser(await api.verifyEmailCode(code));
      navigate(next, { replace: true });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    setResent(null);
    setResendError(null);
    try {
      setResent((await api.resendVerification()).message);
      setCode("");
      setError(null);
    } catch (err) {
      setResendError(err);
    }
  }

  const attemptsLeft = error instanceof ApiError
    ? (error.details as { attempts_left?: number } | null)?.attempts_left
    : undefined;

  return (
    <form className="card auth__card stack" onSubmit={onSubmit} noValidate aria-labelledby="verify-title">
      <h1 className="page__title" id="verify-title">Check your email</h1>
      <p className="muted">
        We sent a 6-digit code to <strong>{user.email}</strong>. Enter it below, or click the link in that email.
      </p>
      <EmailNotSentNote what="code (and the link)" />
      <Field label="Verification code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]*"
        maxLength={6} required value={code} className="input code-input"
        onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
        error={attemptsLeft !== undefined ? `That code isn't right. ${attemptsLeft} ${attemptsLeft === 1 ? "try" : "tries"} left.` : undefined} />
      {attemptsLeft === undefined && <InlineError error={error} />}
      <Button type="submit" variant="primary" loading={busy} disabled={code.length !== 6}>Verify email</Button>
      <div className="auth__alt">
        <Button variant="ghost" onClick={() => void resend()}>Send a new code</Button>
        {resent && <span className="subtle" role="status">{resent}</span>}
        <InlineError error={resendError} />
        <Link to={next} className="subtle">Do this later</Link>
      </div>
    </form>
  );
}
