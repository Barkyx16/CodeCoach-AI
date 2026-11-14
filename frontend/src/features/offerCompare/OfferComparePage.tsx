import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { useApplications, useOfferComparison } from "@/api/queries";
import type { ComparisonDoc, ComparisonFigures, CurrencyRate, OfferComparison, OfferFactor, OfferRating, OfferTerms } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { BackLink } from "@/components/BackLink";
import { Button } from "@/components/Button";
import { ErrorState, InlineError, LoadingState } from "@/components/States";
import { PrivateUnavailable } from "@/components/Unavailable";
import { VersionConflict } from "@/components/VersionConflict";
import { useLeaveWarning } from "@/hooks/useLeaveWarning";
import { savedVersion } from "@/lib/conflict";
import { isGone } from "@/lib/errors";
import { timeAgo } from "@/lib/format";
import { dropCopy, useCopySince, writeCopy } from "@/lib/deviceCopies";
import { useRequestKey } from "@/lib/requestKey";

import { Figures } from "./Figures";
import { asText } from "./text";

const SUGGESTED = ["Schedule", "Commute", "Learning opportunities", "Role scope", "Flexibility", "Benefits"];
const PERIODS: Record<string, string> = { year: "a year", month: "a month", week: "a week", hour: "an hour" };
const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 16) || "f";

function blankOffer(id: string): OfferTerms {
  return {
    id, label: `Offer ${id.toUpperCase()}`, application_id: null, source_note: "", terms_as_of: null, currency: null, pay_amount: null,
    pay_period: null, months_paid: null, hours_per_week: null, weeks_per_year: null, guaranteed_extra: null, guaranteed_note: "",
    bonus_amount: null, bonus_note: "", equity_note: "", benefits_note: "",
  };
}

/** /offers/compare/:id: the private comparison workspace (Volume 10, prompt 9; docs/OFFER_COMPARISON.md). */
export function OfferComparePage() {
  const { comparisonId = "" } = useParams();
  const c = useOfferComparison(comparisonId);
  if (c.isPending) return <LoadingState label="Loading your comparison…" />;
  if (c.isError && isGone(c.error)) return <PrivateUnavailable what="comparison" list={{ to: "/offers/compare", label: "Compare offers" }} />;
  if (c.isError) return <div className="page"><ErrorState error={c.error} onRetry={() => void c.refetch()} /></div>;
  return <Workspace key={c.data.id} saved={c.data} />;
}

