import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/Button";
import { Field } from "@/components/Field";
import { InlineError } from "@/components/States";

import { fieldErrorsFrom } from "./fieldErrors";
import { AuthLayout } from "./AuthLayout";

function useRedirectTarget(): string {
  const location = useLocation();
  return (location.state as { from?: string } | null)?.from ?? "/problems";
}

function GuestButton() {
  const { continueAsGuest } = useAuth();
  const navigate = useNavigate();
  const target = useRedirectTarget();
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
  const notice = (useLocation().state as { notice?: string } | null)?.notice ?? null;
  const navigate = useNavigate();
  const target = useRedirectTarget();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

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
          onChange={(e) => setEmail(e.target.value)} />
        <Field label="Password" type="password" autoComplete="current-password" required value={password}
          onChange={(e) => setPassword(e.target.value)} />
        <Link className="auth__forgot" to="/forgot-password">Forgot your password?</Link>
        <InlineError error={error} />
        <Button type="submit" variant="primary" loading={busy} disabled={!email || !password}>Sign in</Button>
        <div className="auth__alt">
          <span className="subtle">New here? <Link to="/register">Create an account</Link></span>
          <GuestButton />
        </div>
      </form>
    </AuthLayout>
  );
}

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const target = useRedirectTarget();
  const [form, setForm] = useState({ display_name: "", email: "", password: "" });
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const fieldErrors = fieldErrorsFrom(error);
  const generalError = Object.keys(fieldErrors).length ? null : error;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await register({ email: form.email, password: form.password, display_name: form.display_name || null });
      navigate(target, { replace: true });
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
        <p className="muted">Save your progress, attempts and AI feedback across devices.</p>
        <Field label="Name" optional autoComplete="nickname" maxLength={40} value={form.display_name}
          onChange={set("display_name")} error={fieldErrors.display_name} />
        <Field label="Email" type="email" autoComplete="email" required value={form.email}
          onChange={set("email")} error={fieldErrors.email} />
        <Field label="Password" type="password" autoComplete="new-password" required minLength={10}
          value={form.password} onChange={set("password")} error={fieldErrors.password}
          hint="At least 10 characters with upper- and lower-case letters and a number." />
        <InlineError error={generalError} />
        <Button type="submit" variant="primary" loading={busy} disabled={!form.email || !form.password}>
          Create account
        </Button>
        <div className="auth__alt">
          <span className="subtle">Have an account? <Link to="/login">Sign in</Link></span>
          <GuestButton />
        </div>
      </form>
    </AuthLayout>
  );
}
