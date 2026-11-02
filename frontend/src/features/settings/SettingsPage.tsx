import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useAIUsage, useCapabilities } from "@/api/queries";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Field } from "@/components/Field";
import { InlineError } from "@/components/States";
import { fieldErrorsFrom } from "@/features/auth/fieldErrors";
import { formatDateTime } from "@/lib/format";
import { EditorPreferencesControls } from "./EditorPreferencesControls";
import { EditorAppearancePreview } from "./EditorAppearancePreview";
import { Icon } from "@/components/Icon";

export function SettingsPage() {
  const { user } = useAuth();
  const [upgraded, setUpgraded] = useState(false);
  if (!user) return null;
  return (
    <div className="page settings">
      <div className="page__header">
        <div>
          <p className="eyebrow">YOUR WORKSPACE, YOUR WAY</p>
          <h1 className="page__title">Settings</h1>
          <p className="page__subtitle">
            {user.is_guest ? "Guest session" : user.email} · member since {formatDateTime(user.created_at)}
          </p>
        </div>
        <Link className="btn btn--secondary btn--md" to="/history"><Icon name="file" size={16} />View practice history</Link>
      </div>
      <div className="account-summary"><div className="account-summary__avatar" aria-hidden="true">{(user.display_name ?? user.email ?? "Guest").trim().split(/\s+/).map((part) => part[0]).slice(0, 2).join("").toUpperCase() || "C"}</div><div><strong>{user.display_name ?? user.email ?? "Guest"}</strong><p className="subtle">{user.is_guest ? "A temporary session for exploring CodeCoach." : user.email}</p></div><span className="badge">{user.is_guest ? "Guest account" : "Your account"}</span></div>
      {upgraded && (
        <p className="banner banner--success" role="status">
          Your account is ready. Everything you did as a guest is saved, and you can sign in from any device.
        </p>
      )}
      <div className="settings__grid">
        {user.is_guest && <KeepProgressCard onUpgraded={() => setUpgraded(true)} />}
        <ProfileCard />
        <Card className="stack" aria-labelledby="editor-preferences-title"><h2 id="editor-preferences-title" className="section-title"><Icon name="code" size={17} />Editor preferences</h2><EditorAppearancePreview /><EditorPreferencesControls /></Card>
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
        <h2 id="profile-title" className="section-title"><Icon name="user" size={17} />Profile</h2>
        <p className="subtle">A name to make this workspace your own.</p>
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

/** Guests can turn their temporary account into a real one without losing anything. */
function KeepProgressCard({ onUpgraded }: { onUpgraded(): void }) {
  const { adoptToken } = useAuth();
  const retention = useCapabilities().data?.guest_retention_days;
  const [form, setForm] = useState({ display_name: "", email: "", password: "" });
  const state = useFormState();
  const errors = fieldErrorsFrom(state.error) as Record<string, string | undefined>;
  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void state.run(async () => {
      const response = await api.upgradeGuest({ email: form.email, password: form.password, display_name: form.display_name || null });
      onUpgraded(); // this card unmounts once the account is no longer a guest
      adoptToken(response);
    }, "");
  };
  return (
    <Card className="keep-progress">
      <form className="stack" onSubmit={onSubmit} aria-labelledby="keep-progress-title">
        <h2 id="keep-progress-title" className="section-title"><Icon name="shield" size={17} />Keep your progress</h2>
        <p className="muted">
          This is a guest session.{retention ? ` Guest accounts are deleted after ${retention} days without activity. ` : " "}
          Create an account to keep your attempts, hints, reviews and interviews, and sign in from any device.
        </p>
        <Field label="Name" optional autoComplete="nickname" maxLength={40} value={form.display_name}
          onChange={set("display_name")} error={errors.display_name} />
        <Field label="Email" type="email" autoComplete="email" required value={form.email}
          onChange={set("email")} error={errors.email} />
        <Field label="Password" type="password" autoComplete="new-password" required value={form.password}
          onChange={set("password")} error={errors.password}
          hint="At least 10 characters with upper- and lower-case letters and a number." />
        {!errors.email && !errors.password && !errors.display_name && <InlineError error={state.error} />}
        <div className="row">
          <Button type="submit" variant="primary" loading={state.busy} disabled={!form.email || !form.password}>
            Create my account
          </Button>
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
        <h2 id="password-title" className="section-title"><Icon name="shield" size={17} />Password</h2>
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
      <h2 id="ai-title" className="section-title"><Icon name="spark" size={17} />AI coach & privacy</h2>
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
      <h2 id="data-title" className="section-title"><Icon name="file" size={17} />Your data</h2>
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