function Workspace({ saved }: { saved: OfferComparison }) {
  const [archivedNow, setArchivedNow] = useState(saved.archived);
  const [restoring, setRestoring] = useState(false);
  const qc = useQueryClient();
  const { user } = useAuth();
  const apps = useApplications();
  const deviceKey = `offer-compare-draft:${user?.id ?? "anon"}:${saved.id}`;
  const since = useCopySince(deviceKey); // a copy removed from "Your data" after this opened isn't written back
  const [doc, setDoc] = useState<ComparisonDoc>(saved.doc);
  const [base, setBase] = useState(saved.revision);
  const [onDevice] = useState<{ doc: ComparisonDoc; base: number } | null>(() => {
    try {
      const d = JSON.parse(localStorage.getItem(deviceKey) ?? "null") as { doc: ComparisonDoc; base: number } | null;
      return d && JSON.stringify(d.doc) !== JSON.stringify(saved.doc) ? d : null;
    } catch { return null; }
  });
  const [offer, setOffer] = useState<"open" | "restored" | "dismissed">(onDevice ? "open" : "dismissed");
  const [previewed, setPreviewed] = useState<ComparisonFigures | null>(null);
  const [previewError, setPreviewError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [status, setStatus] = useState("");
  const [against, setAgainst] = useState<OfferComparison | null>(null);
  const [hidden, setHidden] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const [custom, setCustom] = useState("");
  const keys = useRequestKey();
  const dirty = JSON.stringify(doc) !== JSON.stringify(saved.doc);
  useLeaveWarning(dirty);

  useEffect(() => {
    // Blocked, full or removed on purpose: the changes last as long as the page.
    if (dirty) writeCopy(deviceKey, JSON.stringify({ doc, base }), since);
    else dropCopy(deviceKey);
  }, [doc, base, dirty, deviceKey, since]);
  useEffect(() => {
    if (!dirty) return;
    const t = window.setTimeout(() => {
      api.previewOfferComparison(doc).then((r) => { setPreviewed(r.derived as unknown as ComparisonFigures); setPreviewError(null); }).catch(setPreviewError);
    }, 400);
    return () => window.clearTimeout(t);
  }, [doc, dirty]);
  // The saved figures until there are changes; then the latest preview of them (figures shown are
  // never from a version other than the saved one or a newer draft).
  const figures: ComparisonFigures = dirty && previewed ? previewed : (saved.derived as unknown as ComparisonFigures);
  const figureError = dirty ? previewError : null;

  const offers = doc.offers ?? [];
  const factors = doc.factors ?? [];
  const rates = doc.conversions ?? [];
  const currencies = useMemo(() => [...new Set((doc.offers ?? []).map((o) => o.currency).filter(Boolean))] as string[], [doc.offers]);
  const change = (patch: Partial<ComparisonDoc>) => setDoc((d) => ({ ...d, ...patch }));
  const setTerm = (id: string, patch: Partial<OfferTerms>) => change({ offers: offers.map((o) => (o.id === id ? { ...o, ...patch } : o)) });
  const setFactor = (id: string, patch: Partial<OfferFactor>) => change({ factors: factors.map((f) => (f.id === id ? { ...f, ...patch } : f)) });
  const setRate = (i: number, patch: Partial<CurrencyRate>) => change({ conversions: rates.map((r, j) => (j === i ? { ...r, ...patch } : r)) });
  const num = (v: string) => (v.trim() === "" ? null : Number(v));

  function addFactor(name: string) {
    const label = name.trim();
    if (!label || factors.length >= 12) return;
    let id = slug(label);
    while (factors.some((f) => f.id === id)) id = `${id.slice(0, 14)}-${factors.length}`;
    change({ factors: [...factors, { id, label, weight: null, ratings: {} }] });
    setCustom("");
  }

  async function save(over?: number) {
    setBusy(true);
    setError(null);
    setStatus("");
    const expected = over ?? base;
    try {
      const next = await api.saveOfferComparison(saved.id, { doc, expected_revision: expected, client_request_id: keys.keyFor({ doc, expected }) });
      keys.done();
      setAgainst(null);
      setBase(next.revision);
      setDoc(next.doc);
      qc.setQueryData(["me", "offer-comparison", saved.id], next);
      void qc.invalidateQueries({ queryKey: ["me", "offer-comparisons"] });
      setStatus(next.save_replay ? `Saved as version ${next.save_replay.accepted_revision} (your earlier save went through).` : `Saved as version ${next.revision}. Only you can see it.`);
    } catch (e) {
      if (e instanceof ApiError && e.code === "stale_revision") setAgainst(savedVersion<OfferComparison>(e.details) ?? null);
      else setError(e);
    } finally {
      setBusy(false);
    }
  }

  async function restore() {
    setRestoring(true);
    try {
      const next = await api.archiveOfferComparison(saved.id, false);
      setArchivedNow(next.archived);
      qc.setQueryData(["me", "offer-comparison", saved.id], (old: OfferComparison | undefined) => (old ? { ...old, archived: next.archived } : old));
      void qc.invalidateQueries({ queryKey: ["me", "offer-comparisons"] });
      void qc.invalidateQueries({ queryKey: ["me", "recent-work"] });
      setStatus("Restored to your active comparisons, unchanged.");
    } catch (e) {
      setError(e);
    } finally {
      setRestoring(false);
    }
  }

  return (
    <div className={`page oc-page${hidden ? " is-hidden" : ""}`}>
      <BackLink fallback={{ to: "/offers/compare", label: "Compare offers" }} />
      <div className="page__header">
        <div>
          <p className="eyebrow">COMPARE OFFERS · PRIVATE</p>
          <label className="field oc-title">
            <span className="field__label">Comparison name</span>
            <input className="input" maxLength={80} value={doc.title} onChange={(e) => change({ title: e.target.value })} />
          </label>
          <p className="subtle">It organises the facts you enter and your own priorities. It doesn't choose for you, and nothing here changes an application.</p>
        </div>
      </div>
      {archivedNow && (
        <p className="banner banner--info row" role="note">
          <span>Archived: it's out of your active list, kept exactly as it is. Nothing was deleted.</span>
          <Button size="sm" loading={restoring} onClick={() => void restore()}>Restore</Button>
        </p>
      )}
      {offer === "open" && onDevice && (
        <section className="banner banner--info stack-sm" aria-labelledby="oc-device">
          <h2 className="section-title" id="oc-device">Unsaved changes</h2>
          <p>This device has changes you didn't save (from version {onDevice.base}).</p>
          <span className="row">
            <Button size="sm" variant="primary" onClick={() => { setDoc(onDevice.doc); setBase(onDevice.base); setOffer("restored"); }}>Restore them</Button>
            <Button size="sm" variant="ghost" onClick={() => { try { localStorage.removeItem(deviceKey); } catch { /* nothing */ } setOffer("dismissed"); }}>Discard them</Button>
          </span>
        </section>
      )}
      <div className="row oc-toolbar">
        <Button variant="primary" loading={busy} disabled={!dirty} onClick={() => void save()}>Save</Button>
        <label className="row"><input type="checkbox" checked={hidden} onChange={(e) => setHidden(e.target.checked)} /> Hide amounts on screen</label>
        <Button variant="ghost" onClick={() => setPreview(asText(doc, figures))}>Copy as text…</Button>
        <span className="subtle" role="status">{status || (dirty ? "Unsaved changes, kept on this device" : `Version ${base}, saved ${timeAgo(saved.updated_at)}`)}</span>
      </div>
      <InlineError error={error} />
      {against && (
        <VersionConflict what="comparison" savedWhen={`version ${against.revision}, ${timeAgo(against.updated_at)}`} busy={busy} keepMineLabel="Keep mine as the newest"
          fields={[{ label: "The comparison", mine: asText(doc, figures), saved: asText(against.doc, against.derived as unknown as ComparisonFigures) }]}
          onKeepMine={() => void save(against.revision)}
          onUseSaved={() => { setDoc(against.doc); setBase(against.revision); setAgainst(null); qc.setQueryData(["me", "offer-comparison", saved.id], against); }} />
      )}
      {preview !== null && (
        <section className="card stack-sm" role="dialog" aria-labelledby="oc-preview-title" aria-modal="false">
          <h2 className="section-title" id="oc-preview-title">Copy as text: exactly this</h2>
          <pre className="oc-preview">{preview}</pre>
          <p className="subtle">Copying puts this on your clipboard. Nothing is sent, shared or published.</p>
          <span className="row">
            <Button size="sm" variant="primary" onClick={() => { void navigator.clipboard?.writeText(preview).then(() => setStatus("Copied to your clipboard."), () => setStatus("Your browser didn't allow copying; select the text instead.")); }}>Copy</Button>
            <Button size="sm" variant="ghost" onClick={() => setPreview(null)}>Close</Button>
          </span>
        </section>
      )}

      <section className="stack-sm" aria-labelledby="oc-offers">
        <h2 className="section-title" id="oc-offers">The offers ({offers.length} of 3)</h2>
        <div className="oc-columns">
          {offers.map((o) => (
            <fieldset key={o.id} className="card stack-sm oc-offer">
              <legend className="visually-hidden">{o.label}</legend>
              <label className="field"><span className="field__label">Name</span><input className="input" maxLength={80} value={o.label} onChange={(e) => setTerm(o.id, { label: e.target.value })} /></label>
              <label className="field"><span className="field__label">Linked application (optional)</span>
                <select className="input" value={o.application_id ?? ""} onChange={(e) => setTerm(o.id, { application_id: e.target.value || null })}>
                  <option value="">Not linked</option>
                  {(apps.data ?? []).map((a) => <option key={a.id} value={a.id}>{a.role_title} at {a.employer}</option>)}
                </select>
              </label>
              <label className="field"><span className="field__label">Where these terms came from</span><input className="input" maxLength={300} value={o.source_note ?? ""} onChange={(e) => setTerm(o.id, { source_note: e.target.value })} /></label>
              <label className="field"><span className="field__label">Terms as of</span><input className="input" type="date" value={o.terms_as_of ?? ""} onChange={(e) => setTerm(o.id, { terms_as_of: e.target.value || null })} /></label>
              <div className="oc-pair">
                <label className="field"><span className="field__label">Pay</span><input className="input oc-money" type="number" min={0} step="any" value={o.pay_amount ?? ""} onChange={(e) => setTerm(o.id, { pay_amount: num(e.target.value) })} /></label>
                <label className="field"><span className="field__label">Per</span>
                  <select className="input" value={o.pay_period ?? ""} onChange={(e) => setTerm(o.id, { pay_period: (e.target.value || null) as OfferTerms["pay_period"] })}>
                    <option value="">Not entered</option>{Object.entries(PERIODS).map(([k, v]) => <option key={k} value={k}>{v.replace(/^an? /, "")}</option>)}
                  </select>
                </label>
                <label className="field"><span className="field__label">Currency (3 letters)</span><input className="input" maxLength={3} value={o.currency ?? ""} onChange={(e) => setTerm(o.id, { currency: e.target.value.toUpperCase() || null })} /></label>
              </div>
              <div className="oc-pair">
                {o.pay_period === "month" && <label className="field"><span className="field__label">Monthly payments a year</span><input className="input" type="number" min={1} max={14} step="any" value={o.months_paid ?? ""} onChange={(e) => setTerm(o.id, { months_paid: num(e.target.value) })} /></label>}
                {o.pay_period === "hour" && <label className="field"><span className="field__label">Hours a week</span><input className="input" type="number" min={1} max={100} step="any" value={o.hours_per_week ?? ""} onChange={(e) => setTerm(o.id, { hours_per_week: num(e.target.value) })} /></label>}
                {(o.pay_period === "hour" || o.pay_period === "week") && <label className="field"><span className="field__label">Weeks paid a year</span><input className="input" type="number" min={1} max={53} step="any" value={o.weeks_per_year ?? ""} onChange={(e) => setTerm(o.id, { weeks_per_year: num(e.target.value) })} /></label>}
              </div>
              <label className="field"><span className="field__label">Guaranteed one-off cash (0 if none; blank if unknown)</span><input className="input oc-money" type="number" min={0} step="any" value={o.guaranteed_extra ?? ""} onChange={(e) => setTerm(o.id, { guaranteed_extra: num(e.target.value) })} /></label>
              <label className="field"><span className="field__label">Conditional bonus (up to; blank if unknown)</span><input className="input oc-money" type="number" min={0} step="any" value={o.bonus_amount ?? ""} onChange={(e) => setTerm(o.id, { bonus_amount: num(e.target.value) })} /></label>
              <label className="field"><span className="field__label">Bonus conditions</span><input className="input" maxLength={200} value={o.bonus_note ?? ""} onChange={(e) => setTerm(o.id, { bonus_note: e.target.value })} /></label>
              <label className="field"><span className="field__label">Equity (described, never valued)</span><input className="input" maxLength={300} value={o.equity_note ?? ""} onChange={(e) => setTerm(o.id, { equity_note: e.target.value })} /></label>
              <label className="field"><span className="field__label">Benefits</span><input className="input" maxLength={300} value={o.benefits_note ?? ""} onChange={(e) => setTerm(o.id, { benefits_note: e.target.value })} /></label>
              <Button size="sm" variant="ghost" onClick={() => change({ offers: offers.filter((x) => x.id !== o.id), factors: factors.map((f) => ({ ...f, ratings: Object.fromEntries(Object.entries(f.ratings ?? {}).filter(([k]) => k !== o.id)) })) })}>Remove “{o.label}”</Button>
            </fieldset>
          ))}
        </div>
        {offers.length < 3 && <Button variant="secondary" onClick={() => change({ offers: [...offers, blankOffer(["a", "b", "c"].find((x) => !offers.some((o) => o.id === x)) ?? "c")] })}>Add an offer</Button>}
      </section>

      <section className="card stack-sm" aria-labelledby="oc-factors">
        <h2 className="section-title" id="oc-factors">What matters to you</h2>
        <p className="subtle">Your own ratings, 1 to 5, or unknown, or not comparable. They're subjective; nothing here judges an employer.</p>
        <span className="row oc-suggest">
          {SUGGESTED.filter((s) => !factors.some((f) => f.label === s)).map((s) => <Button key={s} size="sm" variant="ghost" onClick={() => addFactor(s)}>Add “{s}”</Button>)}
        </span>
        <span className="row">
          <label className="field"><span className="field__label">Your own factor</span><input className="input" maxLength={60} value={custom} onChange={(e) => setCustom(e.target.value)} /></label>
          <Button size="sm" variant="secondary" disabled={!custom.trim()} onClick={() => addFactor(custom)}>Add</Button>
        </span>
        {factors.map((f) => (
          <fieldset key={f.id} className="oc-factor stack-sm">
            <legend><strong>{f.label}</strong></legend>
            <div className="oc-columns">
              {offers.map((o) => {
                const r = f.ratings?.[o.id] ?? { state: "unknown", value: null, note: "" };
                const shown = r.state === "rated" ? String(r.value) : r.state;
                return (
                  <div key={o.id} className="stack-sm">
                    <label className="field"><span className="field__label">{o.label}: your rating</span>
                      <select className="input" value={shown} onChange={(e) => {
                        const v = e.target.value;
                        const next: Pick<OfferRating, "state" | "value"> = v === "unknown" || v === "not_comparable" ? { state: v, value: null } : { state: "rated", value: Number(v) };
                        setFactor(f.id, { ratings: { ...(f.ratings ?? {}), [o.id]: { ...r, ...next } } });
                      }}>
                        <option value="unknown">Unknown</option><option value="not_comparable">Not comparable</option>
                        {[1, 2, 3, 4, 5].map((n) => <option key={n} value={String(n)}>{n} of 5</option>)}
                      </select>
                    </label>
                    <label className="field"><span className="field__label">{o.label}: note</span><input className="input" maxLength={200} value={r.note ?? ""} onChange={(e) => setFactor(f.id, { ratings: { ...(f.ratings ?? {}), [o.id]: { ...r, note: e.target.value } } })} /></label>
                  </div>
                );
              })}
            </div>
            <span className="row">
              <label className="field"><span className="field__label">Weight (optional)</span>
                <select className="input" value={f.weight ?? ""} onChange={(e) => setFactor(f.id, { weight: e.target.value === "" ? null : Number(e.target.value) })}>
                  <option value="">None</option>{[0, 1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
                </select>
              </label>
              <Button size="sm" variant="ghost" onClick={() => change({ factors: factors.filter((x) => x.id !== f.id) })}>Remove “{f.label}”</Button>
            </span>
          </fieldset>
        ))}
        <label className="row"><input type="checkbox" checked={doc.weights_on ?? false} onChange={(e) => change({ weights_on: e.target.checked })} /> Use my weights to order the offers (you can turn this off)</label>
      </section>

      <section className="card stack-sm" aria-labelledby="oc-rates">
        <h2 className="section-title" id="oc-rates">Currencies</h2>
        <p className="subtle">Offers in different currencies stay apart unless you enter a rate with its date. No market rate is looked up.</p>
        {rates.map((r, i) => (
          <span key={i} className="row oc-rate">
            <label className="field"><span className="field__label">From</span><input className="input" maxLength={3} value={r.from_currency} onChange={(e) => setRate(i, { from_currency: e.target.value.toUpperCase() })} /></label>
            <label className="field"><span className="field__label">To</span><input className="input" maxLength={3} value={r.to_currency} onChange={(e) => setRate(i, { to_currency: e.target.value.toUpperCase() })} /></label>
            <label className="field"><span className="field__label">Rate</span><input className="input" type="number" min={0} step="any" value={r.rate} onChange={(e) => setRate(i, { rate: Number(e.target.value) })} /></label>
            <label className="field"><span className="field__label">As of</span><input className="input" type="date" value={r.as_of} onChange={(e) => setRate(i, { as_of: e.target.value })} /></label>
            <Button size="sm" variant="ghost" onClick={() => change({ conversions: rates.filter((_, j) => j !== i) })}>Remove rate</Button>
          </span>
        ))}
        {rates.length < 6 && currencies.length > 1 && (
          <Button size="sm" variant="secondary" onClick={() => change({ conversions: [...rates, { from_currency: currencies[0]!, to_currency: currencies[1]!, rate: 1, as_of: new Date().toISOString().slice(0, 10), note: "" }] })}>Add a rate</Button>
        )}
        <label className="field"><span className="field__label">Also show figures in</span>
          <select className="input" value={doc.show_in ?? ""} onChange={(e) => change({ show_in: e.target.value || null })}>
            <option value="">Each offer's own currency only</option>{currencies.map((cur) => <option key={cur} value={cur}>{cur}</option>)}
          </select>
        </label>
      </section>

      <InlineError error={figureError} />
      <Figures doc={doc} figures={figures} />
      <p className="subtle">Saved comparisons are private to your account, included in your data export and deleted with it. <Link to="/applications">Applications</Link> are only changed from their own page.</p>
    </div>
  );
}
