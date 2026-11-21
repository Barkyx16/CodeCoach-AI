import { useId } from "react";

import { Button } from "@/components/Button";

import { DEFAULT_DISPLAY, useDisplayPrefs, type DisplayPrefs } from "./displayPrefs";

type Option<K extends keyof DisplayPrefs> = { value: DisplayPrefs[K]; label: string };

function Choice<K extends keyof DisplayPrefs>({ name, legend, hint, options }: { name: K; legend: string; hint?: string; options: Option<K>[] }) {
  const { prefs, update } = useDisplayPrefs();
  const id = useId();
  return (
    <fieldset className="field display-choice" aria-describedby={hint ? `${id}-hint` : undefined}>
      <legend className="field__label">{legend}</legend>
      <div className="segmented">
        {options.map((o) => (
          <label key={o.value} className={`segmented__option${prefs[name] === o.value ? " segmented__option--active" : ""}`}>
            <input type="radio" name={`display-${name}`} value={o.value} checked={prefs[name] === o.value}
              onChange={() => update({ [name]: o.value } as Partial<DisplayPrefs>)} />
            {o.label}
          </label>
        ))}
      </div>
      {hint && <p className="subtle display-choice__hint" id={`${id}-hint`}>{hint}</p>}
    </fieldset>
  );
}

/** Theme, contrast, text size, spacing and motion. Presentation only; stored in this browser. */
export function DisplayControls() {
  const { prefs, reset, persisted } = useDisplayPrefs();
  const isDefault = JSON.stringify(prefs) === JSON.stringify(DEFAULT_DISPLAY);
  return (
    <div className="stack display-controls">
      <Choice name="theme" legend="Theme" options={[{ value: "system", label: "Match device" }, { value: "light", label: "Light" }, { value: "dark", label: "Dark" }]} />
      <Choice name="contrast" legend="Contrast" hint="Stronger text and borders. Text colours are checked to at least 7:1 against page, card and tinted backgrounds."
        options={[{ value: "standard", label: "Standard" }, { value: "high", label: "Higher" }]} />
      <Choice name="text" legend="Text size" hint="Applies to the whole app. The code editor keeps its own font size (see Editor)."
        options={[{ value: "default", label: "Default" }, { value: "large", label: "Large" }, { value: "larger", label: "Larger" }]} />
      <Choice name="spacing" legend="Reading layout" hint="More space between lines and paragraphs in questions, lessons and feedback."
        options={[{ value: "default", label: "Standard" }, { value: "spacious", label: "Spacious" }]} />
      <Choice name="motion" legend="Motion" hint="Your device's reduced-motion setting is always followed; this also reduces motion here."
        options={[{ value: "system", label: "Follow device" }, { value: "reduce", label: "Reduce" }]} />
      <div className="row display-controls__footer">
        <Button size="sm" variant="ghost" disabled={isDefault} onClick={reset}>Reset to defaults</Button>
        <span className="subtle" role="status">
          {persisted ? "Saved in this browser." : "This browser won't store settings (private mode or blocked site data), so they apply for this visit only."}
        </span>
      </div>
    </div>
  );
}
