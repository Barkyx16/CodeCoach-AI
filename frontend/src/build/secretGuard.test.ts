import { leakedServerSecrets, secretLookingPublicVars } from "./secretGuard";

describe("build secret guard", () => {
  it("flags public VITE_* variables named like secrets, and only those", () => {
    const env = {
      VITE_API_BASE_URL: "http://localhost:8000",
      VITE_SERVICE_WORKER: "1",
      VITE_STRIPE_SECRET_KEY: "x",
      VITE_ANTHROPIC_API_KEY: "x",
      VITE_GITHUB_TOKEN: "x",
      VITE_DB_PASSWORD: "x",
      SECRET_KEY: "server-only, not published by Vite",
    };
    expect(secretLookingPublicVars(env)).toEqual(["VITE_ANTHROPIC_API_KEY", "VITE_DB_PASSWORD", "VITE_GITHUB_TOKEN", "VITE_STRIPE_SECRET_KEY"]);
  });

  it("finds a server secret's value in built code by name, without reporting the value", () => {
    const env = { SECRET_KEY: "synthetic-signing-key-0123456789abcdef", ANTHROPIC_API_KEY: "sk-ant-synthetic-0123456789", RUNNER_TOKEN: undefined };
    expect(leakedServerSecrets(`const k="${env.ANTHROPIC_API_KEY}";`, env)).toEqual(["ANTHROPIC_API_KEY"]);
    expect(leakedServerSecrets("const nothing = 1;", env)).toEqual([]);
  });

  it("checks each previous key, and ignores values too short to tell from ordinary words", () => {
    const env = { SECRET_KEY_PREVIOUS: "old-synthetic-key-aaaaaaaaaaaa, older-synthetic-key-bbbbbbbbbb", POSTGRES_PASSWORD: "codecoach" };
    expect(leakedServerSecrets("x older-synthetic-key-bbbbbbbbbb y", env)).toEqual(["SECRET_KEY_PREVIOUS"]);
    expect(leakedServerSecrets("Welcome to codecoach", env)).toEqual([]);
  });
});
