import { describe, expect, it } from "vitest";

// @ts-expect-error: a plain .mjs build script, no type declarations
import { apiOrigin, fillTemplate } from "../../scripts/csp-origin.mjs";

describe("the API origin written into the web image's Content-Security-Policy", () => {
  it.each([
    ["https://api.example.com", "https://api.example.com"],
    ["https://api.example.com/", "https://api.example.com"],
    ["https://api.example.com/codecoach", "https://api.example.com"], // a path prefix: the app keeps it, the policy doesn't need it
    ["https://API.Example.COM", "https://api.example.com"], // browsers compare hosts lower-cased
    ["https://api.example.com:443", "https://api.example.com"], // the default port is no port
    ["https://api.example.com:8443", "https://api.example.com:8443"],
    ["http://127.0.0.1:18100", "http://127.0.0.1:18100"],
    ["HTTPS://api.example.com", "https://api.example.com"],
  ])("%s → %s", (value, origin) => {
    expect(apiOrigin(value)).toBe(origin);
  });

  it.each([
    ["", /empty/],
    ["api.example.com", /isn't a URL/],
    ["ftp://api.example.com", /http or https/],
    ["javascript:alert(1)", /http or https/],
    ["https://user:secret@api.example.com", /credentials/],
    ["https://api.example.com/?x=1", /query or a fragment/],
    ["https://api.example.com/#frag", /query or a fragment/],
    ["http://[::1]:8000", /IPv6/],
    ["https://api.example.com; script-src *", /semicolons/],
    ["https://api.example.com\nadd_header X 1", /control characters/],
    ['https://api.example.com" always; add_header X "1', /quotes/],
    ["https://a.example.com https://b.example.com", /spaces/],
    ["https://api.example.com,https://evil.example.com", /commas/],
  ])("refuses %j", (value, reason) => {
    expect(() => apiOrigin(value)).toThrow(reason);
  });

  it("fills exactly one placeholder and changes nothing else", () => {
    const template = "# connect-src lists __API_ORIGIN_ in prose\nadd_header CSP \"connect-src 'self' __API_ORIGIN__;\" always;\n";
    expect(fillTemplate(template, "https://api.example.com")).toBe(template.replace("__API_ORIGIN__", "https://api.example.com"));
    expect(() => fillTemplate("no placeholder", "https://x.example.com")).toThrow(/exactly once \(found 0\)/);
    expect(() => fillTemplate("__API_ORIGIN__ __API_ORIGIN__", "https://x.example.com")).toThrow(/found 2/);
  });
});
