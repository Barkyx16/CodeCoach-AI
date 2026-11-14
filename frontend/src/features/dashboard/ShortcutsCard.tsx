import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { useCapabilities } from "@/api/queries";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/Button";
import { Icon } from "@/components/Icon";

import {
  DEFAULT_SHORTCUTS, SHORTCUTS_LIMIT, type StoredShortcuts,
  readShortcuts, resetShortcuts, resolveShortcuts, sameList, saveShortcuts, shortcutCatalog, shortcutsKey,
} from "./shortcuts";

const SCOPE = "Kept in this browser for your account: another device, or another account on this one, has its own list. "
  + "Only page names are kept, nothing from your records.";
const listOf = (names: string[]) => (names.length > 1 ? `${names.slice(0, -1).join(", ")} and ${names.at(-1)}` : names.join(""));
const NOT_KEPT = "This browser didn't keep it, so the change lasts only until you leave this page.";

/**
 * "Your shortcuts" on the dashboard (Volume 11, prompt 2; docs/SHORTCUTS.md): pages the learner
 * keeps one click away. Each one is a plain link to a page the router has (the palette's commands);
 * opening it starts nothing. Edit shortcuts adds, moves and removes them with buttons that work by
 * keyboard and touch: focus stays on the item that moved and its new place is announced. Reset to
 * defaults only changes this list. Arranging them changes nothing on the account.
 */
export function ShortcutsCard({ coding, careerTitle }: { coding: boolean; careerTitle?: string }) {
  const { user } = useAuth();
  if (!user) return null;
  return <Shortcuts key={user.id} userId={user.id} coding={coding} careerTitle={careerTitle} />;
}

