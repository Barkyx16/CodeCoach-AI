/**
 * Build-time guard: keeps secrets out of what the browser downloads. Everything in the frontend
 * bundle is public, and Vite puts every VITE_* variable into it. Used by vite.config.ts, which
 * fails the build (or dev server start) on either check below. Nothing here runs in the app.
 */

/** Server-side secrets (backend/app/config.py, docker-compose.yml) that the bundle must never contain. */
export const SERVER_SECRET_VARS = [
  "SECRET_KEY",
  "SECRET_KEY_PREVIOUS",
  "ANTHROPIC_API_KEY",
  "RUNNER_TOKEN",
  "SMTP_PASSWORD",
  "POSTGRES_PASSWORD",
  "DATABASE_URL",
] as const;

const SECRET_NAME = /(SECRET|TOKEN|PASSWORD|PASSWD|PRIVATE|CREDENTIAL|API_?KEY|ACCESS_?KEY)/i;
// Shorter values (e.g. the dev database password "codecoach") also occur as ordinary words.
const MIN_CHECKED_LENGTH = 12;

type Env = Record<string, string | undefined>;

/** VITE_* variables whose names say they hold a secret: Vite would publish their values. */
export function secretLookingPublicVars(env: Env): string[] {
  return Object.keys(env)
    .filter((name) => name.startsWith("VITE_") && SECRET_NAME.test(name.slice("VITE_".length)))
    .sort();
}

/** Names (never values) of server secrets whose value appears in `code`. */
export function leakedServerSecrets(code: string, env: Env): string[] {
  const found: string[] = [];
  for (const name of SERVER_SECRET_VARS) {
    const raw = env[name];
    if (!raw) continue;
    const values = name === "SECRET_KEY_PREVIOUS" ? raw.split(",") : [raw];
    if (values.some((v) => v.trim().length >= MIN_CHECKED_LENGTH && code.includes(v.trim()))) found.push(name);
  }
  return found;
}
