import { useEffect, useState, type FormEvent, type MouseEvent, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useAIUsage, useCapabilities, useMyReports, useShares } from "@/api/queries";
import type { User } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Field } from "@/components/Field";
import { Icon, type IconName } from "@/components/Icon";
import { PasswordChecklist } from "@/components/PasswordChecklist";
import { InlineError } from "@/components/States";
import { fieldErrorsFrom } from "@/features/auth/fieldErrors";
import { EditorAppearancePreview } from "./EditorAppearancePreview";
import { CareerSelect } from "@/features/careers/CareerSelect";
import { DisplayControls } from "@/features/display/DisplayControls";

import { DeviceRows } from "./DeviceSection";
import { EditorPreferencesControls } from "./EditorPreferencesControls";

/**
 * Settings, grouped the way people look for things: who you are (Account), how you sign in
 * (Sign-in & security), how the editor looks (Editor), what we keep (Privacy & data), and the
 * one irreversible action (Danger zone), each a section with its own heading. Inside a section,
 * every setting is a row: what it is on the left, its controls on the right (stacked on phones).
 */
const SECTIONS: { id: string; label: string; icon: IconName }[] = [
  { id: "account", label: "Account", icon: "user" },
  { id: "security", label: "Sign-in & security", icon: "lock" },
  { id: "display", label: "Display & reading", icon: "book" },
  { id: "editor", label: "Editor", icon: "code" },
  { id: "device", label: "Offline & app", icon: "download" },
  { id: "privacy", label: "Privacy & data", icon: "shield" },
  { id: "danger", label: "Danger zone", icon: "alert" },
];

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
          <p className="page__subtitle">Manage your account, how you sign in, your editor and your data.</p>
        </div>
      </div>
      <AccountHero user={user} />
      {upgraded && (
        <p className="banner banner--success settings__banner" role="status">
          Your account is ready. Everything you did as a guest is saved, and you can sign in from any device.{" "}
          <Link to="/verify-email" state={{ next: "/settings" }}>Enter the code we emailed you</Link> to confirm your email.
        </p>
      )}
      <div className="settings__layout">
        <SectionNav />
        <div className="settings__sections">
          <Section id="account" title="Account" description="How you appear in CodeCoach, and the address we use to reach you.">
            {user.is_guest && <KeepProgressRow onUpgraded={() => setUpgraded(true)} />}
            <ProfileRow />
            <CareerRow />
            <HelpRow />
            {!user.is_guest && <EmailRow />}
          </Section>
          <Section id="security" title="Sign-in & security" description="Your password and where you're signed in.">
            {!user.is_guest && <PasswordRow />}
            <SessionsRow />
          </Section>
          <Section id="display" title="Display & reading" description="How the app looks and reads on this device. These stay in this browser and aren't part of your account.">
            <div className="setting" role="group" aria-labelledby="display-title">
              <RowIntro icon="book" id="display-title" title="Theme and reading">
                Light or dark, contrast, text size, spacing and motion.
              </RowIntro>
              <div className="setting__body setting__body--wide">
                <DisplayControls />
              </div>
            </div>
          </Section>
          <Section id="editor" title="Editor" description="Applies to the practice workspace and to interviews.">
            <div className="setting" role="group" aria-labelledby="editor-preferences-title">
              <RowIntro icon="code" id="editor-preferences-title" title="Code editor">
                Theme, text size, indentation and line wrapping. Saved in this browser.
              </RowIntro>
              <div className="setting__body setting__body--wide">
                <EditorAppearancePreview />
                <EditorPreferencesControls />
              </div>
            </div>
          </Section>
          <Section id="device" title="Offline & app" description="Installing CodeCoach and using it without a connection on this device.">
            <DeviceRows />
          </Section>
          <Section id="privacy" title="Privacy & data" description="What the AI coach sees, and a copy of everything we store.">
            <AIPrivacyRow />
            <SharedRow />
            <ReportsRow />
            <DataRow />
          </Section>
          <Section id="danger" title="Danger zone" description="Permanent actions. Take a moment before using these." tone="danger">
            <DeleteAccountRow />
          </Section>
        </div>
      </div>
    </div>
  );
}

