import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "@/auth/useAuth";
import { ActionError } from "@/components/ActionError";
import { Button } from "@/components/Button";
import { Field } from "@/components/Field";
import { PasswordChecklist } from "@/components/PasswordChecklist";
import { InlineError } from "@/components/States";

import { fieldErrorsFrom } from "./fieldErrors";
import { CareerSelect } from "@/features/careers/CareerSelect";
import { useRetryWait } from "@/hooks/useCountdown";
import { failureKind } from "@/lib/errors";
import { safeReturnPath } from "@/lib/links";

import { AuthLayout } from "./AuthLayout";

/** After signing in: back to the page that asked for it (e.g. a problem), else `fallback`: the
 * dashboard for returning accounts, the optional welcome for new ones. Only an in-app path counts
 * (never another site, or a sign-in screen that would loop). */
function useRedirectTarget(fallback = "/dashboard"): string {
  const location = useLocation();
  return safeReturnPath((location.state as { from?: unknown } | null)?.from, fallback);
}

/** Router state that carries the page the learner was going to between Sign in and Create account. */
function useCarriedFrom(): { from: string } | undefined {
  const from = safeReturnPath((useLocation().state as { from?: unknown } | null)?.from, "");
  return from ? { from } : undefined;
}

function GuestButton() {
  const { continueAsGuest } = useAuth();
  const navigate = useNavigate();
  const target = useRedirectTarget("/welcome");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  return (
    <div className="guest-access">
    <Button variant="ghost" loading={busy} onClick={async () => {
      setBusy(true);
      setError(null);
      try {
        await continueAsGuest();
        navigate(target, { replace: true });
      } catch (error) {
        setError(error);
      } finally {
        setBusy(false);
      }
    }}>
      Continue as guest
    </Button>
    <InlineError error={error} />
    </div>
  );
}

export function LoginPage() {
  const { login } = useAuth();
  const carried = useCarriedFrom();
  const notice = (useLocation().state as { notice?: string } | null)?.notice ?? null;
  const navigate = useNavigate();
  const target = useRedirectTarget();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  // Too many tries: only Sign in waits (the server's time, counted down); the fields stay usable.
  const wait = useRetryWait(error);
  const fieldErrors = fieldErrorsFrom(error);
  const generalError = Object.keys(fieldErrors).length ? null : error;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login({ email, password });
      navigate(target, { replace: true });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      <form className="card auth__card stack" onSubmit={onSubmit} noValidate aria-labelledby="login-title">
        <h1 className="page__title" id="login-title">Welcome back</h1>
        {notice ? <p className="banner banner--success" role="status">{notice}</p>
          : <p className="muted">Pick up where your last solution left off.</p>}
        <Field label="Email" type="email" autoComplete="email" required value={email}
          onChange={(e) => setEmail(e.target.value)} error={fieldErrors.email} />
        <Field label="Password" type="password" autoComplete="current-password" required value={password}
          onChange={(e) => setPassword(e.target.value)} error={fieldErrors.password} />
        <Link className="auth__forgot" to="/forgot-password">Forgot your password?</Link>
        {failureKind(generalError) === "busy" || failureKind(generalError) === "offline"
          ? <ActionError error={generalError} action="Signing in" />
          : <InlineError error={generalError} />}
        <Button type="submit" variant="primary" loading={busy} disabled={!email || !password || wait > 0}>Sign in</Button>
        <div className="auth__alt">
          <span className="subtle">New here? <Link to="/register" state={carried}>Create an account</Link></span>
          <GuestButton />
        </div>
      </form>
    </AuthLayout>
  );
}

export function RegisterPage() {
  const { register } = useAuth();
  const carried = useCarriedFrom();
  const navigate = useNavigate();
  const target = useRedirectTarget("/welcome");
  const [form, setForm] = useState({ display_name: "", email: "", password: "", career_track: "" });
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const fieldErrors = fieldErrorsFrom(error);
  const generalError = Object.keys(fieldErrors).length ? null : error;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await register({
        email: form.email, password: form.password, display_name: form.display_name || null, career_track: form.career_track,
      });
      // Next: enter the 6-digit code we just emailed (skippable), then continue.
      navigate("/verify-email", { replace: true, state: { next: target } });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  return (
    <AuthLayout>
      <form className="card auth__card stack" onSubmit={onSubmit} noValidate aria-labelledby="register-title">
        <h1 className="page__title" id="register-title">Create your account</h1>
        <p className="muted">Practice interviews for the job you want, and save your progress across devices.</p>
        <CareerSelect value={form.career_track} onChange={(slug) => setForm((f) => ({ ...f, career_track: slug }))}
          placeholder="Choose a job…" required error={fieldErrors.career_track}
          hint="You'll get interview questions written for this job. You can change it any time." />
        <Field label="Name" optional autoComplete="nickname" maxLength={40} value={form.display_name}
          onChange={set("display_name")} error={fieldErrors.display_name} />
        <Field label="Email" type="email" autoComplete="email" required value={form.email}
          onChange={set("email")} error={fieldErrors.email} />
        <Field label="Password" type="password" autoComplete="new-password" required minLength={10}
          value={form.password} onChange={set("password")} error={fieldErrors.password}
          extra={<PasswordChecklist password={form.password} />} />
        <InlineError error={generalError} />
        <Button type="submit" variant="primary" loading={busy} disabled={!form.email || !form.password || !form.career_track}>
          Create account
        </Button>
        <div className="auth__alt">
          <span className="subtle">Have an account? <Link to="/login" state={carried}>Sign in</Link></span>
          <GuestButton />
        </div>
      </form>
    </AuthLayout>
  );
}
