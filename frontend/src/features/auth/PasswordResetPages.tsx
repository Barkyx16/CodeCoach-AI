import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { Field } from "@/components/Field";
import { InlineError } from "@/components/States";

import { AuthLayout } from "./AuthLayout";
import { fieldErrorsFrom } from "./fieldErrors";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setSent((await api.requestPasswordReset(email)).message);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      <form className="card auth__card stack" onSubmit={onSubmit} noValidate aria-labelledby="forgot-title">
        <h1 className="page__title" id="forgot-title">Reset your password</h1>
        {sent ? (
          <>
            <p role="status">{sent}</p>
            <p className="muted">The link works once and expires soon. Check your spam folder if it doesn't arrive.</p>
          </>
        ) : (
          <>
            <p className="muted">Enter your account's email and we'll send you a link to choose a new password.</p>
            <Field label="Email" type="email" autoComplete="email" required value={email}
              onChange={(e) => setEmail(e.target.value)} />
            <InlineError error={error} />
            <Button type="submit" variant="primary" loading={busy} disabled={!email}>Send reset link</Button>
          </>
        )}
        <div className="auth__alt"><span className="subtle">Remembered it? <Link to="/login">Sign in</Link></span></div>
      </form>
    </AuthLayout>
  );
}

/** Read the token from the link's #fragment once, then remove it from the address bar. */
function useTokenFromFragment(): string | null {
  const [token] = useState(() => new URLSearchParams(window.location.hash.slice(1)).get("token"));
  useEffect(() => {
    if (window.location.hash) {
      window.history.replaceState(window.history.state, "", window.location.pathname + window.location.search);
    }
  }, []);
  return token;
}

export function ResetPasswordPage() {
  const token = useTokenFromFragment();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const mismatch = confirm.length > 0 && confirm !== password;
  const fieldErrors = fieldErrorsFrom(error);
  const linkProblem = error instanceof ApiError && error.code === "invalid_reset_token";

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!token || mismatch) return;
    setBusy(true);
    setError(null);
    try {
      await api.confirmPasswordReset(token, password);
      navigate("/login", { replace: true, state: { notice: "Your password was changed. Sign in with the new one." } });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      <form className="card auth__card stack" onSubmit={onSubmit} noValidate aria-labelledby="reset-title">
        <h1 className="page__title" id="reset-title">Choose a new password</h1>
        {!token || linkProblem ? (
          <>
            <p role="alert">This reset link is invalid or has expired.</p>
            <Link className="btn btn--primary btn--md" to="/forgot-password">Request a new link</Link>
          </>
        ) : (
          <>
            <p className="muted">This signs you out everywhere, so a stolen session can't outlive the change.</p>
            <Field label="New password" type="password" autoComplete="new-password" required minLength={10}
              value={password} onChange={(e) => setPassword(e.target.value)} error={fieldErrors.new_password}
              hint="At least 10 characters with upper- and lower-case letters and a number." />
            <Field label="Confirm new password" type="password" autoComplete="new-password" required
              value={confirm} onChange={(e) => setConfirm(e.target.value)}
              error={mismatch ? "The passwords don't match." : undefined} />
            <InlineError error={Object.keys(fieldErrors).length ? null : error} />
            <Button type="submit" variant="primary" loading={busy} disabled={!password || !confirm || mismatch}>
              Set new password
            </Button>
          </>
        )}
      </form>
    </AuthLayout>
  );
}