function Shortcuts({ userId, coding, careerTitle }: { userId: string; coding: boolean; careerTitle?: string }) {
  const capabilities = useCapabilities();
  const executionEnabled = capabilities.data?.execution_enabled ?? true;
  const demoMode = capabilities.data?.demo_mode === true;
  const catalog = useMemo(() => shortcutCatalog({ coding, executionEnabled, demoMode }), [coding, executionEnabled, demoMode]);
  const [stored, setStored] = useState<StoredShortcuts>(() => readShortcuts(userId));
  const [ids, setIds] = useState<string[]>(stored.ids);
  const [unsaved, setUnsaved] = useState(false);
  const [editing, setEditing] = useState(false);
  const [said, setSaid] = useState("");
  const [adding, setAdding] = useState("");
  const focusNext = useRef<string | null>(null);
  const editorRef = useRef<HTMLDivElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const base = useId();

  // Another tab of this browser changed the list: show what's stored now.
  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      if (event.key !== null && event.key !== shortcutsKey(userId)) return;
      const next = readShortcuts(userId);
      setStored(next);
      setIds(next.ids);
      setUnsaved(false);
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [userId]);

  useEffect(() => {
    const target = focusNext.current;
    if (!target) return;
    focusNext.current = null;
    editorRef.current?.querySelector<HTMLElement>(`[data-focus="${target}"]`)?.focus();
  });

  const items = resolveShortcuts(ids, catalog, careerTitle);
  const labelOf = (id: string) => items.find((s) => s.id === id)?.label ?? catalog.find((s) => s.id === id)?.label ?? id;
  const addable = catalog.filter((s) => !s.unavailable && !ids.includes(s.id));
  const sections = [...new Set(addable.map((s) => s.section))];
  const isDefault = sameList(ids, DEFAULT_SHORTCUTS);

  function apply(next: string[], message: string, focus: string | null) {
    const kept = saveShortcuts(userId, next);
    setIds(next);
    setUnsaved(!kept);
    if (kept) setStored({ ids: next, custom: true, dropped: 0, unreadable: false });
    setSaid(kept ? message : `${message} ${NOT_KEPT}`);
    focusNext.current = focus;
  }

  function move(id: string, by: -1 | 1) {
    const from = ids.indexOf(id);
    const to = from + by;
    if (to < 0 || to >= ids.length) {
      setSaid(`${labelOf(id)} is already ${by < 0 ? "first" : "last"}.`);
      return;
    }
    const next = [...ids];
    next.splice(from, 1);
    next.splice(to, 0, id);
    apply(next, `${labelOf(id)} moved to position ${to + 1} of ${next.length}.`, `${by < 0 ? "up" : "down"}:${id}`);
  }

  function remove(id: string) {
    const at = ids.indexOf(id);
    const next = ids.filter((x) => x !== id);
    const neighbour = next[at] ?? next[at - 1];
    apply(next, `${labelOf(id)} removed. ${next.length ? `${next.length} ${next.length === 1 ? "shortcut" : "shortcuts"} left.` : "No shortcuts left."}`,
      neighbour ? `remove:${neighbour}` : "add");
  }

  function add() {
    if (!adding) {
      setSaid("Choose a page to add first.");
      return;
    }
    if (ids.includes(adding) || ids.length >= SHORTCUTS_LIMIT) return;
    const next = [...ids, adding];
    setAdding("");
    apply(next, `${labelOf(adding)} added as shortcut ${next.length} of ${next.length}.`, next.length >= SHORTCUTS_LIMIT ? "done" : "add");
  }

  function reset() {
    const kept = resetShortcuts(userId);
    setIds([...DEFAULT_SHORTCUTS]);
    setUnsaved(!kept);
    if (kept) setStored({ ids: [...DEFAULT_SHORTCUTS], custom: false, dropped: 0, unreadable: false });
    setSaid(`${kept ? "Shortcuts are back to the defaults." : `Shortcuts are back to the defaults on this page. ${NOT_KEPT}`} Nothing else changed.`);
    focusNext.current = "reset";
  }

  function finish() {
    setEditing(false);
    setSaid("");
    toggleRef.current?.focus();
  }

  const dropped = !unsaved && (stored.unreadable
    ? "Your saved shortcuts couldn't be read, so the defaults are shown."
    : stored.dropped > 0
      ? `${stored.dropped === 1 ? "One saved shortcut is" : `${stored.dropped} saved shortcuts are`} no longer offered, so ${stored.dropped === 1 ? "it isn't" : "they aren't"} shown.`
      : null);

  return (
    <section className="card stack shortcuts" aria-labelledby={`${base}-title`}>
      <div className="shortcuts__head">
        <h2 id={`${base}-title`} className="section-title"><Icon name="link" size={16} />Your shortcuts</h2>
        <button ref={toggleRef} type="button" className="btn btn--ghost btn--sm" aria-expanded={editing} aria-controls={`${base}-editor`}
          onClick={() => (editing ? finish() : setEditing(true))}>
          Edit shortcuts
        </button>
      </div>

      {!editing && (items.length ? (
        <ul className="shortcuts__list">
          {items.map((s) => (
            <li key={s.id}>
              {s.unavailable ? (
                <span className="shortcut shortcut--off">
                  <span className="shortcut__label">{s.label}</span>
                  <span className="shortcut__note">{s.unavailable}</span>
                </span>
              ) : (
                <Link className="shortcut" to={s.to}>
                  <span className="shortcut__label">{s.label}</span>
                  {s.note && <span className="shortcut__note">{s.note}</span>}
                </Link>
              )}
            </li>
          ))}
        </ul>
      ) : <p className="subtle">No shortcuts yet. Use Edit shortcuts to keep a page you use often one click away.</p>)}

      {!editing && dropped && <p className="subtle">{dropped}</p>}
      {unsaved && !editing && <p className="subtle">{NOT_KEPT}</p>}

      {editing && (
        <div id={`${base}-editor`} ref={editorRef} className="stack shortcuts__editor">
          <p className="subtle">{SCOPE}</p>
          {said && <p className="shortcuts__said" aria-hidden="true">{said}</p>}
          {items.length ? (
            <ol className="shortcuts__edit-list">
              {items.map((s, i) => (
                <li key={s.id} className="shortcut-edit">
                  <span className="shortcut-edit__name">
                    <strong>{s.label}</strong>
                    {s.unavailable && <span className="subtle"> {s.unavailable}</span>}
                  </span>
                  <span className="shortcut-edit__actions">
                    <Button size="sm" data-focus={`up:${s.id}`} aria-label={`Move up: ${s.label}`} aria-disabled={i === 0 || undefined}
                      onClick={() => move(s.id, -1)}>Move up</Button>
                    <Button size="sm" data-focus={`down:${s.id}`} aria-label={`Move down: ${s.label}`} aria-disabled={i === items.length - 1 || undefined}
                      onClick={() => move(s.id, 1)}>Move down</Button>
                    <Button size="sm" variant="ghost" data-focus={`remove:${s.id}`} aria-label={`Remove ${s.label}`} onClick={() => remove(s.id)}>Remove</Button>
                  </span>
                </li>
              ))}
            </ol>
          ) : <p className="subtle">No shortcuts. Add a page below.</p>}

          {ids.length >= SHORTCUTS_LIMIT ? (
            <p className="subtle">That's {SHORTCUTS_LIMIT} shortcuts, the most there can be. Remove one to add another.</p>
          ) : addable.length > 0 && (
            <div className="shortcuts__add">
              <label htmlFor={`${base}-add`}>Add a shortcut</label>
              <div className="shortcuts__add-row">
                <select id={`${base}-add`} className="select" data-focus="add" value={adding} onChange={(e) => setAdding(e.target.value)}>
                  <option value="">Choose a page…</option>
                  {sections.map((section) => (
                    <optgroup key={section} label={section}>
                      {addable.filter((s) => s.section === section).map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
                    </optgroup>
                  ))}
                </select>
                <Button size="sm" onClick={add} aria-disabled={!adding || undefined}>Add</Button>
              </div>
            </div>
          )}

          <div className="shortcuts__foot">
            <Button size="sm" variant="ghost" data-focus="reset" onClick={reset} aria-describedby={`${base}-reset`}>Reset to defaults</Button>
            <Button size="sm" variant="primary" data-focus="done" onClick={finish}>Done</Button>
          </div>
          <p id={`${base}-reset`} className="subtle">
            Reset puts back {listOf(DEFAULT_SHORTCUTS.map(labelOf))}{isDefault ? " (what's here now)" : ""}. It only changes this list.
          </p>
        </div>
      )}
      {/* Always in the page, so a screen reader announces each change; shown while editing. */}
      <p className="visually-hidden" role="status">{said}</p>
    </section>
  );
}