function initials(user: User): string {
  const source = user.display_name ?? user.email ?? "Guest";
  return source.trim().split(/[\s@._-]+/).filter(Boolean).map((part) => part[0]).slice(0, 2).join("").toUpperCase() || "C";
}

function AccountHero({ user }: { user: User }) {
  const name = user.display_name ?? (user.is_guest ? "Guest" : user.email);
  const secondary = user.is_guest ? "Temporary guest session" : user.display_name ? user.email : null;
  const since = new Date(user.created_at).toLocaleDateString(undefined, { dateStyle: "medium" });
  return (
    <div className="settings-hero">
      <div className="settings-hero__avatar" aria-hidden="true">{initials(user)}</div>
      <div className="settings-hero__who">
        <strong>{name}</strong>
        {secondary && <span className="subtle">{secondary}</span>}
      </div>
      <ul className="settings-hero__facts" aria-label="Account status">
        <li><Badge tone={user.is_guest ? "warning" : "info"}>{user.is_guest ? "Guest account" : "Your account"}</Badge></li>
        {!user.is_guest && (
          <li>{user.email_verified ? <Badge tone="success">Email verified</Badge> : <Badge tone="warning">Email not verified</Badge>}</li>
        )}
        <li className="subtle">Member since {since}</li>
      </ul>
    </div>
  );
}

/** Scroll to a section and move keyboard and screen-reader focus to its heading. */
function jumpTo(id: string): boolean {
  const section = document.getElementById(id);
  if (!section) return false;
  const smooth = !window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  section.scrollIntoView?.({ behavior: smooth ? "smooth" : "auto", block: "start" });
  section.querySelector<HTMLElement>("h2")?.focus({ preventScroll: true });
  return true;
}

/** Jump links to each section. Highlights the section you're reading as you scroll. */
function SectionNav() {
  const [active, setActive] = useState(SECTIONS[0]!.id);
  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver((entries) => {
      const hit = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (hit) setActive(hit.target.id);
    }, { rootMargin: "-120px 0px -55% 0px" });
    for (const s of SECTIONS) {
      const el = document.getElementById(s.id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  }, []);
  function jump(e: MouseEvent<HTMLAnchorElement>, id: string) {
    if (jumpTo(id)) {
      e.preventDefault();
      setActive(id);
    }
  }
  return (
    <nav className="settings__nav" aria-label="Settings sections">
      {SECTIONS.map((s) => (
        <a key={s.id} href={`#${s.id}`} aria-current={active === s.id ? "true" : undefined}
          className={s.id === "danger" ? "settings__nav-danger" : undefined} onClick={(e) => jump(e, s.id)}>
          <Icon name={s.icon} size={16} />{s.label}
        </a>
      ))}
    </nav>
  );
}

function Section({ id, title, description, tone, children }: {
  id: string; title: string; description: string; tone?: "danger"; children: ReactNode;
}) {
  return (
    <section id={id} className={`settings-section${tone ? ` settings-section--${tone}` : ""}`} aria-labelledby={`${id}-heading`}>
      <div className="settings-section__header">
        <h2 id={`${id}-heading`} tabIndex={-1}>{title}</h2>
        <p className="subtle">{description}</p>
      </div>
      <div className="card settings-section__card">{children}</div>
    </section>
  );
}

/** The left half of a setting row: its name (the accessible name of the row's form) and what it does. */
function RowIntro({ icon, id, title, children }: { icon: IconName; id: string; title: string; children?: ReactNode }) {
  return (
    <div className="setting__intro">
      <h3 id={id} className="setting__title"><Icon name={icon} size={17} />{title}</h3>
      {children && <p className="setting__desc">{children}</p>}
    </div>
  );
}

