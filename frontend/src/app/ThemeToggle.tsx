import { resolvedTheme, useDisplayPrefs } from "@/features/display/displayPrefs";

/**
 * Light or dark in one press, in the sidebar's account block. It sets the same preference as
 * Settings › Display (kept in this browser only); "Match device" is chosen there.
 */
export function ThemeToggle() {
  const { prefs, update } = useDisplayPrefs();
  const next = resolvedTheme(prefs) === "dark" ? "light" : "dark";
  return (
    <button type="button" className="theme-toggle btn btn--ghost btn--sm" aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`} onClick={() => update({ theme: next })}>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"
        strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        {next === "dark" ? (
          <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" />
        ) : (
          <>
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
          </>
        )}
      </svg>
    </button>
  );
}
