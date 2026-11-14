import { type KeyboardEvent, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";

import { useCapabilities, useCareers } from "@/api/queries";
import { useAuth } from "@/auth/useAuth";
import { DEFAULT_TRACK } from "@/features/careers/practiceTrack";

import { type Command, commandsFor, readRecent, rememberRecent, searchCommands } from "./commands";

interface Group { title: string; commands: Command[] }

/**
 * Go to a page by typing (docs/NAVIGATION.md "Command palette"). A modal <dialog> (the browser's
 * own focus handling: the page behind is inert, Escape closes) with a combobox: type to filter,
 * arrow keys to move, Enter to open, Escape or Close to leave. Choosing a command closes the dialog
 * first and then navigates through the router, so a page with unsaved work still asks before it's
 * left. Focus goes back to whatever opened the palette; after a navigation the new page takes it.
 */
export function CommandPalette({ opener, onClose, onGo }: {
  opener: HTMLElement | null;
  onClose: () => void;
  onGo: (to: string) => void;
}) {
  const { user, isAuthenticated } = useAuth();
  const capabilities = useCapabilities();
  const careers = useCareers();
  const track = user?.career_track ?? DEFAULT_TRACK;
  const career = careers.data?.find((c) => c.slug === track);
  const commands = useMemo(() => commandsFor({
    signedIn: isAuthenticated,
    isAdmin: Boolean(user?.is_admin),
    coding: career ? career.has_coding : track === DEFAULT_TRACK,
    executionEnabled: capabilities.data?.execution_enabled ?? true,
    demoMode: capabilities.data?.demo_mode === true,
  }), [isAuthenticated, user?.is_admin, career, track, capabilities.data?.execution_enabled, capabilities.data?.demo_mode]);
  const userId = isAuthenticated ? user?.id ?? null : null;
  const [recent] = useState(() => (userId ? readRecent(userId) : []));

  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [said, setSaid] = useState("");
  const dialogRef = useRef<HTMLDialogElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const closed = useRef(false);
  const ids = useId();
  const listId = `${ids}-list`;
  const hintId = `${ids}-hint`;
  const optionId = (c: Command) => `${ids}-${c.id}`;

  const groups = useMemo<Group[]>(() => {
    if (query.trim()) {
      const found = searchCommands(commands, query);
      return found.length ? [{ title: "Matching pages", commands: found }] : [];
    }
    const recentCommands = recent.map((id) => commands.find((c) => c.id === id)).filter((c): c is Command => Boolean(c));
    const rest = commands.filter((c) => !recentCommands.includes(c));
    const sections: Group[] = recentCommands.length ? [{ title: "Recently used", commands: recentCommands }] : [];
    for (const c of rest) {
      const last = sections.at(-1);
      if (last && last.title === c.section) last.commands.push(c);
      else sections.push({ title: c.section, commands: [c] });
    }
    return sections;
  }, [commands, query, recent]);
  const flat = useMemo(() => groups.flatMap((g) => g.commands), [groups]);
  const current = flat[Math.min(active, flat.length - 1)];

  // Open as a modal (focus moves into it, the page behind can't be reached) and start in the field.
  useLayoutEffect(() => {
    const dialog = dialogRef.current;
    if (dialog && !dialog.open) dialog.showModal();
    inputRef.current?.focus();
  }, []);

  function close() {
    if (closed.current) return;
    closed.current = true;
    if (dialogRef.current?.open) dialogRef.current.close();
    // Back where the learner was. (If what opened it has gone, the page's main region.)
    if (opener?.isConnected) opener.focus({ preventScroll: true });
    else document.getElementById("main")?.focus({ preventScroll: true });
    onClose();
  }

  function choose(command: Command | undefined) {
    if (!command) return;
    if (command.unavailable) {
      setSaid(command.unavailable);
      return;
    }
    if (userId) rememberRecent(userId, command.id);
    close();
    onGo(command.to);
  }

  // The browser's own Escape (the dialog's cancel event) closes it the same way.
  useEffect(() => {
    const dialog = dialogRef.current;
    const cancel = (event: Event) => { event.preventDefault(); close(); };
    dialog?.addEventListener("cancel", cancel);
    return () => dialog?.removeEventListener("cancel", cancel);
  });

  useEffect(() => {
    if (current) document.getElementById(optionId(current))?.scrollIntoView?.({ block: "nearest" });
  });

  function onKeyDown(event: KeyboardEvent) {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!flat.length) return;
      const step = event.key === "ArrowDown" ? 1 : -1;
      setActive((i) => (Math.min(i, flat.length - 1) + step + flat.length) % flat.length);
      setSaid("");
    } else if (event.key === "Enter" && event.target === inputRef.current) {
      event.preventDefault();
      choose(current);
    } else if (event.key.toLowerCase() === "k" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault(); // already open: the shortcut just returns to the field
      inputRef.current?.select();
    }
  }

  const count = flat.length;
  const status = said || (query.trim()
    ? count ? `${count} ${count === 1 ? "page matches" : "pages match"}.` : "No page matches."
    : `${count} pages.`);

  return (
    <dialog ref={dialogRef} className="palette" aria-label="Go to a page" onKeyDown={onKeyDown}
      onClick={(event) => { if (event.target === event.currentTarget) close(); /* the backdrop */ }}>
      <div className="palette__panel">
        <div className="palette__top">
          <label className="palette__label" htmlFor={`${ids}-input`}>Go to a page</label>
          <button type="button" className="btn btn--ghost btn--sm palette__close" onClick={close}>Close</button>
        </div>
        <input id={`${ids}-input`} ref={inputRef} className="input palette__input" type="text" role="combobox"
          aria-expanded="true" aria-controls={listId} aria-autocomplete="list" aria-describedby={hintId}
          aria-activedescendant={current ? optionId(current) : undefined}
          autoComplete="off" autoCorrect="off" autoCapitalize="none" spellCheck={false} enterKeyHint="go"
          placeholder="Type a page, like notes or interview" value={query}
          onChange={(event) => { setQuery(event.target.value); setActive(0); setSaid(""); }} />
        <p className="visually-hidden" role="status">{status}</p>
        <div id={listId} role="listbox" aria-label="Pages" className="palette__list">
          {groups.map((group) => (
            <div key={group.title} role="group" aria-label={group.title} className="palette__group">
              <div className="palette__group-title" aria-hidden="true">{group.title}</div>
              {group.commands.map((command) => {
                const selected = command === current;
                return (
                  <div key={command.id} id={optionId(command)} role="option" aria-selected={selected}
                    aria-disabled={command.unavailable ? true : undefined}
                    className={`palette__option${selected ? " palette__option--active" : ""}${command.unavailable ? " palette__option--unavailable" : ""}`}
                    onMouseMove={() => { if (!selected) setActive(flat.indexOf(command)); }}
                    onMouseDown={(event) => event.preventDefault() /* typing stays in the field */}
                    onClick={() => choose(command)}>
                    <span className="palette__option-label">{command.label}</span>
                    <span className="palette__option-detail">{command.unavailable ?? command.note ?? command.detail}</span>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
        {!count && (
          <div className="palette__empty">
            <p><strong>No page matches “{query.trim()}”.</strong></p>
            <p className="subtle">Try another word, like “notes”, “plan” or “interview”. The palette finds pages, not what’s written in your notes or answers.</p>
          </div>
        )}
        <p id={hintId} className="palette__hint subtle">
          <span><kbd>↑</kbd> <kbd>↓</kbd> to move</span> <span><kbd>Enter</kbd> to open</span> <span><kbd>Esc</kbd> to close</span>
        </p>
      </div>
    </dialog>
  );
}