function Status({ children }: { children: ReactNode }) {
  return <span className="setting__status" role="status"><Icon name="check" size={15} />{children}</span>;
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

function ProfileRow() {
  const { user, setUser } = useAuth();
  const [name, setName] = useState(user?.display_name ?? "");
  const form = useFormState();
  const nameError = fieldErrorsFrom(form.error).display_name;
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void form.run(async () => setUser(await api.updateProfile({ display_name: name.trim() || null })), "Saved.");
  };
  return (
    <form className="setting" onSubmit={onSubmit} aria-labelledby="profile-title">
      <RowIntro icon="user" id="profile-title" title="Profile">A name to make this workspace your own.</RowIntro>
      <div className="setting__body">
        <Field label="Display name" maxLength={40} value={name} onChange={(e) => setName(e.target.value)}
          hint="Shown in the header and on your dashboard." error={nameError} />
        {!nameError && <InlineError error={form.error} />}
        <div className="setting__actions">
          <Button type="submit" variant="primary" loading={form.busy}>Save profile</Button>
          {form.done && <Status>{form.done}</Status>}
        </div>
      </div>
    </form>
  );
}

/** The job this person is preparing for: decides which interview questions they practice. */
function CareerRow() {
  const { user, setUser } = useAuth();
  const [track, setTrack] = useState(user?.career_track ?? "");
  const form = useFormState();
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void form.run(async () => setUser(await api.updateProfile({ career_track: track })), "Saved. Your practice questions now match this job.");
  };
  return (
    <form className="setting" onSubmit={onSubmit} aria-labelledby="career-title">
      <RowIntro icon="target" id="career-title" title="Career">
        The job you're preparing for. Practice questions, tabs and progress follow it. Switching keeps
        everything you've practised: History and Analytics still show your other careers.
      </RowIntro>
      <div className="setting__body">
        <CareerSelect value={track} onChange={setTrack} />
        <InlineError error={form.error} />
        <div className="setting__actions">
          <Button type="submit" variant="secondary" loading={form.busy} disabled={!track || track === user?.career_track}>
            Save career
          </Button>
          {form.done && <Status>{form.done}</Status>}
        </div>
      </div>
    </form>
  );
}

/** Guests can turn their temporary account into a real one without losing anything. */
function KeepProgressRow({ onUpgraded }: { onUpgraded(): void }) {
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
      onUpgraded(); // this row unmounts once the account is no longer a guest
      adoptToken(response);
    }, "");
  };
  return (
    <form className="setting setting--highlight keep-progress" onSubmit={onSubmit} aria-labelledby="keep-progress-title">
      <RowIntro icon="shield" id="keep-progress-title" title="Keep your progress">
        This is a guest session.{retention ? ` Guest accounts are deleted after ${retention} days without activity. ` : " "}
        Create an account to keep your attempts, hints, reviews and interviews, and sign in from any device.
      </RowIntro>
      <div className="setting__body">
        <Field label="Name" optional autoComplete="nickname" maxLength={40} value={form.display_name}
          onChange={set("display_name")} error={errors.display_name} />
        <Field label="Email" type="email" autoComplete="email" required value={form.email}
          onChange={set("email")} error={errors.email} />
        <Field label="Password" type="password" autoComplete="new-password" required value={form.password}
          onChange={set("password")} error={errors.password}
          extra={<PasswordChecklist password={form.password} />} />
        {!errors.email && !errors.password && !errors.display_name && <InlineError error={state.error} />}
        <div className="setting__actions">
          <Button type="submit" variant="primary" loading={state.busy} disabled={!form.email || !form.password}>
            Create my account
          </Button>
        </div>
      </div>
    </form>
  );
}

/** Current email, whether it's verified, and changing it (needs the password). */
function EmailRow() {
  const { user, setUser } = useAuth();
  const [newEmail, setNewEmail] = useState("");
  const [password, setPassword] = useState("");
  const form = useFormState();
  const errors = fieldErrorsFrom(form.error) as Record<string, string | undefined>;
  if (!user) return null;
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void form.run(async () => {
      setUser(await api.changeEmail({ new_email: newEmail, password }));
      setNewEmail("");
      setPassword("");
    }, "Email changed. We sent a code to the new address, and a notice to the old one.");
  };
  return (
    <form className="setting" onSubmit={onSubmit} aria-labelledby="email-title">
      <RowIntro icon="mail" id="email-title" title="Email">
        Used to sign in and for account notices. Changing it needs your password.
      </RowIntro>
      <div className="setting__body">
        <div className="setting__current">
          <strong>{user.email}</strong>
          {user.email_verified ? <Badge tone="success">Verified</Badge> : <Badge tone="warning">Not verified</Badge>}
        </div>
        {!user.email_verified && (
          <p className="setting__note">
            Confirm it so we can reach you about your account.{" "}
            <Link to="/verify-email" state={{ next: "/settings" }}>Enter the verification code</Link>
          </p>
        )}
        <div className="setting__pair">
          <Field label="New email" type="email" autoComplete="email" value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)} error={errors.new_email} />
          <Field label="Current password" type="password" autoComplete="current-password" value={password}
            onChange={(e) => setPassword(e.target.value)} />
        </div>
        {!errors.new_email && <InlineError error={form.error} />}
        <div className="setting__actions">
          <Button type="submit" variant="secondary" loading={form.busy} disabled={!newEmail || !password}>Change email</Button>
          {form.done && <Status>{form.done}</Status>}
        </div>
      </div>
    </form>
  );
}

