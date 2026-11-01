import { useState, type FormEvent } from "react";

import { api } from "@/api/endpoints";
import { useAIUsage } from "@/api/queries";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Field } from "@/components/Field";
import { InlineError } from "@/components/States";
import { fieldErrorsFrom } from "@/features/auth/fieldErrors";
import { formatDateTime } from "@/lib/format";
import { EditorPreferencesControls } from "./EditorPreferencesControls";

export function SettingsPage() {
  const { user } = useAuth();
  if (!user) return null;
  return (
    <div className="page settings">
      <div className="page__header">
        <div>
          <h1 className="page__title">Settings</h1>
          <p className="page__subtitle">
            {user.is_guest ? "Guest session" : user.email} · member since {formatDateTime(user.created_at)}
          </p>
        </div>
      </div>
      <div className="settings__grid">
        <ProfileCard />
        <Card className="stack" aria-labelledby="editor-preferences-title"><h2 id="editor-preferences-title" className="section-title">Editor preferences</h2><EditorPreferencesControls /></Card>
        {!user.is_guest && <PasswordCard />}
        <AIPrivacyCard />
        <DataCard />
        <DangerCard />
      </div>
    </div>
  );
}

function useFormState() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [done, setDone] = useState<string | null>(null);
  async function run(fn: () => Promise<void>, successMessage: string) {
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      await fn();
      setDone(successMessage);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, done, run };
}

function ProfileCard() {
  const { user, setUser } = useAuth();
  const [name, setName] = useState(user?.display_name ?? "");
  const form = useFormState();
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void form.run(async () => setUser(await api.updateProfile({ display_name: name.trim() || null })), "Saved.");
  };
  return (
    <Card>
      <form className="stack" onSubmit={onSubmit} aria-labelledby="profile-title">
        <h2 id="profile-title" className="section-title">Profile</h2>
        <Field label="Display name" maxLength={40} value={name} onChange={(e) => setName(e.target.value)}
          hint="Shown in the header and on your dashboard." error={fieldErrorsFrom(form.error).display_name} />
        {!fieldErrorsFrom(form.error).display_name && <InlineError error={form.error} />}
        <div className="row">
          <Button type="submit" variant="primary" loading={form.busy}>Save profile</Button>
          {form.done && <span className="subtle" role="status">{form.done}</span>}
        </div>
      </form>
    </Card>
  );
}

function PasswordCard() {
  const { adoptToken } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const form = useFormState();
  const errors = fieldErrorsFrom(form.error) as Record<string, string | undefined>;
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void form.run(async () => {
      adoptToken(await api.changePassword({ current_password: current, new_password: next }));
      setCurrent("");
      setNext("");
    }, "Password changed. Other devices were signed out.");
  };
  return (
    <Card>
      <form className="stack" onSubmit={onSubmit} aria-labelledby="password-title">
        <h2 id="password-title" className="section-title">Password</h2>
        <Field label="Current password" type="password" autoComplete="current-password" value={current}
          onChange={(e) => setCurrent(e.target.value)} />
        <Field label="New password" type="password" autoComplete="new-password" value={next}
          onChange={(e) => setNext(e.target.value)} error={errors.new_password}
          hint="At least 10 characters with upper- and lower-case letters and a number." />
        {!errors.new_password && <InlineError error={form.error} />}
        <div className="row">
          <Button type="submit" variant="primary" loading={form.busy} disabled={!current || !next}>Change password</Button>
          {form.done && <span className="subtle" role="status">{form.done}</span>}
        </div>
      </form>
    </Card>
  );
}

function AIPrivacyCard() {
  const usage = useAIUsage();
  return (
    <Card className="stack" aria-labelledby="ai-title">
      <h2 id="ai-title" className="section-title">AI coach & privacy</h2>
      {usage.data && (
        <p>
          You've used <strong>{usage.data.used_today}</strong> of <strong>{usage.data.daily_limit}</strong> AI requests
          in the last 24 hours. Coach: <strong>{usage.data.provider === "offline" ? "built-in (offline)" : usage.data.provider}</strong>.
        </p>
      )}
      <ul className="strengths">
        <li>Hints, reviews and interview replies send the problem and your current code to the AI provider.</li>
        <li>Anything that looks like a secret (API keys, tokens, passwords in strings) is redacted first.</li>
        <li>We keep the feedback you see so you can revisit it, never the prompt that contained your code.</li>
        <li>The AI never decides pass or fail. Only the test judge does.</li>
      </ul>
    </Card>
  );
}

function DataCard() {
  const form = useFormState();
  const download = () => form.run(async () => {
    const data = await api.exportData();
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "codecoach-data.json";
    a.click();
    URL.revokeObjectURL(url);
  }, "Downloaded codecoach-data.json");
  return (
    <Card className="stack" aria-labelledby="data-title">
      <h2 id="data-title" className="section-title">Your data</h2>
      <p className="muted">Download everything we store about you: profile, submissions with your code, AI feedback,
        interview transcripts and activity.</p>
      <div className="row">
        <Button onClick={() => void download()} loading={form.busy}>Download my data</Button>
        {form.done && <span className="subtle" role="status">{form.done}</span>}
      </div>
      <InlineError error={form.error} />
    </Card>
  );
}

function DangerCard() {
  const { user, forget } = useAuth();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const form = useFormState();
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void form.run(async () => {
      await api.deleteAccount({ password: user?.is_guest ? undefined : password, confirm });
      forget(); // a deliberate sign-out: the route guard sends the user home
    }, "");
  };
  return (
    <Card className="settings__danger">
      <form className="stack" onSubmit={onSubmit} aria-labelledby="danger-title">
        <h2 id="danger-title" className="section-title">Delete account</h2>
        <p className="muted">This permanently deletes your account and all of your submissions, AI feedback,
          interviews and progress. It can't be undone.</p>
        {!user?.is_guest && (
          <Field label="Password" type="password" autoComplete="current-password" value={password}
            onChange={(e) => setPassword(e.target.value)} />
        )}
        <Field label='Type "DELETE" to confirm' value={confirm} onChange={(e) => setConfirm(e.target.value)}
          autoComplete="off" />
        <InlineError error={form.error} />
        <Button type="submit" variant="danger" loading={form.busy}
          disabled={confirm !== "DELETE" || (!user?.is_guest && !password)}>
          Delete my account
        </Button>
      </form>
    </Card>
  );
}
