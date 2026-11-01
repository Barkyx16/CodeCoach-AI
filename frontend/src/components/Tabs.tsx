import { useId, type ReactNode, type KeyboardEvent } from "react";

interface Tab<T extends string> { id: T; label: string }

/** Automatic activation with roving focus, as specified by the ARIA tabs pattern. */
export function Tabs<T extends string>({ label, tabs, value, onChange, children, className = "", listClassName = "", panelClassName = "" }: {
  label: string;
  tabs: readonly Tab<T>[];
  value: NoInfer<T>;
  onChange(value: NoInfer<T>): void;
  children: ReactNode;
  className?: string;
  listClassName?: string;
  panelClassName?: string;
}) {
  const id = useId();
  function handleKey(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const next = event.key === "ArrowRight" ? (index + 1) % tabs.length
      : event.key === "ArrowLeft" ? (index - 1 + tabs.length) % tabs.length
      : event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : null;
    if (next === null) return;
    event.preventDefault();
    const buttons = event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]');
    onChange(tabs[next]!.id);
    buttons?.[next]?.focus();
  }
  return (
    <div className={className}>
      <div className={`tabs ${listClassName}`} role="tablist" aria-label={label}>
        {tabs.map((tab, index) => (
          <button key={tab.id} type="button" role="tab" id={`${id}-tab-${tab.id}`}
            aria-controls={`${id}-panel-${tab.id}`} aria-selected={value === tab.id}
            tabIndex={value === tab.id ? 0 : -1} className={`tab${value === tab.id ? " tab--active" : ""}`}
            onClick={() => onChange(tab.id)} onKeyDown={(event) => handleKey(event, index)}>{tab.label}</button>
        ))}
      </div>
      <div role="tabpanel" id={`${id}-panel-${value}`} aria-labelledby={`${id}-tab-${value}`}
        className={panelClassName} tabIndex={0}>{children}</div>
    </div>
  );
}