function PasswordRow() {
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
    <form className="setting" onSubmit={onSubmit} aria-labelledby="password-title">
      <RowIntro icon="lock" id="password-title" title="Password">
        Changing it signs you out everywhere else, and keeps you signed in here.
      </RowIntro>
      <div className="setting__body">
        <Field label="Current password" type="password" autoComplete="current-password" value={current}
          onChange={(e) => setCurrent(e.target.value)} />
        <Field label="New password" type="password" autoComplete="new-password" value={next}
          onChange={(e) => setNext(e.target.value)} error={errors.new_password}
          extra={<PasswordChecklist password={next} />} />
        {!errors.new_password && <InlineError error={form.error} />}
        <div className="setting__actions">
          <Button type="submit" variant="secondary" loading={form.busy} disabled={!current || !next}>Change password</Button>
          {form.done && <Status>{form.done}</Status>}
        </div>
      </div>
    </form>
  );
}

/** Sign out here, or everywhere (e.g. after using a shared computer). */
function SessionsRow() {
  const { logout, logoutAll } = useAuth();
  const navigate = useNavigate();
  const [busy, setBusy] = useState<"one" | "all" | null>(null);
  const [error, setError] = useState<unknown>(null);
  async function run(kind: "one" | "all") {
    if (kind === "all" && !window.confirm("Sign out of CodeCoach on every device, including this one?")) return;
    setBusy(kind);
    setError(null);
    try {
      await (kind === "all" ? logoutAll() : logout());
      navigate("/");
    } catch (err) {
      setError(err);
      setBusy(null);
    }
  }
  return (
    <div className="setting" role="region" aria-labelledby="sessions-title">
      <RowIntro icon="logout" id="sessions-title" title="Sign out">
        Sign out of this browser, or of every device where you're signed in (useful after a shared computer).
      </RowIntro>
      <div className="setting__body">
        <div className="setting__actions">
          <Button variant="secondary" loading={busy === "one"} disabled={busy !== null} onClick={() => void run("one")}>
            Sign out
          </Button>
          <Button variant="ghost" loading={busy === "all"} disabled={busy !== null} onClick={() => void run("all")}>
            Sign out of all devices
          </Button>
        </div>
        <InlineError error={error} />
      </div>
    </div>
  );
}

const PRIVACY_POINTS = [
  "Hints, reviews and interview replies send the problem and your current code to the AI provider.",
  "Anything that looks like a secret (API keys, tokens, passwords in strings) is redacted first.",
  "We keep the feedback you see so you can revisit it, never the prompt that contained your code.",
  "The AI never decides pass or fail. Only the test judge does.",
];

function AIPrivacyRow() {
  const usage = useAIUsage().data;
  const share = usage && usage.daily_limit > 0 ? Math.min(100, Math.round((usage.used_today / usage.daily_limit) * 100)) : 0;
  return (
    <div className="setting" role="group" aria-labelledby="ai-title">
      <RowIntro icon="spark" id="ai-title" title="AI coach">How the coach uses your code, and today's usage.</RowIntro>
      <div className="setting__body">
        {usage && (
          <div className="usage">
            <p className="usage__head">
              <span>You've used <strong>{usage.used_today}</strong> of <strong>{usage.daily_limit}</strong> AI requests in the last 24 hours.</span>
            </p>
            <div className="usage__bar" aria-hidden="true"><span style={{ width: `${share}%` }} /></div>
            <p className="subtle">Coach: <strong>{usage.provider === "offline" ? "built-in (offline)" : usage.provider}</strong></p>
          </div>
        )}
        <ul className="privacy-points">
          {PRIVACY_POINTS.map((point) => <li key={point}><Icon name="check" size={15} />{point}</li>)}
        </ul>
      </div>
    </div>
  );
}

