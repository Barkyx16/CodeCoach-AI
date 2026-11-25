/**
 * Runs once, after Playwright has started (or found) the web servers and before any test. Refuses
 * to continue against an API that isn't this run's test server, or whose judge doesn't match
 * E2E_JUDGE, rather than letting tests fail obscurely, or write into a developer's database. It
 * never stops the other server: that's for whoever started it. scripts/e2e-run.mjs --list shows
 * servers that e2e runs started.
 */
import { apiProblems } from "../src/build/serverCheck";
import { API_URL, INSTANCE_LABEL, PORTS } from "./ports";

export default async function globalSetup(): Promise<void> {
  const judge = process.env.E2E_JUDGE === "1";
  const problems = await apiProblems(API_URL, { label: INSTANCE_LABEL, judge }, { waitMs: judge ? 60_000 : 0 });
  if (problems.length) {
    throw new Error(
      `This e2e run won't use the API on port ${PORTS.api}:\n- ${problems.join("\n- ")}\n` +
        "Stop that server yourself if it's yours (`npm run e2e:owned` lists servers that e2e runs started), " +
        "or run this suite on other ports: E2E_PORT_OFFSET=10 npm run e2e",
    );
  }
}
