import { PHASES } from "./phases";

/** Shows where the candidate is in the interview arc. Completed steps are marked with text, not just color. */
export function PhaseStepper({ phaseIndex }: { phaseIndex: number }) {
  return (
    <ol className="stepper" aria-label="Interview progress">
      {PHASES.map((p, i) => {
        const state = i < phaseIndex ? "done" : i === phaseIndex ? "current" : "upcoming";
        return (
          <li key={p.id} className={`stepper__step stepper__step--${state}`} aria-current={state === "current" ? "step" : undefined}>
            <span className="stepper__dot" aria-hidden="true">{state === "done" ? "✓" : i + 1}</span>
            <span className="stepper__label">{p.label}</span>
            <span className="visually-hidden">{state === "done" ? " (done)" : state === "current" ? " (current)" : ""}</span>
          </li>
        );
      })}
    </ol>
  );
}