function HelpRow() {
  return (
    <div className="setting" role="group" aria-labelledby="help-row-title">
      <RowIntro icon="book" id="help-row-title" title="Help and the introduction">
        Short answers about practice, drafts, feedback, voice and history, and the guided tour to take again.
      </RowIntro>
      <div className="setting__body setting__body--center">
        <div className="setting__actions">
          <Link className="btn btn--secondary btn--md" to="/help">Open Help</Link>
        </div>
      </div>
    </div>
  );
}

function ReportsRow() {
  const reports = useMyReports();
  const open = reports.data?.filter((r) => r.status === "open" || r.status === "investigating").length ?? 0;
  return (
    <div className="setting" role="group" aria-labelledby="reports-title">
      <RowIntro icon="alert" id="reports-title" title="Your reports">
        Problems you reported with questions, coding problems or feedback, and what happened to them.
      </RowIntro>
      <div className="setting__body setting__body--center">
        <div className="setting__actions">
          <Link className="btn btn--secondary btn--md" to="/reports">See your reports</Link>
          {reports.data && <span className="subtle">{reports.data.length === 0 ? "None yet" : `${open} open of ${reports.data.length}`}</span>}
        </div>
      </div>
    </div>
  );
}

function SharedRow() {
  const shares = useShares();
  const active = shares.data?.filter((s) => s.status === "active" || s.status === "closed").length ?? 0;
  return (
    <div className="setting" role="group" aria-labelledby="shared-title">
      <RowIntro icon="link" id="shared-title" title="Shared for feedback">
        Answers you shared with a reviewer through a private link. Turn links off or delete them at any time.
      </RowIntro>
      <div className="setting__body setting__body--center">
        <div className="setting__actions">
          <Link className="btn btn--secondary btn--md" to="/shares">Manage shared answers</Link>
          {shares.data && <span className="subtle">{active === 0 ? "No working links" : `${active} working ${active === 1 ? "link" : "links"}`}</span>}
        </div>
      </div>
    </div>
  );
}

function DataRow() {
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
    <div className="setting" role="group" aria-labelledby="data-title">
      <RowIntro icon="download" id="data-title" title="Your data">
        A JSON file with everything we store about you: profile, submissions with your code, AI feedback,
        interview transcripts and activity.
      </RowIntro>
      <div className="setting__body setting__body--center">
        <div className="setting__actions">
          <Button onClick={() => void download()} loading={form.busy}><Icon name="download" size={16} />Download my data</Button>
          {form.done && <Status>{form.done}</Status>}
          <Link to="/settings/restore" className="btn btn--ghost btn--md">Restore from a backup</Link>
        </div>
        <InlineError error={form.error} />
      </div>
    </div>
  );
}

function DeleteAccountRow() {
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
    <form className="setting" onSubmit={onSubmit} aria-labelledby="danger-title">
      <RowIntro icon="trash" id="danger-title" title="Delete account">
        Permanently deletes your account and all of your submissions, AI feedback, interviews and progress.
        It can't be undone. <a href="#privacy" onClick={(e) => { if (jumpTo("privacy")) e.preventDefault(); }}>Download your data</a> first if you want a copy.
      </RowIntro>
      <div className="setting__body">
        {!user?.is_guest && (
          <Field label="Password" type="password" autoComplete="current-password" value={password}
            onChange={(e) => setPassword(e.target.value)} />
        )}
        <Field label='Type "DELETE" to confirm' value={confirm} onChange={(e) => setConfirm(e.target.value)}
          autoComplete="off" />
        <InlineError error={form.error} />
        <div className="setting__actions">
          <Button type="submit" variant="danger" loading={form.busy}
            disabled={confirm !== "DELETE" || (!user?.is_guest && !password)}>
            <Icon name="trash" size={16} />Delete my account
          </Button>
        </div>
      </div>
    </form>
  );
}
