/**
 * The demo run uses only its own demo API: one that answers as "e2e-demo" (never a developer's
 * server, never the main e2e suite's).
 */
import { apiProblems } from "../src/build/serverCheck";

export default async function globalSetup(): Promise<void> {
  const offset = Number(process.env.E2E_PORT_OFFSET ?? "50");
  const api = `http://localhost:${8000 + offset}`;
  const problems = await apiProblems(api, { label: "e2e-demo", judge: false });
  if (problems.length) throw new Error(`The demo run won't use the API at ${api}:\n- ${problems.join("\n- ")}`);
}
