import { Link } from "react-router-dom";

import { useAIUsage, useDataSummary } from "@/api/queries";
import type { DataCategory } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { ErrorState, LoadingState } from "@/components/States";
import { recognitionCtor } from "@/features/voice/capabilities";
import { loadVoicePrefs } from "@/features/voice/voicePrefs";

import { DeviceInventory } from "./DeviceInventory";
import { RETENTION_POINTS } from "./retention";

const GROUPS: { id: DataCategory["group"]; title: string }[] = [
  { id: "work", title: "Your work" },
  { id: "sharing", title: "Shared and reported" },
  { id: "account", title: "Your account and sign-in" },
];

/** Counts only: nothing's content is loaded to show them (backend/app/services/data_summary.py). */
function AccountSummary() {
  const summary = useDataSummary();
  if (summary.isPending) return <LoadingState label="Counting what's saved…" />;
  if (summary.isError) return <ErrorState error={summary.error} onRetry={() => void summary.refetch()} />;
  const rows = summary.data.categories;
  return (
    <div className="stack-sm">
      {GROUPS.map((g) => {
        const these = rows.filter((r) => r.group === g.id);
        const some = these.filter((r) => r.count > 0);
        const none = these.filter((r) => r.count === 0);
        return (
          <div key={g.id} className="stack-sm">
            <h3 className="review-minor">{g.title}</h3>
            {some.length > 0 && (
              <ul className="yd-counts">
                {some.map((r) => (
                  <li key={r.key}>
                    <span className="yd-count">{r.count}</span> {r.label}
                    {r.note && <span className="subtle"> {r.note}</span>}
                  </li>
                ))}
              </ul>
            )}
            {none.length > 0 && <p className="subtle">Nothing yet: {none.map((r) => r.label.split(":")[0]).join("; ")}.</p>}
          </div>
        );
      })}
    </div>
  );
}

const PROVIDER_NAME: Record<string, string> = { anthropic: "Anthropic (Claude)" };

/** Where words go when they're processed, from what this app does and this browser offers. */
function Processing() {
  const usage = useAIUsage().data;
  const provider = usage?.provider;
  const external = provider && provider !== "offline" ? (PROVIDER_NAME[provider] ?? provider) : null;
  const dictation = recognitionCtor() !== null;
  const readAloud = loadVoicePrefs().readAloud;
  return (
    <ul className="yd-processing stack-sm">
      <li>
        <h3 className="review-minor">The AI coach</h3>
        {!usage ? <p className="subtle">Checking which coach this CodeCoach uses…</p>
          : external ? (
            <>
              <p>
                Hints, code reviews, explanations of failed tests, and the interviewer in coding interviews send the
                problem, your code and, in an interview, the conversation so far to <strong>{external}</strong>.
                Anything that looks like a secret is removed first. CodeCoach keeps the reply you see, never the request.
              </p>
              <p className="banner banner--info" role="note">
                How long {external} keeps what it receives: <strong>not known to CodeCoach</strong>. It depends on the
                provider's terms and the account this service uses with it. Deleting your account here can't erase the
                provider's copy.
              </p>
            </>
          ) : <p>This CodeCoach uses its built-in coach: hints, reviews and interview replies are worked out on its own server, and nothing you write is sent to an AI provider.</p>}
        <p className="subtle">
          Written answers, question-round interviews, drills, diagrams, code reviews, work samples and the other practice
          labs are checked by fixed rules on CodeCoach's server, whichever coach is set.
        </p>
      </li>
      <li>
        <h3 className="review-minor">Dictation</h3>
        <p>
          Off unless you press the microphone; typing works everywhere. Your browser turns speech into text: Chrome and
          Edge send the audio to their maker's speech service under the browser's terms, and Safari may do it on the
          device. How long that service keeps audio: <strong>not known to CodeCoach</strong>. CodeCoach receives only the
          text you send, never audio.
        </p>
        <p className="subtle">{dictation ? "This browser offers dictation." : "This browser doesn't offer dictation here."}</p>
      </li>
      <li>
        <h3 className="review-minor">The interviewer's voice</h3>
        <p>
          Questions are read aloud by your browser's voices when "Have the interviewer read each question aloud" is on. Some voices are online
          services: with those, the browser sends the question's text (not your answers) to its maker.
        </p>
        <p className="subtle">
          Read aloud is <strong>{readAloud ? "on" : "off"}</strong> on this device. <Link to="/settings#display">Change it in Settings</Link>.
        </p>
      </li>
      <li>
        <h3 className="review-minor">Email</h3>
        <p>Sign-in codes and account notices go to your address through the mail service this CodeCoach uses. An email that was sent can't be recalled.</p>
      </li>
    </ul>
  );
}

/** /settings/data: what's stored about you, where, and how to remove it (Volume 10, prompt 10). */
export function YourDataPage() {
  const { user } = useAuth();
  if (!user) return null;
  return (
    <div className="page yd-page">
      <div className="page__header">
        <div>
          <p className="eyebrow">SETTINGS · PRIVACY</p>
          <h1 className="page__title">Your data</h1>
          <p className="page__subtitle">
            What CodeCoach keeps about you, where it's kept, and how to remove it. This describes the app as it's built;
            it isn't a legal certification.
          </p>
        </div>
      </div>

      <section className="card stack-sm" aria-labelledby="yd-device">
        <h2 className="section-title" id="yd-device">On this device</h2>
        <p>
          Copies kept in this browser for this account, so nothing is lost before it's sent or saved. They aren't sent
          anywhere by being here, and signing out on this device removes them. Choose any to remove now.
        </p>
        <DeviceInventory userId={user.id} />
        <h3 className="review-minor">Also on this device, not removed here</h3>
        <ul className="mini-list">
          <li>Display, editor and voice settings: device settings, not account data. <Link to="/settings#display">Settings</Link></li>
          <li>Your dashboard shortcuts: which pages you keep there, by name, for this account. Kept when you sign out; Reset to defaults on the dashboard clears them. <Link to="/dashboard">Dashboard</Link></li>
          <li>Which version&apos;s changes you&apos;ve looked at in What&apos;s new, for this account: one number, nothing about what you read. Kept when you sign out. <Link to="/whats-new">What&apos;s new</Link></li>
          <li>Public pages you saved for offline reading. <Link to="/offline">Manage saved items</Link></li>
          <li>Your sign-in: a cookie this page can't read. Nothing here touches it; signing out ends it.</li>
          <li>Which account last used this device (its id and name, no password or token), so drafts still show offline. Removed when you sign out.</li>
          <li>This tab's list positions and reminders already shown: gone when the tab closes.</li>
        </ul>
      </section>

      <section className="card stack-sm" aria-labelledby="yd-account">
        <h2 className="section-title" id="yd-account">Saved to your account</h2>
        <p>On CodeCoach's server, visible only to you. Counted, not opened: nothing's content is loaded to show these numbers.</p>
        <AccountSummary />
        <div className="row">
          <Link className="btn btn--secondary btn--md" to="/settings#privacy">Download my data</Link>
          <Link className="btn btn--ghost btn--md" to="/settings/restore">Restore from a backup</Link>
          <Link className="btn btn--ghost btn--md" to="/settings#danger">Delete my account</Link>
        </div>
        <h3 className="review-minor">How long it's kept</h3>
        <ul className="mini-list">
          {RETENTION_POINTS.map((p) => <li key={p}>{p}</li>)}
        </ul>
      </section>

      <section className="card stack-sm" aria-labelledby="yd-processing">
        <h2 className="section-title" id="yd-processing">Where your words go when they're processed</h2>
        <Processing />
      </section>
    </div>
  );
}
