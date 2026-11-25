import { PASSWORD_RULES } from "@/lib/passwordRules";

export function PasswordChecklist({ password }: { password: string }) {
  return (
    <ul className="password-rules" aria-label="Password requirements">
      {PASSWORD_RULES.map((rule) => {
        const ok = rule.test(password);
        return (
          <li key={rule.id} className={ok ? "password-rules__ok" : undefined}>
            <span aria-hidden="true">{ok ? "✓" : "○"}</span> {rule.label}
            <span className="visually-hidden">{ok ? " (met)" : " (not met yet)"}</span>
          </li>
        );
      })}
    </ul>
  );
}
